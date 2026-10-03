from django.urls import path
from .views import (
    BookingListCreateView, VendorBusyView, ConfirmBookingView, DeclineBookingView,
    CompleteBookingView, CancelBookingView, CancelPreviewView,
)

urlpatterns = [
    path("", BookingListCreateView.as_view()),
    path("vendors/<int:vendor_id>/busy/", VendorBusyView.as_view()),
    path("<int:pk>/confirm/", ConfirmBookingView.as_view()),
    path("<int:pk>/decline/", DeclineBookingView.as_view()),
    path("<int:pk>/complete/", CompleteBookingView.as_view()),
    path("<int:pk>/cancel/", CancelBookingView.as_view()),
    path("<int:pk>/cancel-preview/", CancelPreviewView.as_view()),
]