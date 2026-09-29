from rest_framework import generics, viewsets, status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import VendorProfile, Service
from .permissions import IsVendor
from .serializers import VendorProfileSerializer, ServiceSerializer


class VendorListView(generics.ListAPIView):
    """Public marketplace listing. Filters: ?city=Pune&category=FOOD_TRUCK"""
    serializer_class = VendorProfileSerializer
    permission_classes = [AllowAny]

    def get_queryset(self):
        qs = VendorProfile.objects.filter(is_verified=True).prefetch_related("services")
        city = self.request.query_params.get("city")
        category = self.request.query_params.get("category")
        if city:
            qs = qs.filter(city__iexact=city)
        if category:
            qs = qs.filter(services__category=category, services__is_active=True).distinct()
        return qs


class VendorDetailView(generics.RetrieveAPIView):
    serializer_class = VendorProfileSerializer
    permission_classes = [AllowAny]
    queryset = VendorProfile.objects.filter(is_verified=True).prefetch_related("services")


class MyVendorProfileView(APIView):
    """A logged-in vendor creates and manages their own profile."""
    permission_classes = [IsVendor]

    def get(self, request):
        profile = getattr(request.user, "vendor_profile", None)
        if not profile:
            return Response({"detail": "No profile yet."}, status=404)
        return Response(VendorProfileSerializer(profile).data)

    def post(self, request):
        if hasattr(request.user, "vendor_profile"):
            return Response({"detail": "Profile already exists."}, status=400)
        ser = VendorProfileSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        ser.save(user=request.user)
        return Response(ser.data, status=status.HTTP_201_CREATED)

    def patch(self, request):
        profile = request.user.vendor_profile
        ser = VendorProfileSerializer(profile, data=request.data, partial=True)
        ser.is_valid(raise_exception=True)
        ser.save()
        return Response(ser.data)


class MyServiceViewSet(viewsets.ModelViewSet):
    """A vendor manages only their own services."""
    serializer_class = ServiceSerializer
    permission_classes = [IsVendor]

    def get_queryset(self):
        return Service.objects.filter(vendor__user=self.request.user)

    def perform_create(self, serializer):
        serializer.save(vendor=self.request.user.vendor_profile)