from django.conf import settings
from django.db import models


class VendorProfile(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="vendor_profile"
    )
    business_name = models.CharField(max_length=150)
    description = models.TextField(blank=True)
    city = models.CharField(max_length=80)
    service_radius_km = models.PositiveIntegerField(default=25)
    is_verified = models.BooleanField(default=False)
    razorpay_linked_account_id = models.CharField(max_length=64, blank=True)  # for Route, later
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.business_name


class Service(models.Model):
    class Category(models.TextChoices):
        FOOD_TRUCK = "FOOD_TRUCK", "Food Truck"
        AV_CREW = "AV_CREW", "AV Setup Crew"
        SECURITY = "SECURITY", "Security Team"
        DECOR = "DECOR", "Decor"

    vendor = models.ForeignKey(VendorProfile, on_delete=models.CASCADE, related_name="services")
    category = models.CharField(max_length=20, choices=Category.choices)
    title = models.CharField(max_length=150)
    description = models.TextField(blank=True)
    price_paise = models.PositiveBigIntegerField()   # money as integer paise, never floats
    duration_minutes = models.PositiveIntegerField(default=240)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.title} ({self.vendor})"