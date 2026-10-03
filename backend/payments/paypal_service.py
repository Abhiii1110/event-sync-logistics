import uuid
import requests
from django.conf import settings


class PayPalError(Exception):
    pass


def _access_token():
    r = requests.post(
        f"{settings.PAYPAL_BASE_URL}/v1/oauth2/token",
        auth=(settings.PAYPAL_CLIENT_ID, settings.PAYPAL_CLIENT_SECRET),
        data={"grant_type": "client_credentials"},
        timeout=15,
    )
    if r.status_code != 200:
        raise PayPalError(f"Auth failed: {r.text}")
    return r.json()["access_token"]


def _money(minor_units):
    # 1500000 minor units -> "15000.00"; PayPal wants a decimal string
    return f"{minor_units / 100:.2f}"


def create_order(booking):
    token = _access_token()
    r = requests.post(
        f"{settings.PAYPAL_BASE_URL}/v2/checkout/orders",
        headers={
            "Authorization": f"Bearer {token}",
            "PayPal-Request-Id": f"booking-{booking.pk}",  # idempotency key
        },
        json={
            "intent": "CAPTURE",
            "purchase_units": [{
                "reference_id": str(booking.pk),
                "custom_id": str(booking.pk),
                "amount": {
                    "currency_code": settings.PAYPAL_CURRENCY,
                    "value": _money(booking.total_paise),
                },
            }],
        },
        timeout=15,
    )
    if r.status_code not in (200, 201):
        raise PayPalError(f"Create order failed: {r.text}")
    return r.json()          # contains "id"


def capture_order(paypal_order_id):
    token = _access_token()
    r = requests.post(
        f"{settings.PAYPAL_BASE_URL}/v2/checkout/orders/{paypal_order_id}/capture",
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "PayPal-Request-Id": f"capture-{paypal_order_id}",
        },
        timeout=15,
    )
    if r.status_code not in (200, 201):
        raise PayPalError(f"Capture failed: {r.text}")
    return r.json()          # check ["status"] == "COMPLETED"

def refund_capture(capture_id, amount_paise, request_id):
    token = _access_token()
    r = requests.post(
        f"{settings.PAYPAL_BASE_URL}/v2/payments/captures/{capture_id}/refund",
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "PayPal-Request-Id": request_id,   # same id on retry = no double refund
        },
        json={
            "amount": {
                "currency_code": settings.PAYPAL_CURRENCY,
                "value": _money(amount_paise),
            },
            "note_to_payer": "Booking cancelled",
        },
        timeout=15,
    )
    if r.status_code not in (200, 201):
        raise PayPalError(f"Refund failed: {r.text}")
    return r.json()          # contains "id" and "status"

