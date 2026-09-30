from datetime import timedelta

from django.test import TestCase
from django.utils import timezone

from accounts.models import User
from vendors.models import VendorProfile, Service
from .services import create_booking, SlotUnavailable


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