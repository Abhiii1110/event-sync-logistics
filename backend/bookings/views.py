from datetime import datetime, time, timedelta

from django.utils import timezone
from django.utils.dateparse import parse_date
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Booking
from .serializers import BookingCreateSerializer, BookingSerializer
from .services import BookingError, SlotUnavailable, blocking_bookings, create_booking


class BookingListCreateView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        if user.role == "VENDOR":
            qs = Booking.objects.filter(vendor__user=user)
        else:
            qs = Booking.objects.filter(client=user)
        qs = qs.select_related("service", "vendor")
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