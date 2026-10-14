from decimal import Decimal

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
    # 1500050 minor units -> "15000.50"; PayPal wants a decimal string
    return f"{Decimal(minor_units) / 100:.2f}"


def create_order(booking, attempt=1):
    token = _access_token()
    r = requests.post(
        f"{settings.PAYPAL_BASE_URL}/v2/checkout/orders",
        headers={
            "Authorization": f"Bearer {token}",
            # Same key = same order. A NEW attempt gets a new key, so a failed order isn't reused.
            "PayPal-Request-Id": f"booking-{booking.pk}-{attempt}",
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
    return r.json()


def get_order(order_id):
    token = _access_token()
    r = requests.get(
        f"{settings.PAYPAL_BASE_URL}/v2/checkout/orders/{order_id}",
        headers={"Authorization": f"Bearer {token}"},
        timeout=15,
    )
    if r.status_code != 200:
        raise PayPalError(f"Get order failed: {r.text}")
    return r.json()


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
    if r.status_code in (200, 201):
        return r.json()
    # The browser and a webhook can race. If someone already captured it, read the result.
    if r.status_code == 422 and "ORDER_ALREADY_CAPTURED" in r.text:
        return get_order(paypal_order_id)
    raise PayPalError(f"Capture failed: {r.text}")


def refund_capture(capture_id, amount_paise, request_id):
    token = _access_token()
    r = requests.post(
        f"{settings.PAYPAL_BASE_URL}/v2/payments/captures/{capture_id}/refund",
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "PayPal-Request-Id": request_id,
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
    return r.json()


def verify_webhook_signature(headers, event):
    """Ask PayPal whether this request really came from PayPal."""
    if settings.DEBUG and not settings.PAYPAL_WEBHOOK_VERIFY:
        return True          # local experiments only; has no effect when DEBUG is False
    if not settings.PAYPAL_WEBHOOK_ID:
        raise PayPalError("PAYPAL_WEBHOOK_ID is not configured.")

    token = _access_token()
    r = requests.post(
        f"{settings.PAYPAL_BASE_URL}/v1/notifications/verify-webhook-signature",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "auth_algo": headers.get("PAYPAL-AUTH-ALGO"),
            "cert_url": headers.get("PAYPAL-CERT-URL"),
            "transmission_id": headers.get("PAYPAL-TRANSMISSION-ID"),
            "transmission_sig": headers.get("PAYPAL-TRANSMISSION-SIG"),
            "transmission_time": headers.get("PAYPAL-TRANSMISSION-TIME"),
            "webhook_id": settings.PAYPAL_WEBHOOK_ID,
            "webhook_event": event,
        },
        timeout=15,
    )
    if r.status_code != 200:
        raise PayPalError(f"Signature check failed: {r.text}")
    return r.json().get("verification_status") == "SUCCESS"