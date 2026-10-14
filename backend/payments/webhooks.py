import logging

from django.utils import timezone

from .models import Payment, WebhookEvent
from .services import PaymentError, capture_and_finalize, finalize_capture, payable_problem

logger = logging.getLogger(__name__)
PAYPAL = Payment.Provider.PAYPAL


def _find_payment(order_id):
    if not order_id:
        return None
    return (Payment.objects.select_related("booking")
            .filter(provider=PAYPAL, provider_order_id=order_id).first())


def _order_id_of_capture(resource):
    return ((resource.get("supplementary_data") or {}).get("related_ids") or {}).get("order_id")


def on_order_approved(event):
    """The buyer approved the order. Capture it here too, in case their browser never did."""
    order = event.get("resource") or {}
    payment = _find_payment(order.get("id"))
    if payment is None:
        return "no matching payment"
    if payment.status != Payment.Status.CREATED:
        return f"payment already {payment.status}"
    problem = payable_problem(payment.booking)
    if problem:
        return f"not captured: {problem}"        # an approved order that is never captured moves no money
    result = capture_and_finalize(payment)
    return f"captured by webhook, payment is {result.status}"


def on_capture_completed(event):
    capture = event.get("resource") or {}
    payment = _find_payment(_order_id_of_capture(capture))
    if payment is None:
        return "no matching payment"
    result = finalize_capture(payment.pk, capture)
    return f"payment is {result.status}"


def on_capture_denied(event):
    capture = event.get("resource") or {}
    payment = _find_payment(_order_id_of_capture(capture))
    if payment is None:
        return "no matching payment"
    changed = Payment.objects.filter(pk=payment.pk, status=Payment.Status.CREATED).update(
        status=Payment.Status.FAILED, raw_response=capture)
    return "payment marked failed" if changed else f"payment already {payment.status}"


HANDLERS = {
    "CHECKOUT.ORDER.APPROVED": on_order_approved,
    "PAYMENT.CAPTURE.COMPLETED": on_capture_completed,
    "PAYMENT.CAPTURE.DENIED": on_capture_denied,
}


def process_event(event):
    """Store and handle one PayPal event. Duplicates are ignored; failures can be retried."""
    event_id, event_type = event.get("id"), event.get("event_type")
    if not event_id or not event_type:
        raise ValueError("Not a PayPal event.")

    record, _ = WebhookEvent.objects.get_or_create(
        provider=PAYPAL, event_id=event_id,
        defaults={"event_type": event_type, "payload": event})

    if record.status in (WebhookEvent.Status.PROCESSED, WebhookEvent.Status.IGNORED):
        return record                                  # PayPal delivered it twice

    handler = HANDLERS.get(event_type)
    if handler is None:
        record.status = WebhookEvent.Status.IGNORED
        record.note = "no handler for this event type"
        record.processed_at = timezone.now()
        record.save(update_fields=["status", "note", "processed_at"])
        return record

    record.attempts += 1
    try:
        record.note = (handler(event) or "")[:255]
        record.status = WebhookEvent.Status.PROCESSED
    except PaymentError as exc:
        # A business rule said no. Retrying cannot change that, so a human should look.
        record.status = WebhookEvent.Status.REVIEW
        record.note = str(exc)[:255]
        logger.error("Webhook %s needs review: %s", event_id, exc)
    except Exception as exc:
        # Probably temporary (network, database). Return an error so PayPal retries later.
        record.status = WebhookEvent.Status.FAILED
        record.note = str(exc)[:255]
        record.save(update_fields=["status", "note", "attempts"])
        raise

    record.processed_at = timezone.now()
    record.save(update_fields=["status", "note", "attempts", "processed_at"])
    return record