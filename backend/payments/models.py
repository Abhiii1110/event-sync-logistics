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