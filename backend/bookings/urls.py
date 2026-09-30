from django.urls import path
from .views import BookingListCreateView, VendorBusyView

urlpatterns = [
    path("", BookingListCreateView.as_view()),
    path("vendors/<int:vendor_id>/busy/", VendorBusyView.as_view()),
]