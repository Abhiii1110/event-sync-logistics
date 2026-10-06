from datetime import timedelta
from unittest.mock import patch

from django.conf import settings
from django.test import TestCase
from django.utils import timezone

from accounts.models import User
from bookings.lifecycle import cancel_booking, complete_booking, confirm_booking
from bookings.models import Booking
from bookings.services import change_status, create_booking
from vendors.models import Service, VendorProfile

from .models import Payment, Payout
from .payout_providers import PayoutProviderError
from .payouts import (
    PayoutError, PayoutNotFound, raise_dispute, release_payout, reset_stuck_processing,
)

S = Booking.Status
SEND = "payments.payout_providers.MockPayoutProvider.send"
REFUND = "payments.services.paypal_service.refund_capture"
REFUND_OK = {"id": "REF1", "status": "COMPLETED"}


class PayoutTests(TestCase):
    def setUp(self):
        self.client_user = User.objects.create_user("c1", "c1@t.com", "Test@12345", role="CLIENT")
        self.other_user = User.objects.create_user("c2", "c2@t.com", "Test@12345", role="CLIENT")
        self.vendor_user = User.objects.create_user("v1", "v1@t.com", "Test@12345", role="VENDOR")
        vendor = VendorProfile.objects.create(
            user=self.vendor_user, business_name="Spice Wheels", city="Pune", is_verified=True)
        self.service = Service.objects.create(
            vendor=vendor, category="FOOD_TRUCK", title="Package",
            price_paise=1500000, duration_minutes=240)

    # ---- helpers -------------------------------------------------------
    def pending_booking(self, days_ahead=10):
        return create_booking(
            client=self.client_user, service=self.service,
            start_time=timezone.now() + timedelta(days=days_ahead), event_location="Pune")

    def paid_booking(self, days_ahead=10):
        booking = self.pending_booking(days_ahead)
        Payment.objects.create(
            booking=booking, provider="PAYPAL", provider_order_id=f"ORD{booking.pk}",
            provider_payment_id=f"CAP{booking.pk}", amount_paise=booking.total_paise,
            currency="USD", status=Payment.Status.PAID)
        change_status(booking, S.PAID, hold_expires_at=None)
        return booking

    def completed_booking(self):
        booking = self.paid_booking()
        confirm_booking(booking_id=booking.pk, user=self.vendor_user)
        now = timezone.now()
        Booking.objects.filter(pk=booking.pk).update(
            start_time=now - timedelta(hours=6), end_time=now - timedelta(hours=2))
        return complete_booking(booking_id=booking.pk, user=self.vendor_user)

    def make_due(self, payout):
        Payout.objects.filter(pk=payout.pk).update(
            release_at=timezone.now() - timedelta(minutes=1))

    # ---- completion payouts -------------------------------------------
    def test_completion_creates_pending_payout(self):
        booking = self.completed_booking()
        payout = Payout.objects.get(booking=booking)
        self.assertEqual(payout.status, Payout.Status.PENDING)
        self.assertEqual(payout.kind, Payout.Kind.COMPLETION)
        self.assertEqual(payout.amount_paise, 1350000)
        self.assertEqual(payout.platform_fee_paise, 150000)
        self.assertEqual(
            payout.release_at,
            booking.completed_at + timedelta(hours=settings.PAYOUT_DISPUTE_HOURS))

    @patch(SEND)
    def test_not_released_inside_dispute_window(self, mock_send):
        payout = Payout.objects.get(booking=self.completed_booking())
        release_payout(payout.pk)
        mock_send.assert_not_called()
        payout.refresh_from_db()
        self.assertEqual(payout.status, Payout.Status.PENDING)

    @patch(SEND, return_value="REF1")
    def test_release_pays_once_and_closes_booking(self, mock_send):
        booking = self.completed_booking()
        payout = Payout.objects.get(booking=booking)
        self.make_due(payout)

        release_payout(payout.pk)
        release_payout(payout.pk)          # second call must do nothing

        self.assertEqual(mock_send.call_count, 1)
        payout.refresh_from_db()
        booking.refresh_from_db()
        self.assertEqual(payout.status, Payout.Status.RELEASED)
        self.assertEqual(payout.provider_reference, "REF1")
        self.assertEqual(booking.status, S.PAYOUT_RELEASED)

    @patch(SEND, side_effect=PayoutProviderError("bank down"))
    def test_failures_retry_then_need_attention(self, mock_send):
        payout = Payout.objects.get(booking=self.completed_booking())
        self.make_due(payout)

        release_payout(payout.pk)
        payout.refresh_from_db()
        self.assertEqual(payout.status, Payout.Status.PENDING)     # will be retried
        self.assertEqual(payout.attempts, 1)
        self.assertIn("bank down", payout.last_error)

        for _ in range(settings.PAYOUT_MAX_ATTEMPTS - 1):
            release_payout(payout.pk)
        payout.refresh_from_db()
        self.assertEqual(payout.status, Payout.Status.FAILED)
        self.assertEqual(payout.attempts, settings.PAYOUT_MAX_ATTEMPTS)

    def test_stuck_processing_is_reset(self):
        payout = Payout.objects.get(booking=self.completed_booking())
        Payout.objects.filter(pk=payout.pk).update(
            status=Payout.Status.PROCESSING,
            updated_at=timezone.now() - timedelta(minutes=30))
        self.assertEqual(reset_stuck_processing(), 1)
        payout.refresh_from_db()
        self.assertEqual(payout.status, Payout.Status.PENDING)

    # ---- disputes ------------------------------------------------------
    @patch(SEND)
    def test_dispute_freezes_payout(self, mock_send):
        booking = self.completed_booking()
        raise_dispute(booking_id=booking.pk, user=self.client_user, reason="No show")
        payout = Payout.objects.get(booking=booking)
        self.make_due(payout)

        release_payout(payout.pk)
        mock_send.assert_not_called()
        payout.refresh_from_db()
        self.assertEqual(payout.status, Payout.Status.DISPUTED)

    def test_dispute_rejected_after_window_closes(self):
        booking = self.completed_booking()
        self.make_due(Payout.objects.get(booking=booking))
        with self.assertRaises(PayoutError):
            raise_dispute(booking_id=booking.pk, user=self.client_user, reason="Late")

    def test_other_user_cannot_dispute(self):
        booking = self.completed_booking()
        with self.assertRaises(PayoutNotFound):
            raise_dispute(booking_id=booking.pk, user=self.other_user, reason="Not mine")

    # ---- cancellation compensation ------------------------------------
    @patch(SEND, return_value="REF2")
    def test_late_client_cancel_compensates_vendor(self, mock_send):
        booking = self.paid_booking(days_ahead=1)
        confirm_booking(booking_id=booking.pk, user=self.vendor_user)
        cancel_booking(booking_id=booking.pk, user=self.client_user)

        payout = Payout.objects.get(booking=booking)
        self.assertEqual(payout.kind, Payout.Kind.CANCELLATION)
        self.assertEqual(payout.amount_paise, 1350000)     # 1,500,000 kept, minus 10% fee
        self.assertEqual(payout.platform_fee_paise, 150000)

        release_payout(payout.pk)
        payout.refresh_from_db()
        booking.refresh_from_db()
        self.assertEqual(payout.status, Payout.Status.RELEASED)
        self.assertEqual(booking.status, S.CANCELLED)      # cancellation payouts don't change it

    @patch(REFUND, return_value=REFUND_OK)
    def test_half_refund_pays_vendor_the_other_half(self, mock_refund):
        booking = self.paid_booking(days_ahead=4)
        confirm_booking(booking_id=booking.pk, user=self.vendor_user)
        cancel_booking(booking_id=booking.pk, user=self.client_user)

        payout = Payout.objects.get(booking=booking)
        self.assertEqual(payout.amount_paise, 675000)      # 750,000 kept, minus 10%
        self.assertEqual(payout.platform_fee_paise, 75000)

    @patch(REFUND, return_value=REFUND_OK)
    def test_no_compensation_when_nothing_was_kept(self, mock_refund):
        unpaid = self.pending_booking(days_ahead=20)
        cancel_booking(booking_id=unpaid.pk, user=self.client_user)

        paid = self.paid_booking(days_ahead=10)
        cancel_booking(booking_id=paid.pk, user=self.vendor_user, required_status=S.PAID)

        self.assertEqual(Payout.objects.count(), 0)