import logging
from decimal import Decimal

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from bookings.models import Booking
from bookings.services import BookingError, change_status,mark_booking_paid
from . import paypal_service
from .models import Payment

logger = logging.getLogger(__name__)


class PaymentError(Exception):
    pass


class PaymentNotFound(PaymentError):
    pass


def _extract_capture(data):
    try:
        return data["purchase_units"][0]["payments"]["captures"][0]
    except (KeyError, IndexError, TypeError):
        return None


def create_paypal_payment(*, user, booking_id):
    # Only the booking's own client can pay for it
    try:
        booking = Booking.objects.get(pk=booking_id, client=user)
    except Booking.DoesNotExist:
        raise PaymentNotFound("Booking not found.")

    if booking.status != Booking.Status.PENDING_PAYMENT:
        raise PaymentError("This booking is not awaiting payment.")
    if booking.hold_expires_at is None or booking.hold_expires_at <= timezone.now():
        raise PaymentError("The slot hold has expired. Please book again.")

    # Clicking "Pay" twice must not create two orders
    existing = Payment.objects.filter(
        booking=booking, provider=Payment.Provider.PAYPAL, status=Payment.Status.CREATED
    ).first()
    if existing:
        return existing

    # The amount comes from OUR database, never from the request
    order = paypal_service.create_order(booking)

    return Payment.objects.create(
        booking=booking,
        provider=Payment.Provider.PAYPAL,
        provider_order_id=order["id"],
        amount_paise=booking.total_paise,
        currency=settings.PAYPAL_CURRENCY,
        status=Payment.Status.CREATED,
        raw_response=order,
    )


def capture_paypal_payment(*, user, paypal_order_id):
    # 1. Find OUR record first. Unknown orders (or other users' orders) are rejected.
    try:
        payment = Payment.objects.get(
            provider=Payment.Provider.PAYPAL,
            provider_order_id=paypal_order_id,
            booking__client=user,
        )
    except Payment.DoesNotExist:
        raise PaymentNotFound("Unknown order.")

    # 2. Idempotent: already paid means success, nothing is redone
    if payment.status == Payment.Status.PAID:
        return payment
    if payment.status != Payment.Status.CREATED:
        raise PaymentError(f"Payment is {payment.status}; it cannot be captured.")
    if payment.booking.status != Booking.Status.PENDING_PAYMENT:
        raise PaymentError("This booking is no longer awaiting payment.")

    # 3. Ask PayPal to capture the money
    data = paypal_service.capture_order(paypal_order_id)
    capture = _extract_capture(data)

    if data.get("status") != "COMPLETED" or not capture or capture.get("status") != "COMPLETED":
        raise PaymentError("PayPal has not completed this payment.")

    # 4. Verify the amount PayPal actually captured matches our records
    expected = Decimal(payment.amount_paise) / 100
    paid = Decimal(capture["amount"]["value"])
    if paid != expected or capture["amount"]["currency_code"] != payment.currency:
        Payment.objects.filter(pk=payment.pk).update(
            status=Payment.Status.FAILED, raw_response=data
        )
        logger.error("Amount mismatch on PayPal order %s", paypal_order_id)
        raise PaymentError("Amount mismatch. Payment flagged for review.")

    # 5. Update payment and booking together, or not at all
    with transaction.atomic():
        payment = Payment.objects.select_for_update().get(pk=payment.pk)
        if payment.status == Payment.Status.PAID:      # a parallel request got here first
            return payment

        booking = Booking.objects.select_for_update().get(pk=payment.booking_id)
        try:
            mark_booking_paid(booking)
        except BookingError as e:
            raise PaymentError(str(e))

        payment.status = Payment.Status.PAID
        payment.provider_payment_id = capture["id"]
        payment.raw_response = data
        payment.save(update_fields=["status", "provider_payment_id", "raw_response", "updated_at"])

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