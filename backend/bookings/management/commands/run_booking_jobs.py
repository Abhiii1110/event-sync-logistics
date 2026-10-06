from datetime import timedelta

from django.conf import settings
from django.core.management.base import BaseCommand
from django.utils import timezone

from bookings.lifecycle import cancel_booking, complete_booking, settle_refund
from bookings.models import Booking
from bookings.services import BookingError
from payments.models import Payout
from payments.payouts import (
    create_completion_payout, ensure_cancellation_payout, release_payout,
    reset_stuck_processing,
)

S = Booking.Status


class Command(BaseCommand):
    help = "Booking and payout housekeeping. Safe to run as often as you like."

    def _safe(self, label, fn, pk, **kwargs):
        try:
            fn(booking_id=pk, **kwargs)
            self.stdout.write(f"{label}: booking {pk} done")
        except BookingError as e:
            self.stdout.write(f"{label}: booking {pk} skipped ({e})")

    def handle(self, *args, **options):
        now = timezone.now()

        # 1. Vendor never answered a paid booking: cancel with a full refund
        cutoff = now - timedelta(hours=settings.VENDOR_RESPONSE_HOURS)
        for b in list(Booking.objects.filter(status=S.PAID, updated_at__lt=cutoff)):
            self._safe("auto-decline", cancel_booking, b.pk,
                       cancelled_by=Booking.CancelledBy.SYSTEM,
                       reason="Vendor did not respond in time")

        # 2. Event ended long enough ago: mark completed (this also creates the payout)
        cutoff = now - timedelta(hours=settings.AUTO_COMPLETE_AFTER_HOURS)
        for b in list(Booking.objects.filter(status=S.VENDOR_CONFIRMED, end_time__lt=cutoff)):
            self._safe("auto-complete", complete_booking, b.pk, system=True)

        # 3. Retry refunds that failed earlier
        for b in list(Booking.objects.filter(status=S.CANCELLED, refund_paise__gt=0)):
            settle_refund(b.pk)
            self.stdout.write(f"refund retry: booking {b.pk}")

        # 4. Backfill payouts that should exist but don't
        for b in list(Booking.objects.filter(status=S.COMPLETED, payout__isnull=True)):
            create_completion_payout(b)
            self.stdout.write(f"payout created: booking {b.pk}")
        recent = now - timedelta(days=30)
        for b in list(Booking.objects.filter(
                cancelled_by=Booking.CancelledBy.CLIENT, cancelled_at__gte=recent,
                status__in=[S.CANCELLED, S.REFUNDED], payout__isnull=True)):
            if ensure_cancellation_payout(b):
                self.stdout.write(f"cancellation payout created: booking {b.pk}")

        # 5. Free payouts stuck in PROCESSING after a crash
        stuck = reset_stuck_processing()
        if stuck:
            self.stdout.write(f"reset {stuck} stuck payout(s)")

        # 6. Release every payout whose dispute window has passed
        for p in list(Payout.objects.filter(status=Payout.Status.PENDING, release_at__lte=now)):
            result = release_payout(p.pk)
            self.stdout.write(f"payout {p.pk}: {result.status}")