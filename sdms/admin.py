# -*- coding: utf-8 -*-
from django.contrib import admin
from import_export.admin import ImportMixin

from .models import SdmsCustomerRecord, BookResource


@admin.register(SdmsCustomerRecord)
class SdmsCustomerRecordAdmin(ImportMixin, admin.ModelAdmin):
    resource_class = BookResource
    list_display = (
        'consumer_id',
        'kyc_date',
        'waitlist_status',
        'nic_status',
        'omc_status',
        'name',
        'address',
    )
    list_filter = ('kyc_date',)
    search_fields = ('name',)
