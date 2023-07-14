from django.contrib import admin

# Register your models here.
# -*- coding: utf-8 -*-
from django.contrib import admin

from .models import RetailCustomer, RetailCustomerAddress, RetailCustomerDocuments


@admin.register(RetailCustomer)
class RetailCustomerAdmin(admin.ModelAdmin):
    list_display = (
        'id',
        'created_on',
        'updated_on',
        'unit_name',
        'shop_type',
        'mobile_number',
        'whatsapp_number',
        'referral_code',
    )
    list_filter = ('created_on', 'updated_on')


@admin.register(RetailCustomerAddress)
class RetailCustomerAddressAdmin(admin.ModelAdmin):
    list_display = (
        'id',
        'parent',
        'created_on',
        'updated_on',
        'title',
        'floor',
        'street_no',
        'landmark',
        'locality',
        'city',
        'pincode',
    )
    list_filter = ('parent', 'created_on', 'updated_on')


@admin.register(RetailCustomerDocuments)
class RetailCustomerDocumentsAdmin(admin.ModelAdmin):
    list_display = ('id', 'parent', 'type', 'link')
    list_filter = ('parent',)
