from django.urls import path
from .views import PayPalCreateOrderView, PayPalCaptureView, paypal_test_page

urlpatterns = [
    path("paypal/create-order/", PayPalCreateOrderView.as_view()),
    path("paypal/capture/", PayPalCaptureView.as_view()),
    path("paypal/test-page/", paypal_test_page),
]