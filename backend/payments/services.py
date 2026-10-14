import logging
from decimal import Decimal, InvalidOperation

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from bookings.models import Booking
from bookings.services import BookingError, change_status, has_overlap, mark_booking_paid
from vendors.models import VendorProfile
from . import paypal_service
from .models import Payment
from .paypal_service import PayPalError

logger = logging.getLogger(__name__)
S = Booking.Status


class PaymentError(Exception):
    pass


class PaymentNotFound(PaymentError):
    pass


def _extract_capture(data):
    try:
        return data["purchase_units"][0]["payments"]["captures"][0]
    except (KeyError, IndexError, TypeError):
        return None


def payable_problem(booking):
    """Why this booking cannot take a payment right now, or None if it can."""
    if booking.status != S.PENDING_PAYMENT:
        return "This booking is no longer awaiting payment."
    hold_over = booking.hold_expires_at is None or booking.hold_expires_at <= timezone.now()
    if hold_over and has_overlap(
            booking.vendor_id, booking.start_time, booking.end_time, booking.pk):
        return "This time slot is no longer available."
    return None


def create_paypal_payment(*, user, booking_id):
    try:
        booking = Booking.objects.get(pk=booking_id, client=user)
    except Booking.DoesNotExist:
        raise PaymentNotFound("Booking not found.")

    if booking.status != S.PENDING_PAYMENT:
        raise PaymentError("This booking is not awaiting payment.")
    if booking.hold_expires_at is None or booking.hold_expires_at <= timezone.now():
        raise PaymentError("The slot hold has expired. Please book again.")

    # Clicking "Pay" twice must not create two orders
    open_payment = Payment.objects.filter(
        booking=booking, provider=Payment.Provider.PAYPAL, status=Payment.Status.CREATED
    ).first()
    if open_payment:
        return open_payment

    attempt = Payment.objects.filter(booking=booking, provider=Payment.Provider.PAYPAL).count() + 1
    order = paypal_service.create_order(booking, attempt)

    # get_or_create: two simultaneous requests end up with ONE row instead of a crash
    payment, _ = Payment.objects.get_or_create(
        provider=Payment.Provider.PAYPAL,
        provider_order_id=order["id"],
        defaults=dict(
            booking=booking,
            amount_paise=booking.total_paise,
            currency=settings.PAYPAL_CURRENCY,
            status=Payment.Status.CREATED,
            raw_response=order,
        ),
    )
    return payment


def finalize_capture(payment_id, capture):
    """Record a COMPLETED PayPal capture.

    The browser flow, the webhook and the reconciliation job all call this, possibly
    at the same moment and possibly more than once. The row locks and the status
    check make every combination safe: the booking is paid exactly once.
    """
    if capture.get("status") != "COMPLETED":
        raise PaymentError("PayPal has not completed this payment.")

    outcome = "already_done"
    with transaction.atomic():
        payment = Payment.objects.select_for_update().get(pk=payment_id)

        if payment.status == Payment.Status.CREATED:
            amount = capture.get("amount") or {}
            expected = Decimal(payment.amount_paise) / 100
            try:
                paid = Decimal(str(amount.get("value", "")))
            except InvalidOperation:
                paid = None

            if paid != expected or amount.get("currency_code") != payment.currency:
                payment.status = Payment.Status.FAILED
                payment.raw_response = capture
                payment.save(update_fields=["status", "raw_response", "updated_at"])
                outcome = "mismatch"
            else:
                # Same lock order as create_booking: vendor first, then the booking
                VendorProfile.objects.select_for_update().get(pk=payment.booking.vendor_id)
                booking = Booking.objects.select_for_update().get(pk=payment.booking_id)
                usable = booking.status == S.PENDING_PAYMENT and not has_overlap(
                    booking.vendor_id, booking.start_time, booking.end_time, booking.pk)

                payment.provider_payment_id = capture.get("id", "")
                payment.raw_response = capture
                if usable:
                    payment.status = Payment.Status.PAID
                    mark_booking_paid(booking)
                    outcome = "paid"
                else:
                    # Cancelled meanwhile, or the slot was taken after the hold expired
                    payment.status = Payment.Status.REFUND_DUE
                    outcome = "unusable"
                payment.save(update_fields=[
                    "status", "provider_payment_id", "raw_response", "updated_at"])

        elif payment.status == Payment.Status.REFUND_DUE:
            outcome = "unusable"          # an earlier refund attempt failed: try again

    if outcome == "mismatch":
        logger.error("Amount mismatch on payment %s", payment_id)
        raise PaymentError("Amount mismatch. Payment flagged for review.")

    if outcome == "unusable":
        try:
            refund_unusable_payment(payment_id)
        except (PayPalError, PaymentError):
            logger.exception("Refund for payment %s failed; the job will retry it", payment_id)

    return Payment.objects.get(pk=payment_id)


def capture_and_finalize(payment):
    """Capture an approved PayPal order and record the result."""
    problem = payable_problem(payment.booking)
    if problem:
        raise PaymentError(problem)

    data = paypal_service.capture_order(payment.provider_order_id)
    capture = _extract_capture(data)
    if data.get("status") != "COMPLETED" or not capture or capture.get("status") != "COMPLETED":
        raise PaymentError("PayPal has not completed this payment yet.")
    return finalize_capture(payment.pk, capture)


def capture_paypal_payment(*, user, paypal_order_id):
    # 1. Find OUR record first. Unknown orders (or other users' orders) are rejected.
    try:
        payment = Payment.objects.select_related("booking").get(
            provider=Payment.Provider.PAYPAL,
            provider_order_id=paypal_order_id,
            booking__client=user,
        )
    except Payment.DoesNotExist:
        raise PaymentNotFound("Unknown order.")

    # 2. Idempotent: whatever already happened is reported, nothing is redone
    if payment.status == Payment.Status.PAID:
        return payment
    if payment.status in (Payment.Status.REFUND_DUE, Payment.Status.REFUNDED):
        raise PaymentError("This payment could not be applied to the booking and is being refunded.")
    if payment.status != Payment.Status.CREATED:
        raise PaymentError(f"Payment is {payment.status}; it cannot be captured.")

    payment = capture_and_finalize(payment)
    if payment.status != Payment.Status.PAID:
        raise PaymentError(
            "The time slot was taken while you were paying, so your payment is being refunded in full.")
    return payment


def reconcile_open_payment(payment):
    """Ask PayPal what really happened to an order we never heard back about."""
    order = paypal_service.get_order(payment.provider_order_id)
    capture = _extract_capture(order)
    if order.get("status") == "COMPLETED" and capture and capture.get("status") == "COMPLETED":
        return finalize_capture(payment.pk, capture)
    if order.get("status") == "APPROVED" and payable_problem(payment.booking) is None:
        return capture_and_finalize(payment)           # approved but nobody captured it
    return payment


def refund_booking_payment(booking_id):
    """Refund booking.refund_paise on its paid PayPal payment. Safe to call repeatedly."""
    booking = Booking.objects.get(pk=booking_id)
    if booking.refund_paise <= 0:
        return None

    payment = Payment.objects.filter(
        booking=booking, provider=Payment.Provider.PAYPAL,
        status__in=[Payment.Status.PAID, Payment.Status.REFUNDED],
    ).first()
    if payment is None:
        raise PaymentError("No paid payment found for this booking.")
    if booking.refund_paise > payment.amount_paise:
        raise PaymentError("Refund is larger than the amount paid.")

    if payment.status == Payment.Status.PAID:
        result = paypal_service.refund_capture(
            payment.provider_payment_id, booking.refund_paise, f"refund-{payment.pk}")
        if result.get("status") not in ("COMPLETED", "PENDING"):
            raise PaymentError(f"Refund not accepted: {result.get('status')}")

        with transaction.atomic():
            payment = Payment.objects.select_for_update().get(pk=payment.pk)
            if payment.status == Payment.Status.PAID:
                payment.status = Payment.Status.REFUNDED
                payment.refunded_paise = booking.refund_paise
                payment.refund_id = result["id"]
                payment.save(update_fields=[
                    "status", "refunded_paise", "refund_id", "updated_at"])

    with transaction.atomic():
        locked = Booking.objects.select_for_update().get(pk=booking_id)
        if locked.status == Booking.Status.CANCELLED:
            change_status(locked, Booking.Status.REFUNDED)
    return payment

def refund_unusable_payment(payment_id):
    """A payment arrived that cannot be applied to its booking. Return it in full."""
    payment = Payment.objects.get(pk=payment_id)
    if payment.status != Payment.Status.REFUND_DUE:
        return payment

    result = paypal_service.refund_capture(
        payment.provider_payment_id, payment.amount_paise, f"refund-{payment.pk}")
    if result.get("status") not in ("COMPLETED", "PENDING"):
        raise PaymentError(f"Refund not accepted: {result.get('status')}")

    with transaction.atomic():
        payment = Payment.objects.select_for_update().get(pk=payment_id)
        if payment.status == Payment.Status.REFUND_DUE:
            payment.status = Payment.Status.REFUNDED
            payment.refunded_paise = payment.amount_paise
            payment.refund_id = result["id"]
            payment.save(update_fields=["status", "refunded_paise", "refund_id", "updated_at"])

        booking = Booking.objects.select_for_update().get(pk=payment.booking_id)
        if booking.status == S.PENDING_PAYMENT:
            change_status(
                booking, S.CANCELLED,
                cancelled_at=timezone.now(), cancelled_by=Booking.CancelledBy.SYSTEM,
                cancel_reason="The slot was no longer available when the payment arrived",
                refund_paise=booking.total_paise, hold_expires_at=None)
            change_status(booking, S.REFUNDED)
        elif booking.status == S.CANCELLED and booking.refund_paise == 0:
            change_status(booking, S.REFUNDED, refund_paise=booking.total_paise)
    return payment