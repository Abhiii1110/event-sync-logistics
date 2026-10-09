from rest_framework import serializers
from vendors.models import Service
from .models import Booking
from django.utils import timezone

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
    client_name = serializers.CharField(source="client.username", read_only=True)
    refund_status = serializers.SerializerMethodField()
    hold_seconds_left = serializers.SerializerMethodField()
    payout_status = serializers.SerializerMethodField()
    payout_release_at = serializers.SerializerMethodField()

    class Meta:
        model = Booking
        fields = (
            "id", "service", "service_title", "vendor", "vendor_name", "client_name",
            "start_time", "end_time", "event_location", "notes", "status",
            "total_paise", "platform_fee_paise", "vendor_amount_paise",
            "hold_expires_at", "hold_seconds_left", "created_at",
            "vendor_confirmed_at", "completed_at", "cancelled_at",
            "cancelled_by", "cancel_reason", "refund_paise", "refund_status",
            "payout_status", "payout_release_at",
        )

    def get_refund_status(self, obj):
        if obj.refund_paise == 0:
            return "NONE"
        return "DONE" if obj.status == Booking.Status.REFUNDED else "PENDING"

    def get_hold_seconds_left(self, obj):
        if obj.status != Booking.Status.PENDING_PAYMENT or not obj.hold_expires_at:
            return None
        return max(0, int((obj.hold_expires_at - timezone.now()).total_seconds()))

    def get_payout_status(self, obj):
        payout = getattr(obj, "payout", None)      # None when no payout exists yet
        return payout.status if payout else None

    def get_payout_release_at(self, obj):
        payout = getattr(obj, "payout", None)
        return payout.release_at if payout else None

class ReasonSerializer(serializers.Serializer):
    reason = serializers.CharField(required=False, allow_blank=True, max_length=255)