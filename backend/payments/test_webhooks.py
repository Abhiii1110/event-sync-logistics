from datetime import timedelta
from unittest.mock import MagicMock, patch

from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from accounts.models import User
from bookings.lifecycle import cancel_booking
from bookings.models import Booking
from bookings.services import change_status, create_booking
from vendors.models import Service, VendorProfile

from .models import Payment, WebhookEvent
from .paypal_service import PayPalError
from .services import (
    capture_paypal_payment, create_paypal_payment, reconcile_open_payment,
    refund_unusable_payment,
)
from .webhooks import process_event

S = Booking.Status
REFUND = "payments.services.paypal_service.refund_capture"
CAPTURE = "payments.services.paypal_service.capture_order"
GET_ORDER = "payments.services.paypal_service.get_order"
REFUND_OK = {"id": "REF1", "status": "COMPLETED"}


def capture_response(value="15000.00"):
    return {"status": "COMPLETED", "purchase_units": [{"payments": {"captures": [
        {"id": "CAP1", "status": "COMPLETED",
         "amount": {"currency_code": "USD", "value": value}}]}}]}


def completed_event(event_id, order_id, value="15000.00"):
    return {
        "id": event_id,
        "event_type": "PAYMENT.CAPTURE.COMPLETED",
        "resource": {
            "id": f"CAP-{event_id}",
            "status": "COMPLETED",
            "amount": {"currency_code": "USD", "value": value},
            "supplementary_data": {"related_ids": {"order_id": order_id}},
        },
    }


class Base(TestCase):
    def setUp(self):
        self.client_user = User.objects.create_user("c1", "c1@t.com", "Test@12345", role="CLIENT")
        self.other_client = User.objects.create_user("c2", "c2@t.com", "Test@12345", role="CLIENT")
        vendor_user = User.objects.create_user("v1", "v1@t.com", "Test@12345", role="VENDOR")
        vendor = VendorProfile.objects.create(
            user=vendor_user, business_name="Spice Wheels", city="Pune", is_verified=True)
        self.service = Service.objects.create(
            vendor=vendor, category="FOOD_TRUCK", title="Package",
            price_paise=1500000, duration_minutes=240)
        self.start = timezone.now() + timedelta(days=10)

    def booking_for(self, user):
        return create_booking(
            client=user, service=self.service, start_time=self.start, event_location="Pune")

    def open_payment(self, booking, order_id="ORD1"):
        return Payment.objects.create(
            booking=booking, provider="PAYPAL", provider_order_id=order_id,
            amount_paise=booking.total_paise, currency="USD", status=Payment.Status.CREATED)

    def expire_hold(self, booking):
        Booking.objects.filter(pk=booking.pk).update(
            hold_expires_at=timezone.now() - timedelta(minutes=1))


class WebhookFlowTests(Base):
    def test_capture_event_marks_booking_paid(self):
        booking = self.booking_for(self.client_user)
        self.open_payment(booking)
        record = process_event(completed_event("EV1", "ORD1"))
        booking.refresh_from_db()
        self.assertEqual(booking.status, S.PAID)
        self.assertEqual(Payment.objects.get().status, Payment.Status.PAID)
        self.assertEqual(record.status, WebhookEvent.Status.PROCESSED)

    def test_duplicate_event_is_processed_once(self):
        booking = self.booking_for(self.client_user)
        self.open_payment(booking)
        event = completed_event("EV1", "ORD1")
        with patch("payments.webhooks.finalize_capture",
                   return_value=MagicMock(pk=1, status="PAID")) as fake:
            process_event(event)
            process_event(event)
        self.assertEqual(fake.call_count, 1)
        self.assertEqual(WebhookEvent.objects.count(), 1)

    @patch(CAPTURE)
    def test_browser_capture_after_webhook_does_nothing_more(self, mock_capture):
        booking = self.booking_for(self.client_user)
        self.open_payment(booking)
        process_event(completed_event("EV1", "ORD1"))
        payment = capture_paypal_payment(user=self.client_user, paypal_order_id="ORD1")
        self.assertEqual(payment.status, Payment.Status.PAID)
        mock_capture.assert_not_called()

    @patch(CAPTURE)
    def test_approval_event_captures_when_the_browser_did_not(self, mock_capture):
        booking = self.booking_for(self.client_user)
        self.open_payment(booking)
        mock_capture.return_value = capture_response()
        process_event({"id": "EV2", "event_type": "CHECKOUT.ORDER.APPROVED",
                       "resource": {"id": "ORD1"}})
        booking.refresh_from_db()
        self.assertEqual(booking.status, S.PAID)
        mock_capture.assert_called_once()

    @patch(CAPTURE)
    def test_approval_event_for_a_cancelled_booking_captures_nothing(self, mock_capture):
        booking = self.booking_for(self.client_user)
        self.open_payment(booking)
        cancel_booking(booking_id=booking.pk, user=self.client_user)
        record = process_event({"id": "EV2", "event_type": "CHECKOUT.ORDER.APPROVED",
                                "resource": {"id": "ORD1"}})
        mock_capture.assert_not_called()
        self.assertIn("not captured", record.note)

    @patch(REFUND, return_value=REFUND_OK)
    def test_payment_for_cancelled_booking_is_refunded(self, mock_refund):
        booking = self.booking_for(self.client_user)
        self.open_payment(booking)
        cancel_booking(booking_id=booking.pk, user=self.client_user)   # cancelled before paying
        process_event(completed_event("EV1", "ORD1"))
        booking.refresh_from_db()
        self.assertEqual(Payment.objects.get().status, Payment.Status.REFUNDED)
        self.assertEqual(booking.status, S.REFUNDED)
        self.assertEqual(booking.refund_paise, booking.total_paise)
        mock_refund.assert_called_once()

    @patch(REFUND, return_value=REFUND_OK)
    def test_payment_after_the_slot_was_lost_is_refunded(self, mock_refund):
        first = self.booking_for(self.client_user)
        self.open_payment(first)
        self.expire_hold(first)
        second = self.booking_for(self.other_client)     # allowed: the first hold ran out
        change_status(second, S.PAID, hold_expires_at=None)

        process_event(completed_event("EV1", "ORD1"))

        first.refresh_from_db()
        second.refresh_from_db()
        self.assertEqual(first.status, S.REFUNDED)
        self.assertEqual(second.status, S.PAID)          # the other client keeps the slot
        self.assertEqual(Payment.objects.get().status, Payment.Status.REFUNDED)

    def test_expired_hold_with_a_free_slot_is_accepted(self):
        booking = self.booking_for(self.client_user)
        self.open_payment(booking)
        self.expire_hold(booking)
        process_event(completed_event("EV1", "ORD1"))
        booking.refresh_from_db()
        self.assertEqual(booking.status, S.PAID)

    @patch(REFUND)
    def test_failed_refund_is_retried_later(self, mock_refund):
        booking = self.booking_for(self.client_user)
        payment = self.open_payment(booking)
        cancel_booking(booking_id=booking.pk, user=self.client_user)

        mock_refund.side_effect = PayPalError("paypal down")
        process_event(completed_event("EV1", "ORD1"))
        payment.refresh_from_db()
        self.assertEqual(payment.status, Payment.Status.REFUND_DUE)

        mock_refund.side_effect = None
        mock_refund.return_value = REFUND_OK
        refund_unusable_payment(payment.pk)              # what the job does
        payment.refresh_from_db()
        booking.refresh_from_db()
        self.assertEqual(payment.status, Payment.Status.REFUNDED)
        self.assertEqual(booking.status, S.REFUNDED)

    def test_event_for_an_unknown_order_is_ignored_safely(self):
        record = process_event(completed_event("EV1", "NOT-OURS"))
        self.assertEqual(record.status, WebhookEvent.Status.PROCESSED)
        self.assertIn("no matching payment", record.note)

    def test_new_attempt_after_a_failed_payment_uses_a_new_request_id(self):
        booking = self.booking_for(self.client_user)
        with patch("payments.services.paypal_service.create_order") as fake:
            fake.return_value = {"id": "O1"}
            first = create_paypal_payment(user=self.client_user, booking_id=booking.pk)
            Payment.objects.filter(pk=first.pk).update(status=Payment.Status.FAILED)
            fake.return_value = {"id": "O2"}
            second = create_paypal_payment(user=self.client_user, booking_id=booking.pk)
        self.assertNotEqual(first.pk, second.pk)
        self.assertEqual(fake.call_args_list[1].args[1], 2)

    @patch(GET_ORDER)
    def test_reconciliation_finds_a_payment_we_never_heard_about(self, mock_get):
        booking = self.booking_for(self.client_user)
        payment = self.open_payment(booking)
        mock_get.return_value = capture_response()
        reconcile_open_payment(payment)
        booking.refresh_from_db()
        self.assertEqual(booking.status, S.PAID)


class WebhookEndpointTests(Base):
    URL = "/api/payments/paypal/webhook/"

    @patch("payments.views.paypal_service.verify_webhook_signature", return_value=False)
    def test_forged_event_is_rejected(self, _verify):
        booking = self.booking_for(self.client_user)
        self.open_payment(booking)
        response = APIClient().post(self.URL, completed_event("EV1", "ORD1"), format="json")
        self.assertEqual(response.status_code, 400)
        booking.refresh_from_db()
        self.assertEqual(booking.status, S.PENDING_PAYMENT)
        self.assertEqual(WebhookEvent.objects.count(), 0)

    @patch("payments.views.paypal_service.verify_webhook_signature", return_value=True)
    def test_genuine_event_is_stored_and_applied(self, _verify):
        booking = self.booking_for(self.client_user)
        self.open_payment(booking)
        response = APIClient().post(self.URL, completed_event("EV1", "ORD1"), format="json")
        self.assertEqual(response.status_code, 200)
        booking.refresh_from_db()
        self.assertEqual(booking.status, S.PAID)
        self.assertEqual(WebhookEvent.objects.count(), 1)