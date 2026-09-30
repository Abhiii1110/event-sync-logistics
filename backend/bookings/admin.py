from django.contrib import admin
from .models import Booking


@admin.register(Booking)
class BookingAdmin(admin.ModelAdmin):
    list_display = ("id", "client", "vendor", "service", "start_time", "end_time", "status", "total_paise")
    list_filter = ("status",)