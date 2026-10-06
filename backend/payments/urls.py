from django.urls import path
from .views import (
    PayPalCreateOrderView, PayPalCaptureView, paypal_test_page,
    VendorPayoutListView, EarningsSummaryView, DisputeView,
)

urlpatterns = [
    path("paypal/create-order/", PayPalCreateOrderView.as_view()),
    path("paypal/capture/", PayPalCaptureView.as_view()),
    path("paypal/test-page/", paypal_test_page),
    path("payouts/", VendorPayoutListView.as_view()),
    path("earnings/", EarningsSummaryView.as_view()),
    path("bookings/<int:booking_id>/dispute/", DisputeView.as_view()),
]