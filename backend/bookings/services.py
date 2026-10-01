from datetime import timedelta

from django.conf import settings
from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from vendors.models import VendorProfile
from .models import Booking

S = Booking.Status


class BookingError(Exception):
    pass


class SlotUnavailable(BookingError):
    pass


def blocking_bookings(vendor_id):
    """Bookings that currently occupy the vendor's calendar."""
    now = timezone.now()
    return Booking.objects.filter(vendor_id=vendor_id).filter(
        Q(status__in=[S.PAID, S.VENDOR_CONFIRMED, S.COMPLETED, S.PAYOUT_RELEASED])
        | Q(status=S.PENDING_PAYMENT, hold_expires_at__gt=now)
    )


def has_overlap(vendor_id, start, end):
    # Two ranges overlap when each one starts before the other ends
    return blocking_bookings(vendor_id).filter(
        start_time__lt=end, end_time__gt=start
    ).exists()


def create_booking(*, client, service, start_time, event_location, notes=""):
    now = timezone.now()

    if start_time <= now:
        raise BookingError("Start time must be in the future.")
    if not service.is_active:
        raise BookingError("This service is not available.")
    if not service.vendor.is_verified:
        raise BookingError("This vendor is not verified yet.")

    end_time = start_time + timedelta(minutes=service.duration_minutes)
    total = service.price_paise
    fee = total * settings.PLATFORM_FEE_PERCENT // 100   # integer math, no floats

    with transaction.atomic():
        # Lock the vendor's row so concurrent bookings for the same vendor
        # run one at a time. Locking the vendor (not the bookings) matters:
        # if no bookings exist yet, there would be no rows to lock.
        VendorProfile.objects.select_for_update().get(pk=service.vendor_id)

        if has_overlap(service.vendor_id, start_time, end_time):
            raise SlotUnavailable("This vendor is already booked for that time.")

        return Booking.objects.create(
            client=client,
            vendor_id=service.vendor_id,
            service=service,
            start_time=start_time,
            end_time=end_time,
            event_location=event_location,
            notes=notes,
            total_paise=total,
            platform_fee_paise=fee,
            vendor_amount_paise=total - fee,
            hold_expires_at=now + timedelta(minutes=settings.BOOKING_HOLD_MINUTES),
        )


def mark_booking_paid(booking):
    if booking.status != S.PENDING_PAYMENT:
        raise BookingError(f"Cannot pay a booking in status {booking.status}.")
    booking.status = S.PAID
    booking.hold_expires_at = None
    booking.save(update_fields=["status", "hold_expires_at", "updated_at"])