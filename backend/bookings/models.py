from django.conf import settings
from django.db import models


class Booking(models.Model):
    class Status(models.TextChoices):
        PENDING_PAYMENT = "PENDING_PAYMENT", "Pending payment"
        PAID = "PAID", "Paid"
        VENDOR_CONFIRMED = "VENDOR_CONFIRMED", "Vendor confirmed"
        COMPLETED = "COMPLETED", "Completed"
        PAYOUT_RELEASED = "PAYOUT_RELEASED", "Payout released"
        CANCELLED = "CANCELLED", "Cancelled"
        REFUNDED = "REFUNDED", "Refunded"

    client = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="bookings"
    )
    vendor = models.ForeignKey(
        "vendors.VendorProfile", on_delete=models.PROTECT, related_name="bookings"
    )
    service = models.ForeignKey(
        "vendors.Service", on_delete=models.PROTECT, related_name="bookings"
    )

    start_time = models.DateTimeField()
    end_time = models.DateTimeField()
    event_location = models.CharField(max_length=255)
    notes = models.TextField(blank=True)

    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.PENDING_PAYMENT
    )

    # Money in paise, computed on the server
    total_paise = models.PositiveBigIntegerField()
    platform_fee_paise = models.PositiveBigIntegerField()
    vendor_amount_paise = models.PositiveBigIntegerField()

    # An unpaid booking holds the slot only until this time
    hold_expires_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["vendor", "start_time", "end_time"])]

    def __str__(self):
        return f"Booking #{self.pk} ({self.status})"