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


import threading

from django.db import connection
from django.test import TransactionTestCase

from .models import Booking


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