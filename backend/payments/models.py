from django.db import models


class Payment(models.Model):
    class Provider(models.TextChoices):
        RAZORPAY = "RAZORPAY", "Razorpay"
        PAYPAL = "PAYPAL", "PayPal"

    class Status(models.TextChoices):
        CREATED = "CREATED", "Created"
        PAID = "PAID", "Paid"
        FAILED = "FAILED", "Failed"
        REFUNDED = "REFUNDED", "Refunded"

    booking = models.ForeignKey(
        "bookings.Booking", on_delete=models.PROTECT, related_name="payments"
    )
    provider = models.CharField(max_length=10, choices=Provider.choices)
    provider_order_id = models.CharField(max_length=64)
    provider_payment_id = models.CharField(max_length=64, blank=True)
    amount_paise = models.PositiveBigIntegerField()
    currency = models.CharField(max_length=3)
    refunded_paise = models.PositiveBigIntegerField(default=0)
    refund_id = models.CharField(max_length=64, blank=True)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.CREATED)
    raw_response = models.JSONField(null=True, blank=True)   # gateway reply, useful for debugging
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["provider", "provider_order_id"], name="uniq_provider_order"
            )
        ]

    def __str__(self):
        return f"{self.provider} {self.provider_order_id} ({self.status})"

class Payout(models.Model):
    class Kind(models.TextChoices):
        COMPLETION = "COMPLETION", "Completed booking"
        CANCELLATION = "CANCELLATION", "Late-cancellation compensation"

    class Status(models.TextChoices):
        PENDING = "PENDING", "Pending"
        PROCESSING = "PROCESSING", "Processing"
        RELEASED = "RELEASED", "Released"
        FAILED = "FAILED", "Failed"
        DISPUTED = "DISPUTED", "Disputed"
        CANCELLED = "CANCELLED", "Cancelled"

    # One payout per booking: the database itself prevents paying a booking twice
    booking = models.OneToOneField(
        "bookings.Booking", on_delete=models.PROTECT, related_name="payout"
    )
    vendor = models.ForeignKey(
        "vendors.VendorProfile", on_delete=models.PROTECT, related_name="payouts"
    )
    kind = models.CharField(max_length=15, choices=Kind.choices)
    amount_paise = models.PositiveBigIntegerField()          # what the vendor receives
    platform_fee_paise = models.PositiveBigIntegerField()    # what the platform keeps
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.PENDING)
    release_at = models.DateTimeField()
    released_at = models.DateTimeField(null=True, blank=True)

    provider = models.CharField(max_length=20, default="mock")
    provider_reference = models.CharField(max_length=64, blank=True)
    attempts = models.PositiveSmallIntegerField(default=0)
    last_error = models.CharField(max_length=255, blank=True)

    dispute_reason = models.CharField(max_length=255, blank=True)
    disputed_at = models.DateTimeField(null=True, blank=True)
    resolution_note = models.CharField(max_length=255, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["status", "release_at"])]

    def __str__(self):
        return f"Payout #{self.pk} booking {self.booking_id} ({self.status})"