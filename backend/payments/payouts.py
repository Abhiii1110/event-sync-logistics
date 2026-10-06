import logging
from datetime import timedelta

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from bookings.models import Booking
from bookings.services import S, change_status
from .models import Payment, Payout
from .payout_providers import PayoutProviderError, get_provider

logger = logging.getLogger(__name__)


class PayoutError(Exception):
    pass


class PayoutNotFound(PayoutError):
    pass


def create_completion_payout(booking):
    """Called when a booking becomes COMPLETED. Safe to call twice."""
    release_at = (booking.completed_at or timezone.now()) + timedelta(
        hours=settings.PAYOUT_DISPUTE_HOURS)
    payout, _ = Payout.objects.get_or_create(
        booking=booking,
        defaults=dict(
            vendor_id=booking.vendor_id,
            kind=Payout.Kind.COMPLETION,
            amount_paise=booking.vendor_amount_paise,
            platform_fee_paise=booking.platform_fee_paise,
            release_at=release_at,
            provider=settings.PAYOUT_PROVIDER,
        ),
    )
    return payout


def ensure_cancellation_payout(booking):
    """If a CLIENT cancelled late and the platform kept money, the vendor is
    compensated for the held slot (minus the platform fee). Safe to call twice."""
    if booking.cancelled_by != Booking.CancelledBy.CLIENT:
        return None
    if booking.status not in (S.CANCELLED, S.REFUNDED):
        return None
    if booking.status == S.CANCELLED and booking.refund_paise > 0:
        return None      # the refund hasn't been paid yet; the job calls us again later

    retained = booking.total_paise - booking.refund_paise
    if retained <= 0:
        return None

    # A booking cancelled before payment has nothing to compensate
    was_paid = Payment.objects.filter(
        booking=booking, status__in=[Payment.Status.PAID, Payment.Status.REFUNDED]
    ).exists()
    if not was_paid:
        return None

    fee = retained * settings.PLATFORM_FEE_PERCENT // 100
    payout, _ = Payout.objects.get_or_create(
        booking=booking,
        defaults=dict(
            vendor_id=booking.vendor_id,
            kind=Payout.Kind.CANCELLATION,
            amount_paise=retained - fee,
            platform_fee_paise=fee,
            release_at=timezone.now(),
            provider=settings.PAYOUT_PROVIDER,
        ),
    )
    return payout


def _mark_failed(payout_id, message):
    with transaction.atomic():
        payout = Payout.objects.select_for_update().get(pk=payout_id)
        payout.last_error = message[:255]
        payout.status = (
            Payout.Status.FAILED
            if payout.attempts >= settings.PAYOUT_MAX_ATTEMPTS
            else Payout.Status.PENDING
        )
        payout.save(update_fields=["last_error", "status", "updated_at"])


def release_payout(payout_id):
    """Pay the vendor. Idempotent, and never calls the provider while holding a lock."""
    now = timezone.now()

    # 1. Claim it. Only one worker can move PENDING -> PROCESSING.
    with transaction.atomic():
        payout = Payout.objects.select_for_update().get(pk=payout_id)
        if payout.status != Payout.Status.PENDING or payout.release_at > now:
            return payout
        payout.status = Payout.Status.PROCESSING
        payout.attempts += 1
        payout.save(update_fields=["status", "attempts", "updated_at"])

    # 2. Talk to the provider (slow, can fail) outside any lock
    try:
        reference = get_provider(payout.provider).send(payout)
    except PayoutProviderError as e:
        logger.exception("Payout %s failed", payout_id)
        _mark_failed(payout_id, str(e))
        return Payout.objects.get(pk=payout_id)

    # 3. Record success, and close the booking if this was the main payout
    with transaction.atomic():
        payout = Payout.objects.select_for_update().get(pk=payout_id)
        payout.status = Payout.Status.RELEASED
        payout.released_at = timezone.now()
        payout.provider_reference = reference
        payout.last_error = ""
        payout.save(update_fields=[
            "status", "released_at", "provider_reference", "last_error", "updated_at"])

        if payout.kind == Payout.Kind.COMPLETION:
            booking = Booking.objects.select_for_update().get(pk=payout.booking_id)
            if booking.status == S.COMPLETED:
                change_status(booking, S.PAYOUT_RELEASED)
    return payout


def reset_stuck_processing():
    """A crash between steps 1 and 3 would leave a payout PROCESSING forever.
    Putting it back to PENDING is safe because the provider call is idempotent."""
    cutoff = timezone.now() - timedelta(minutes=settings.PAYOUT_PROCESSING_TIMEOUT_MINUTES)
    return Payout.objects.filter(
        status=Payout.Status.PROCESSING, updated_at__lt=cutoff
    ).update(status=Payout.Status.PENDING)


def raise_dispute(*, booking_id, user, reason):
    """The client freezes the vendor's payout while the dispute window is open."""
    if not Booking.objects.filter(pk=booking_id, client=user).exists():
        raise PayoutNotFound("Booking not found.")

    with transaction.atomic():
        try:
            payout = Payout.objects.select_for_update().get(booking_id=booking_id)
        except Payout.DoesNotExist:
            raise PayoutError("Only completed bookings can be disputed.")

        if payout.kind != Payout.Kind.COMPLETION:
            raise PayoutError("Only completed bookings can be disputed.")
        if payout.status != Payout.Status.PENDING:
            raise PayoutError(f"This payout is already {payout.status} and cannot be disputed.")
        if payout.release_at <= timezone.now():
            raise PayoutError("The dispute window has closed.")

        payout.status = Payout.Status.DISPUTED
        payout.dispute_reason = reason[:255]
        payout.disputed_at = timezone.now()
        payout.save(update_fields=["status", "dispute_reason", "disputed_at", "updated_at"])
    return payout