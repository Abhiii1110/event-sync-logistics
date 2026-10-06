from django.contrib import admin
from django.utils import timezone

from .models import Payment ,Payout


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ("id", "booking", "provider", "provider_order_id", "amount_paise", "status", "created_at")
    list_filter = ("provider", "status")

@admin.register(Payout)
class PayoutAdmin(admin.ModelAdmin):
    list_display = ("id", "booking", "vendor", "kind", "amount_paise", "status", "release_at", "attempts")
    list_filter = ("status", "kind")
    actions = ["resolve_for_vendor", "resolve_for_client", "retry_failed"]

    @admin.action(description="Resolve dispute in the VENDOR's favour (release payout)")
    def resolve_for_vendor(self, request, queryset):
        n = queryset.filter(status=Payout.Status.DISPUTED).update(
            status=Payout.Status.PENDING, release_at=timezone.now(),
            resolution_note="Resolved in vendor's favour by admin")
        self.message_user(request, f"{n} payout(s) will be released by the next job run.")

    @admin.action(description="Resolve dispute in the CLIENT's favour (cancel payout)")
    def resolve_for_client(self, request, queryset):
        n = queryset.filter(status=Payout.Status.DISPUTED).update(
            status=Payout.Status.CANCELLED,
            resolution_note="Resolved in client's favour by admin. Refund handled manually.")
        self.message_user(request, f"{n} payout(s) cancelled.")

    @admin.action(description="Retry failed payouts")
    def retry_failed(self, request, queryset):
        n = queryset.filter(status=Payout.Status.FAILED).update(
            status=Payout.Status.PENDING, attempts=0, last_error="")
        self.message_user(request, f"{n} payout(s) queued for retry.")