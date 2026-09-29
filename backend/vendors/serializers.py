from rest_framework import serializers
from .models import VendorProfile, Service


class ServiceSerializer(serializers.ModelSerializer):
    class Meta:
        model = Service
        fields = ("id", "category", "title", "description",
                  "price_paise", "duration_minutes", "is_active")


class VendorProfileSerializer(serializers.ModelSerializer):
    services = ServiceSerializer(many=True, read_only=True)

    class Meta:
        model = VendorProfile
        fields = ("id", "business_name", "description", "city",
                  "service_radius_km", "is_verified", "services", "created_at")
        read_only_fields = ("is_verified",)  # only admins can verify