from rest_framework import serializers
from .models import VendorProfile, Service


class ServiceSerializer(serializers.ModelSerializer):
    class Meta:
        model = Service
        fields = ("id", "category", "title", "description",
                  "price_paise", "duration_minutes", "is_active")

    def validate_price_paise(self, value):
        if value < 100:
            raise serializers.ValidationError("Price must be at least ₹1.")
        return value

    def validate_duration_minutes(self, value):
        if not 30 <= value <= 1440:
            raise serializers.ValidationError("Duration must be between 30 minutes and 24 hours.")
        return value


class VendorProfileSerializer(serializers.ModelSerializer):
    services = ServiceSerializer(many=True, read_only=True)

    class Meta:
        model = VendorProfile
        fields = ("id", "business_name", "description", "city",
                  "service_radius_km", "is_verified", "services", "created_at")
        read_only_fields = ("is_verified",)  # only admins can verify