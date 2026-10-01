from django.contrib import admin
from .models import Payment


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ("id", "booking", "provider", "provider_order_id", "amount_paise", "status", "created_at")
    list_filter = ("provider", "status")