from django.contrib import admin
from .models import Appointment

@admin.register(Appointment)
class AppointmentAdmin(admin.ModelAdmin):
    list_display = ['user', 'service', 'date', 'time', 'status', 'created_at']
    list_filter = ['status', 'date']
    search_fields = ['user__username', 'service__name', 'notes']
    list_editable = ['status']
    date_hierarchy = 'date'
