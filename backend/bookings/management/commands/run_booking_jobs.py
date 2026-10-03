from datetime import timedelta

from django.conf import settings
from django.core.management.base import BaseCommand
from django.utils import timezone

from bookings.lifecycle import cancel_booking, complete_booking, settle_refund
from bookings.models import Booking
from bookings.services import BookingError

S = Booking.Status


class Command(BaseCommand):
    help = "Auto-decline unanswered bookings, auto-complete finished events, retry failed refunds."

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

        # 2. Event ended long enough ago: mark completed
        cutoff = now - timedelta(hours=settings.AUTO_COMPLETE_AFTER_HOURS)
        for b in list(Booking.objects.filter(status=S.VENDOR_CONFIRMED, end_time__lt=cutoff)):
            self._safe("auto-complete", complete_booking, b.pk, system=True)

        # 3. Retry refunds that failed earlier (gateway was down)
        for b in list(Booking.objects.filter(status=S.CANCELLED, refund_paise__gt=0)):
            settle_refund(b.pk)
            self.stdout.write(f"refund retry: booking {b.pk}")