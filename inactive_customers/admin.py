# -*- coding: utf-8 -*-
from django.contrib import admin

from .models import InactiveCustomer
from import_export.admin import ImportMixin
from django.contrib.admin import SimpleListFilter
from connection_app.models import ConnectionApplication
from connection_app.enums import ConnectionApplicationLeadStatus


class StatusFilter(SimpleListFilter):
    title = 'Application Status'  # or use _('country') for translated title
    parameter_name = 'application_status'

    def lookups(self, request, model_admin):
        return [
            ('avaliable', 'Avaliable'),
        ]

    def queryset(self, request, queryset):
        state = self.value()
        if state == 'avaliable':
            return queryset.exclude(
                consumer_id__in=ConnectionApplication.objects.exclude(
                    status=ConnectionApplicationLeadStatus.NOT_INTERESTED
                ).values_list('pk')
            )
        return queryset



@admin.register(InactiveCustomer)
class InactiveCustomerAdmin(ImportMixin, admin.ModelAdmin):
    list_display = (
        'id',
        'distributor_code',
        'consumer_id',
        'consumer_name'
    )
    search_fields = ('consumer_name', 'consumer_number', 'consumer_id',)
    list_filter = (
          StatusFilter,
    )
