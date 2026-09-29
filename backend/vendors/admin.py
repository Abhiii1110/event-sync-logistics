from django.contrib import admin
from .models import VendorProfile, Service


@admin.register(VendorProfile)
class VendorProfileAdmin(admin.ModelAdmin):
    list_display = ("id", "business_name", "user", "city", "is_verified", "created_at")
    search_fields = ("business_name", "city", "user__username")
    list_filter = ("city", "is_verified")


@admin.register(Service)
class ServiceAdmin(admin.ModelAdmin):
    list_display = ("id", "title", "vendor", "category", "price_paise", "is_active")
    search_fields = ("title", "vendor__business_name")
    list_filter = ("category", "is_active")