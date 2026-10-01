from rest_framework import serializers


class CreateOrderSerializer(serializers.Serializer):
    booking_id = serializers.IntegerField()


class CaptureSerializer(serializers.Serializer):
    paypal_order_id = serializers.CharField(max_length=64)