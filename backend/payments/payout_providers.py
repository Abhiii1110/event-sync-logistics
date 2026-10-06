class PayoutProviderError(Exception):
    pass


class MockPayoutProvider:
    """Stands in for a real payout API. A real provider (Razorpay Route, a bank
    payout API) would implement the same send() method and use
    f"payout-{payout.pk}" as its idempotency key, so a retry can never pay twice."""

    name = "mock"

    def send(self, payout):
        return f"MOCK-{payout.pk}"      # the same payout always gets the same reference


_PROVIDERS = {"mock": MockPayoutProvider()}


def get_provider(name):
    try:
        return _PROVIDERS[name]
    except KeyError:
        raise PayoutProviderError(f"Unknown payout provider: {name}")