from datetime import datetime, time, timedelta
from .lifecycle import cancel_booking, complete_booking, confirm_booking, refund_amount, role_for

from django.utils import timezone
from django.utils.dateparse import parse_date
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Booking
from .serializers import BookingCreateSerializer, BookingSerializer , ReasonSerializer
from .services import ALLOWED_TRANSITIONS, BookingError, BookingNotFound, InvalidTransition,SlotUnavailable, blocking_bookings, create_booking

S = Booking.Status


class BookingListCreateView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        if user.role == "VENDOR":
            qs = Booking.objects.filter(vendor__user=user)
        else:
            qs = Booking.objects.filter(client=user)
        status_filter = request.query_params.get("status")
        if status_filter:
            qs = qs.filter(status=status_filter)
        qs = qs.select_related("service", "vendor", "client", "payout")
        return Response(BookingSerializer(qs, many=True).data)

    def post(self, request):
        if request.user.role != "CLIENT":
            return Response({"detail": "Only clients can create bookings."}, status=403)

        ser = BookingCreateSerializer(data=request.data)
        ser.is_valid(raise_exception=True)

        try:
            booking = create_booking(client=request.user, **ser.validated_data)
        except SlotUnavailable as e:
            return Response({"detail": str(e)}, status=409)   # 409 = conflict
        except BookingError as e:
            return Response({"detail": str(e)}, status=400)

        return Response(BookingSerializer(booking).data, status=201)


class VendorBusyView(APIView):
    """Busy windows for one day. The React calendar grid will use this."""
    permission_classes = [AllowAny]

    def get(self, request, vendor_id):
        day = parse_date(request.query_params.get("date", ""))
        if not day:
            return Response({"detail": "Use ?date=YYYY-MM-DD"}, status=400)

        day_start = timezone.make_aware(datetime.combine(day, time.min))
        day_end = day_start + timedelta(days=1)
        qs = blocking_bookings(vendor_id).filter(
            start_time__lt=day_end, end_time__gt=day_start
        )
        return Response([{"start": b.start_time, "end": b.end_time} for b in qs])

def _run(fn, **kwargs):
    try:
        booking = fn(**kwargs)
    except BookingNotFound as e:
        return Response({"detail": str(e)}, status=404)
    except InvalidTransition as e:
        return Response({"detail": str(e)}, status=409)
    except BookingError as e:
        return Response({"detail": str(e)}, status=400)
    return Response(BookingSerializer(booking).data)


def _reason(request):
    ser = ReasonSerializer(data=request.data)
    ser.is_valid(raise_exception=True)
    return ser.validated_data.get("reason", "")


class ConfirmBookingView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        if request.user.role != "VENDOR":
            return Response({"detail": "Only vendors can confirm bookings."}, status=403)
        return _run(confirm_booking, booking_id=pk, user=request.user)


class DeclineBookingView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        if request.user.role != "VENDOR":
            return Response({"detail": "Only vendors can decline bookings."}, status=403)
        return _run(cancel_booking, booking_id=pk, user=request.user,
                    reason=_reason(request) or "Declined by vendor",
                    required_status=S.PAID)


class CompleteBookingView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        if request.user.role != "VENDOR":
            return Response({"detail": "Only vendors can complete bookings."}, status=403)
        return _run(complete_booking, booking_id=pk, user=request.user)


class CancelBookingView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        return _run(cancel_booking, booking_id=pk, user=request.user,
                    reason=_reason(request))


class CancelPreviewView(APIView):
    """'If I cancel now, how much do I get back?' The React UI will show this."""
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        booking = Booking.objects.select_related("vendor").filter(pk=pk).first()
        if booking is None:
            return Response({"detail": "Booking not found."}, status=404)
        try:
            actor = role_for(booking, request.user)
        except BookingNotFound as e:
            return Response({"detail": str(e)}, status=404)

        can_cancel = (
            S.CANCELLED in ALLOWED_TRANSITIONS.get(booking.status, set())
            and booking.start_time > timezone.now()
        )
        return Response({
            "can_cancel": can_cancel,
            "total_paise": booking.total_paise,
            "refund_paise": refund_amount(booking, actor) if can_cancel else 0,
        })

class BookingDetailView(APIView):
    """One booking, visible only to its client and its vendor."""
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        booking = (
            Booking.objects.select_related("service", "vendor", "client", "payout")
            .filter(pk=pk).first()
        )
        if booking is None:
            return Response({"detail": "Booking not found."}, status=404)
        try:
            role_for(booking, request.user)
        except BookingNotFound:
            return Response({"detail": "Booking not found."}, status=404)
        return Response(BookingSerializer(booking).data)