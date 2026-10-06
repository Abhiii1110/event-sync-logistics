import logging

from django.conf import settings
from django.db.models import Q, Sum
from django.http import Http404
from django.shortcuts import render
from rest_framework import generics
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from bookings.models import Booking
from vendors.permissions import IsVendor

from .models import Payout
from .paypal_service import PayPalError
from .payouts import PayoutError, PayoutNotFound, raise_dispute
from .serializers import (
    CaptureSerializer, CreateOrderSerializer, DisputeSerializer, PayoutSerializer,
)
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

class VendorPayoutListView(generics.ListAPIView):
    """A vendor's payout history. Filter with ?status=PENDING"""
    permission_classes = [IsVendor]
    serializer_class = PayoutSerializer

    def get_queryset(self):
        qs = Payout.objects.filter(vendor__user=self.request.user)
        status_filter = self.request.query_params.get("status")
        if status_filter:
            qs = qs.filter(status=status_filter)
        return qs


class EarningsSummaryView(APIView):
    permission_classes = [IsVendor]

    def get(self, request):
        P = Payout.Status
        totals = Payout.objects.filter(vendor__user=request.user).aggregate(
            released=Sum("amount_paise", filter=Q(status=P.RELEASED)),
            pending=Sum("amount_paise", filter=Q(status__in=[P.PENDING, P.PROCESSING])),
            disputed=Sum("amount_paise", filter=Q(status=P.DISPUTED)),
            failed=Sum("amount_paise", filter=Q(status=P.FAILED)),
        )
        expected = Booking.objects.filter(
            vendor__user=request.user,
            status__in=[Booking.Status.PAID, Booking.Status.VENDOR_CONFIRMED],
        ).aggregate(total=Sum("vendor_amount_paise"))["total"]

        return Response({
            "released_paise": totals["released"] or 0,
            "pending_paise": totals["pending"] or 0,
            "disputed_paise": totals["disputed"] or 0,
            "failed_paise": totals["failed"] or 0,
            "expected_paise": expected or 0,     # upcoming bookings, not yet completed
        })


class DisputeView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, booking_id):
        ser = DisputeSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        try:
            payout = raise_dispute(
                booking_id=booking_id, user=request.user,
                reason=ser.validated_data["reason"])
        except PayoutNotFound as e:
            return Response({"detail": str(e)}, status=404)
        except PayoutError as e:
            return Response({"detail": str(e)}, status=409)
        return Response(PayoutSerializer(payout).data)