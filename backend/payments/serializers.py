from rest_framework import serializers
from .models import Payout


class CreateOrderSerializer(serializers.Serializer):
    booking_id = serializers.IntegerField()


class CaptureSerializer(serializers.Serializer):
    paypal_order_id = serializers.CharField(max_length=64)



class DisputeSerializer(serializers.Serializer):
    reason = serializers.CharField(max_length=255)


class PayoutSerializer(serializers.ModelSerializer):
    class Meta:
        model = Payout
        fields = (
            "id", "booking", "kind", "amount_paise", "platform_fee_paise", "status",
            "release_at", "released_at", "provider_reference",
            "dispute_reason", "disputed_at", "resolution_note", "created_at",
        )