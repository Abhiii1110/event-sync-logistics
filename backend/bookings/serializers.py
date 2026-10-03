from rest_framework import serializers
from vendors.models import Service
from .models import Booking


class BookingCreateSerializer(serializers.Serializer):
    service_id = serializers.PrimaryKeyRelatedField(
        queryset=Service.objects.select_related("vendor"), source="service"
    )
    start_time = serializers.DateTimeField()
    event_location = serializers.CharField(max_length=255)
    notes = serializers.CharField(required=False, allow_blank=True)


class BookingSerializer(serializers.ModelSerializer):
    service_title = serializers.CharField(source="service.title", read_only=True)
    vendor_name = serializers.CharField(source="vendor.business_name", read_only=True)

    class Meta:
        model = Booking
        fields = (
            "id", "service", "service_title", "vendor", "vendor_name",
            "start_time", "end_time", "event_location", "notes", "status",
            "total_paise", "platform_fee_paise", "vendor_amount_paise",
            "hold_expires_at", "created_at",
        )

    def get_refund_status(self, obj):
        if obj.refund_paise == 0:
            return "NONE"
        return "DONE" if obj.status == Booking.Status.REFUNDED else "PENDING"

class ReasonSerializer(serializers.Serializer):
    reason = serializers.CharField(required=False, allow_blank=True, max_length=255)