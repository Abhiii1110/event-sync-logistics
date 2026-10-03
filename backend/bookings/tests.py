from datetime import timedelta
from unittest.mock import patch

from django.test import TestCase
from django.utils import timezone

from accounts.models import User
from payments.models import Payment
from payments.paypal_service import PayPalError
from vendors.models import VendorProfile, Service
from .lifecycle import cancel_booking, complete_booking, confirm_booking, settle_refund
from .models import Booking
from .services import (
    BookingError, BookingNotFound, InvalidTransition, change_status, create_booking,SlotUnavailable,
)


class OverlapTests(TestCase):
    def setUp(self):
        self.client_user = User.objects.create_user(
            "c1", "c1@t.com", "Test@12345", role="CLIENT")
        vendor_user = User.objects.create_user(
            "v1", "v1@t.com", "Test@12345", role="VENDOR")
        vendor = VendorProfile.objects.create(
            user=vendor_user, business_name="Spice Wheels", city="Pune", is_verified=True)
        self.service = Service.objects.create(
            vendor=vendor, category="FOOD_TRUCK", title="Package",
            price_paise=1500000, duration_minutes=240)
        self.start = timezone.now() + timedelta(days=5)

    def book(self, start):
        return create_booking(
            client=self.client_user, service=self.service,
            start_time=start, event_location="Pune")

    def test_same_time_is_rejected(self):
        self.book(self.start)
        with self.assertRaises(SlotUnavailable):
            self.book(self.start)

    def test_partial_overlap_is_rejected(self):
        self.book(self.start)
        with self.assertRaises(SlotUnavailable):
            self.book(self.start + timedelta(hours=2))

    def test_back_to_back_is_allowed(self):
        self.book(self.start)
        self.book(self.start + timedelta(minutes=240))

    def test_fee_math(self):
        b = self.book(self.start)
        self.assertEqual(b.platform_fee_paise, 150000)
        self.assertEqual(b.vendor_amount_paise, 1350000)


import threading

from django.db import connection
from django.test import TransactionTestCase




class ConcurrencyTests(TransactionTestCase):
    """Uses TransactionTestCase because threads need committed data.
    A normal TestCase wraps everything in one uncommitted transaction,
    which other threads can't see."""

    def setUp(self):
        self.client_user = User.objects.create_user(
            "c1", "c1@t.com", "Test@12345", role="CLIENT")
        vendor_user = User.objects.create_user(
            "v1", "v1@t.com", "Test@12345", role="VENDOR")
        vendor = VendorProfile.objects.create(
            user=vendor_user, business_name="Spice Wheels",
            city="Pune", is_verified=True)
        self.service = Service.objects.create(
            vendor=vendor, category="FOOD_TRUCK", title="Package",
            price_paise=1500000, duration_minutes=240)

    def test_only_one_of_many_simultaneous_bookings_wins(self):
        start = timezone.now() + timedelta(days=5)
        attempts = 5
        results = []
        barrier = threading.Barrier(attempts)  # releases all threads together

        def attempt():
            try:
                barrier.wait()
                create_booking(
                    client=self.client_user, service=self.service,
                    start_time=start, event_location="Pune")
                results.append("ok")
            except SlotUnavailable:
                results.append("conflict")
            except Exception as e:
                results.append(f"error: {e!r}")
            finally:
                connection.close()  # each thread has its own DB connection

        threads = [threading.Thread(target=attempt) for _ in range(attempts)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        self.assertEqual(results.count("ok"), 1, results)
        self.assertEqual(results.count("conflict"), attempts - 1, results)
        self.assertEqual(Booking.objects.count(), 1)

S = Booking.Status
REFUND = "payments.services.paypal_service.refund_capture"
OK = {"id": "REF1", "status": "COMPLETED"}


class LifecycleTests(TestCase):
    def setUp(self):
        self.client_user = User.objects.create_user("c1", "c1@t.com", "Test@12345", role="CLIENT")
        self.vendor_user = User.objects.create_user("v1", "v1@t.com", "Test@12345", role="VENDOR")
        self.other_vendor = User.objects.create_user("v2", "v2@t.com", "Test@12345", role="VENDOR")
        vendor = VendorProfile.objects.create(
            user=self.vendor_user, business_name="Spice Wheels", city="Pune", is_verified=True)
        self.service = Service.objects.create(
            vendor=vendor, category="FOOD_TRUCK", title="Package",
            price_paise=1500000, duration_minutes=240)

    def pending_booking(self, days_ahead=10):
        return create_booking(
            client=self.client_user, service=self.service,
            start_time=timezone.now() + timedelta(days=days_ahead), event_location="Pune")

    def paid_booking(self, days_ahead=10):
        booking = self.pending_booking(days_ahead)
        Payment.objects.create(
            booking=booking, provider="PAYPAL", provider_order_id="ORD1",
            provider_payment_id="CAP1", amount_paise=booking.total_paise,
            currency="USD", status=Payment.Status.PAID)
        change_status(booking, S.PAID, hold_expires_at=None)
        return booking

    def confirmed_booking(self, days_ahead=10):
        booking = self.paid_booking(days_ahead)
        return confirm_booking(booking_id=booking.pk, user=self.vendor_user)

    def test_vendor_confirms_paid_booking(self):
        booking = self.paid_booking()
        booking = confirm_booking(booking_id=booking.pk, user=self.vendor_user)
        self.assertEqual(booking.status, S.VENDOR_CONFIRMED)

    def test_other_vendor_cannot_confirm(self):
        booking = self.paid_booking()
        with self.assertRaises(BookingNotFound):
            confirm_booking(booking_id=booking.pk, user=self.other_vendor)

    def test_cannot_confirm_unpaid_booking(self):
        booking = self.pending_booking()
        with self.assertRaises(InvalidTransition):
            confirm_booking(booking_id=booking.pk, user=self.vendor_user)

    @patch(REFUND)
    def test_vendor_decline_refunds_in_full(self, mock_refund):
        mock_refund.return_value = OK
        booking = self.paid_booking()
        booking = cancel_booking(
            booking_id=booking.pk, user=self.vendor_user,
            reason="Busy", required_status=S.PAID)

        self.assertEqual(booking.status, S.REFUNDED)
        self.assertEqual(booking.refund_paise, booking.total_paise)
        payment = Payment.objects.get()
        self.assertEqual(payment.status, Payment.Status.REFUNDED)
        self.assertEqual(payment.refunded_paise, booking.total_paise)
        mock_refund.assert_called_once()

    @patch(REFUND)
    def test_late_client_cancel_gets_no_refund(self, mock_refund):
        booking = self.confirmed_booking(days_ahead=1)
        booking = cancel_booking(booking_id=booking.pk, user=self.client_user)
        self.assertEqual(booking.status, S.CANCELLED)
        self.assertEqual(booking.refund_paise, 0)
        mock_refund.assert_not_called()

    @patch(REFUND)
    def test_mid_notice_client_cancel_gets_half(self, mock_refund):
        mock_refund.return_value = OK
        booking = self.confirmed_booking(days_ahead=4)
        booking = cancel_booking(booking_id=booking.pk, user=self.client_user)
        self.assertEqual(booking.refund_paise, booking.total_paise // 2)
        self.assertEqual(booking.status, S.REFUNDED)

    @patch(REFUND)
    def test_gateway_failure_does_not_lose_cancellation(self, mock_refund):
        mock_refund.side_effect = PayPalError("gateway down")
        booking = self.paid_booking()
        booking = cancel_booking(booking_id=booking.pk, user=self.vendor_user,
                                 required_status=S.PAID)
        self.assertEqual(booking.status, S.CANCELLED)
        self.assertEqual(booking.refund_paise, booking.total_paise)

        mock_refund.side_effect = None            # gateway is back
        mock_refund.return_value = OK
        booking = settle_refund(booking.pk)
        self.assertEqual(booking.status, S.REFUNDED)

    @patch(REFUND)
    def test_cancelling_twice_is_rejected(self, mock_refund):
        mock_refund.return_value = OK
        booking = self.paid_booking()
        cancel_booking(booking_id=booking.pk, user=self.client_user)
        with self.assertRaises(InvalidTransition):
            cancel_booking(booking_id=booking.pk, user=self.client_user)
        self.assertEqual(mock_refund.call_count, 1)

    def test_complete_only_after_event_ends(self):
        booking = self.confirmed_booking()
        with self.assertRaises(BookingError):
            complete_booking(booking_id=booking.pk, user=self.vendor_user)

        now = timezone.now()
        Booking.objects.filter(pk=booking.pk).update(
            start_time=now - timedelta(hours=6), end_time=now - timedelta(hours=2))
        booking = complete_booking(booking_id=booking.pk, user=self.vendor_user)
        self.assertEqual(booking.status, S.COMPLETED)