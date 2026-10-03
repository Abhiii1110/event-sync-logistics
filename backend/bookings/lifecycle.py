import logging

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from payments.paypal_service import PayPalError
from payments.services import PaymentError, refund_booking_payment

from .models import Booking
from .services import (
    S, BookingError, BookingNotFound, InvalidTransition, change_status, check_transition,
)

logger = logging.getLogger(__name__)
Who = Booking.CancelledBy


def role_for(booking, user):
    """Is this user the booking's client, its vendor, or an admin? Otherwise: 404."""
    if booking.client_id == user.id:
        return Who.CLIENT
    if booking.vendor.user_id == user.id:
        return Who.VENDOR
    if user.role == "ADMIN":
        return Who.ADMIN
    raise BookingNotFound("Booking not found.")   # 404, so we don't reveal it exists


def _get_locked(booking_id):
    """Row-lock the booking so two simultaneous actions can't both succeed."""
    try:
        return Booking.objects.select_for_update().get(pk=booking_id)
    except Booking.DoesNotExist:
        raise BookingNotFound("Booking not found.")


def refund_amount(booking, cancelled_by, now=None):
    now = now or timezone.now()
    if booking.status == S.PENDING_PAYMENT:
        return 0                                    # nothing was paid
    if cancelled_by != Who.CLIENT:
        return booking.total_paise                  # vendor/admin/system: full refund
    if booking.status == S.PAID:
        return booking.total_paise                  # vendor hasn't committed yet

    hours_left = (booking.start_time - now).total_seconds() / 3600
    if hours_left >= settings.CANCEL_FULL_REFUND_HOURS:
        percent = 100
    elif hours_left >= settings.CANCEL_HALF_REFUND_HOURS:
        percent = 50
    else:
        percent = 0
    return booking.total_paise * percent // 100


def confirm_booking(*, booking_id, user):
    with transaction.atomic():
        booking = _get_locked(booking_id)
        if role_for(booking, user) != Who.VENDOR:
            raise BookingError("Only the vendor can confirm a booking.")
        check_transition(booking, S.VENDOR_CONFIRMED)
        if booking.start_time <= timezone.now():
            raise BookingError("The event start time has already passed.")
        change_status(booking, S.VENDOR_CONFIRMED, vendor_confirmed_at=timezone.now())
    return booking


def complete_booking(*, booking_id, user=None, system=False):
    with transaction.atomic():
        booking = _get_locked(booking_id)
        if not system and role_for(booking, user) != Who.VENDOR:
            raise BookingError("Only the vendor can complete a booking.")
        check_transition(booking, S.COMPLETED)
        if booking.end_time > timezone.now():
            raise BookingError("The event has not ended yet.")
        change_status(booking, S.COMPLETED, completed_at=timezone.now())
    return booking


def cancel_booking(*, booking_id, user=None, cancelled_by=None, reason="", required_status=None):
    now = timezone.now()
    with transaction.atomic():
        booking = _get_locked(booking_id)
        actor = cancelled_by or role_for(booking, user)

        if required_status and booking.status != required_status:
            raise InvalidTransition(f"This action needs a booking in status {required_status}.")
        check_transition(booking, S.CANCELLED)
        if actor != Who.SYSTEM and booking.start_time <= now:
            raise BookingError("The event has already started, so it can no longer be cancelled.")

        # refund_amount() reads the status BEFORE it changes, so it is called as an argument
        change_status(
            booking, S.CANCELLED,
            cancelled_at=now, cancelled_by=actor, cancel_reason=reason[:255],
            refund_paise=refund_amount(booking, actor, now), hold_expires_at=None,
        )

    # Money moves only AFTER the cancellation is safely committed
    return settle_refund(booking_id)


def settle_refund(booking_id):
    """Try to pay out the refund owed. If the gateway is down, the booking stays
    CANCELLED with refund_paise > 0, and the background job retries later."""
    booking = Booking.objects.get(pk=booking_id)
    if booking.status == S.CANCELLED and booking.refund_paise > 0:
        try:
            refund_booking_payment(booking_id)
        except (PaymentError, PayPalError):
            logger.exception("Refund for booking %s failed; it will be retried", booking_id)
        booking.refresh_from_db()
    return booking