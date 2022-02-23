# -*- coding: utf-8 -*-
from django.contrib import admin

from .models import InactiveCustomer
from import_export.admin import ImportMixin


@admin.register(InactiveCustomer)
class InactiveCustomerAdmin(ImportMixin, admin.ModelAdmin):
    list_display = (
        'id',
        'distributor_code',
        'consumer_id',
        'consumer_number',
        'consumer_name'
    )
    search_fields = ('consumer_name', 'consumer_number', 'consumer_id',)
