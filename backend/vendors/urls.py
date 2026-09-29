from django.urls import path
from rest_framework.routers import DefaultRouter
from .views import VendorListView, VendorDetailView, MyVendorProfileView, MyServiceViewSet

router = DefaultRouter()
router.register("me/services", MyServiceViewSet, basename="my-services")

urlpatterns = [
    path("", VendorListView.as_view()),
    path("<int:pk>/", VendorDetailView.as_view()),
    path("me/profile/", MyVendorProfileView.as_view()),
] + router.urls