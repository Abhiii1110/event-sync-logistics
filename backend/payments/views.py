import logging

from django.conf import settings
from django.http import Http404
from django.shortcuts import render
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .paypal_service import PayPalError
from .serializers import CaptureSerializer, CreateOrderSerializer
from .services import (
    PaymentError, PaymentNotFound, capture_paypal_payment, create_paypal_payment,
)

logger = logging.getLogger(__name__)


def _error(exc):
    code = 404 if isinstance(exc, PaymentNotFound) else 400
    return Response({"detail": str(exc)}, status=code)


class PayPalCreateOrderView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        if request.user.role != "CLIENT":
            return Response({"detail": "Only clients can pay for bookings."}, status=403)

        ser = CreateOrderSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        try:
            payment = create_paypal_payment(
                user=request.user, booking_id=ser.validated_data["booking_id"]
            )
        except PaymentError as e:
            return _error(e)
        except PayPalError:
            logger.exception("PayPal create-order failed")
            return Response({"detail": "Payment provider error. Please try again."}, status=502)

        return Response({
            "paypal_order_id": payment.provider_order_id,
            "booking_id": payment.booking_id,
            "amount_paise": payment.amount_paise,
            "currency": payment.currency,
        }, status=201)


class PayPalCaptureView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        ser = CaptureSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        try:
            payment = capture_paypal_payment(
                user=request.user, paypal_order_id=ser.validated_data["paypal_order_id"]
            )
        except PaymentError as e:
            return _error(e)
        except PayPalError:
            logger.exception("PayPal capture failed")
            return Response({"detail": "Payment provider error. Please try again."}, status=502)

        return Response({
            "payment_status": payment.status,
            "booking_id": payment.booking_id,
            "booking_status": payment.booking.status,
        })


def paypal_test_page(request):
    """Development-only page to test the PayPal popup before React exists."""
    if not settings.DEBUG:
        raise Http404
    return render(request, "payments/paypal_test.html", {
        "client_id": settings.PAYPAL_CLIENT_ID,
        "currency": settings.PAYPAL_CURRENCY,
    })