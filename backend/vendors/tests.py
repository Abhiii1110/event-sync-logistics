from datetime import timedelta

from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from accounts.models import User
from bookings.services import create_booking

from .models import Service, VendorProfile

SERVICE = {"category": "DECOR", "title": "Stage decor", "price_paise": 500000, "duration_minutes": 120}


class VendorManagementApiTests(TestCase):
    def setUp(self):
        self.vendor_user = User.objects.create_user("v1", "v1@t.com", "Test@12345", role="VENDOR")
        self.client_user = User.objects.create_user("c1", "c1@t.com", "Test@12345", role="CLIENT")
        self.api = APIClient()
        self.api.force_authenticate(self.vendor_user)

    def make_profile(self, verified=False):
        return VendorProfile.objects.create(
            user=self.vendor_user, business_name="Spice Wheels", city="Pune", is_verified=verified)

    def test_adding_a_service_needs_a_profile_first(self):
        response = self.api.post("/api/vendors/me/services/", SERVICE, format="json")
        self.assertEqual(response.status_code, 403)
        self.assertIn("profile", response.data["detail"].lower())

    def test_vendor_creates_profile_then_service(self):
        response = self.api.post(
            "/api/vendors/me/profile/", {"business_name": "Spice Wheels", "city": "Pune"}, format="json")
        self.assertEqual(response.status_code, 201)
        self.assertFalse(response.data["is_verified"])      # an admin must approve it
        response = self.api.post("/api/vendors/me/services/", SERVICE, format="json")
        self.assertEqual(response.status_code, 201)

    def test_bad_price_and_duration_are_rejected(self):
        self.make_profile()
        for bad in ({"price_paise": 50}, {"duration_minutes": 10}, {"duration_minutes": 5000}):
            response = self.api.post("/api/vendors/me/services/", {**SERVICE, **bad}, format="json")
            self.assertEqual(response.status_code, 400, bad)

    def test_clients_cannot_manage_services(self):
        api = APIClient()
        api.force_authenticate(self.client_user)
        self.assertEqual(api.get("/api/vendors/me/services/").status_code, 403)

    def test_service_with_bookings_cannot_be_deleted(self):
        profile = self.make_profile(verified=True)
        service = Service.objects.create(vendor=profile, **SERVICE)
        create_booking(
            client=self.client_user, service=service,
            start_time=timezone.now() + timedelta(days=5), event_location="Pune")
        response = self.api.delete(f"/api/vendors/me/services/{service.pk}/")
        self.assertEqual(response.status_code, 409)
        self.assertTrue(Service.objects.filter(pk=service.pk).exists())