from datetime import timedelta
from unittest.mock import patch

from django.test import TestCase
from django.utils import timezone

from accounts.models import User
from bookings.models import Booking
from bookings.services import create_booking
from vendors.models import VendorProfile, Service
from .models import Payment
from .services import (
    PaymentError, PaymentNotFound, capture_paypal_payment, create_paypal_payment,
)


def paypal_capture_response(value="15000.00", currency="USD"):
    return {
        "status": "COMPLETED",
        "purchase_units": [{"payments": {"captures": [
            {"id": "CAP1", "status": "COMPLETED",
             "amount": {"currency_code": currency, "value": value}}
        ]}}],
    }


class PayPalFlowTests(TestCase):
    def setUp(self):
        self.client_user = User.objects.create_user("c1", "c1@t.com", "Test@12345", role="CLIENT")
        self.other_user = User.objects.create_user("c2", "c2@t.com", "Test@12345", role="CLIENT")
        vendor_user = User.objects.create_user("v1", "v1@t.com", "Test@12345", role="VENDOR")
        vendor = VendorProfile.objects.create(
            user=vendor_user, business_name="Spice Wheels", city="Pune", is_verified=True)
        service = Service.objects.create(
            vendor=vendor, category="FOOD_TRUCK", title="Package",
            price_paise=1500000, duration_minutes=240)
        self.booking = create_booking(
            client=self.client_user, service=service,
            start_time=timezone.now() + timedelta(days=5), event_location="Pune")

    @patch("payments.services.paypal_service.create_order")
    def make_payment(self, mock_create):
        mock_create.return_value = {"id": "ORDER123", "links": []}
        return create_paypal_payment(user=self.client_user, booking_id=self.booking.pk)

    @patch("payments.services.paypal_service.capture_order")
    def test_capture_marks_booking_paid_and_is_idempotent(self, mock_capture):
        self.make_payment()
        mock_capture.return_value = paypal_capture_response()

        capture_paypal_payment(user=self.client_user, paypal_order_id="ORDER123")
        capture_paypal_payment(user=self.client_user, paypal_order_id="ORDER123")

        self.assertEqual(mock_capture.call_count, 1)   # PayPal was only called once
        self.booking.refresh_from_db()
        self.assertEqual(self.booking.status, Booking.Status.PAID)

    @patch("payments.services.paypal_service.capture_order")
    def test_amount_mismatch_is_rejected(self, mock_capture):
        self.make_payment()
        mock_capture.return_value = paypal_capture_response(value="1.00")

        with self.assertRaises(PaymentError):
            capture_paypal_payment(user=self.client_user, paypal_order_id="ORDER123")

        self.booking.refresh_from_db()
        self.assertEqual(self.booking.status, Booking.Status.PENDING_PAYMENT)
        self.assertEqual(Payment.objects.get().status, Payment.Status.FAILED)

    def test_other_user_cannot_capture(self):
        self.make_payment()
        with self.assertRaises(PaymentNotFound):
            capture_paypal_payment(user=self.other_user, paypal_order_id="ORDER123")

    def test_expired_hold_blocks_order_creation(self):
        Booking.objects.filter(pk=self.booking.pk).update(
            hold_expires_at=timezone.now() - timedelta(minutes=1))
        with self.assertRaises(PaymentError):
            create_paypal_payment(user=self.client_user, booking_id=self.booking.pk)