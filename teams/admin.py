from django.contrib import admin

# Register your models here.
# -*- coding: utf-8 -*-
from django.contrib import admin

from .models import ServiceLocations


@admin.register(ServiceLocations)
class ServiceLocationsAdmin(admin.ModelAdmin):
    list_display = (
        'id',
        'parent',
        'type',
        'start_working_hours',
        'end_working_hours',
        'address',
        'lat_long',
        'enabled',
    )
    list_filter = ('parent', 'enabled')
