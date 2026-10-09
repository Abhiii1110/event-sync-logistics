from datetime import timedelta

from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from accounts.models import User
from vendors.models import Service, VendorProfile

from .services import create_booking


class BookingDetailApiTests(TestCase):
    def setUp(self):
        self.client_user = User.objects.create_user("c1", "c1@t.com", "Test@12345", role="CLIENT")
        self.stranger = User.objects.create_user("c2", "c2@t.com", "Test@12345", role="CLIENT")
        self.vendor_user = User.objects.create_user("v1", "v1@t.com", "Test@12345", role="VENDOR")
        vendor = VendorProfile.objects.create(
            user=self.vendor_user, business_name="Spice Wheels", city="Pune", is_verified=True)
        service = Service.objects.create(
            vendor=vendor, category="FOOD_TRUCK", title="Package",
            price_paise=1500000, duration_minutes=240)
        self.booking = create_booking(
            client=self.client_user, service=service,
            start_time=timezone.now() + timedelta(days=5), event_location="Pune")

    def get(self, user):
        api = APIClient()
        api.force_authenticate(user)
        return api.get(f"/api/bookings/{self.booking.pk}/")

    def test_client_sees_booking_with_server_side_timer(self):
        response = self.get(self.client_user)
        self.assertEqual(response.status_code, 200)
        self.assertGreater(response.data["hold_seconds_left"], 0)
        self.assertIsNone(response.data["payout_status"])

    def test_vendor_sees_booking(self):
        self.assertEqual(self.get(self.vendor_user).status_code, 200)

    def test_stranger_gets_404(self):
        self.assertEqual(self.get(self.stranger).status_code, 404)