from django.contrib import admin,messages
from django.utils import timezone

from .models import Payment ,Payout,WebhookEvent
from . webhooks import process_event


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

@admin.register(WebhookEvent)
class WebhookEventAdmin(admin.ModelAdmin):
    list_display = ("id", "event_type", "event_id", "status", "attempts", "note", "received_at")
    list_filter = ("status", "event_type")
    search_fields = ("event_id", "note")
    readonly_fields = ("provider", "event_id", "event_type", "payload", "received_at", "processed_at")
    actions = ["reprocess"]

    @admin.action(description="Reprocess selected events")
    def reprocess(self, request, queryset):
        done = 0
        for event in queryset:
            WebhookEvent.objects.filter(pk=event.pk).update(status=WebhookEvent.Status.RECEIVED)
            try:
                process_event(event.payload)
                done += 1
            except Exception as exc:
                self.message_user(request, f"{event.event_id} failed again: {exc}", level=messages.ERROR)
        self.message_user(request, f"{done} event(s) reprocessed.")