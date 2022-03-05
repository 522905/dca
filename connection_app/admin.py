# -*- coding: utf-8 -*-
import json
from django.contrib import admin
from import_export.admin import ExportActionMixin
# from django.contrib.flatpages.admin import FlatPageAdmin
from fsm_admin2_custom.admin import FSMTransitionCustomMixin
from .enums import ConnectionApplicationLeadStatus
from .models import ConnectionApplication, ConnectionApplicationDocuments
from django_fsm_log.admin import StateLogInline
from rangefilter.filters import DateRangeFilter, DateTimeRangeFilter
from django_admin_listfilter_dropdown.filters import DropdownFilter, RelatedDropdownFilter, ChoiceDropdownFilter
from django.contrib.admin import SimpleListFilter
from django.db import connection
from django.urls import path
from django.http import JsonResponse
from itertools import groupby


class StatusFilter(SimpleListFilter):
    title = 'Application Status'  # or use _('country') for translated title
    parameter_name = 'application_status'

    def lookups(self, request, model_admin):
        return [
            ('SP', 'Staff Pending'),
            ('E', 'End'),
            ('CP', 'Customer Pending'),
        ]

    def queryset(self, request, queryset):
        state = self.value()
        if state == 'SP':
            return queryset.exclude(status__in=(ConnectionApplicationLeadStatus.COMPLETED, ConnectionApplicationLeadStatus.NOT_INTERESTED))
        if state == 'E':
            return queryset.filter(status__in=(ConnectionApplicationLeadStatus.COMPLETED, ConnectionApplicationLeadStatus.NOT_INTERESTED))
        return queryset


def dictfetchall(cursor):
    "Return all rows from a cursor as a dict"
    columns = [col[0] for col in cursor.description]
    return [
        dict(zip(columns, row))
        for row in cursor.fetchall()
    ]


class ConnectionApplicationDocumentsInline(admin.TabularInline):
    extra = 0
    model = ConnectionApplicationDocuments
    template = 'connection_app/admin/document-inline.html'

@admin.register(ConnectionApplication)
class ConnectionApplicationAdmin(ExportActionMixin, FSMTransitionCustomMixin, admin.ModelAdmin):
    fsm_transition_form_template = 'connection_app/transaction_form_template.html'
    fsm_transition_buttons_template = 'connection_app/transition_buttons.html'

    fsm_fields = ['status', ]
    list_display = (
        'id',
        'name',
        'mobile',
        'application_type',
        'created_on',
        'updated_on',
        'required_by',
        'status',
        'referral_code',
    )

    search_fields = ('name','referral_code','mobile')
    ordering = ('id',)

    list_filter = (
          StatusFilter,
          ('created_on', DateRangeFilter),
          ('updated_on', DateRangeFilter),
          ('required_by', DateRangeFilter),
          ('status', DropdownFilter),
          ('application_type', DropdownFilter),
    )

    draft_fieldsets = [(None, {'fields': [
        'name', 'mobile', 'address', 'application_type', 'item_code',
        'connection_type', 'referral_code', 'applicant_remarks',
        'communication_mode', 'fsm_display_status'
    ]})]

    process_fieldsets = [(None, {'fields': [
            'lead_details_in_html', 'attachment_details_in_html', 'fsm_display_status'
        ]})]

    readonly_fields = ('lead_details_in_html', 'attachment_details_in_html')

    def get_fieldsets(self, request, obj=None):
        # fieldsets = super().get_fieldsets(request, obj)

        if obj and obj.status not in (
                ConnectionApplicationLeadStatus.EDIT_APPLICATION,
        ):
            return self.process_fieldsets
        else:
            return self.draft_fieldsets

    def get_inlines(self, request, obj):
        if obj and obj.status != ConnectionApplicationLeadStatus.EDIT_APPLICATION:
            return [StateLogInline, ]
        else:
            return [ConnectionApplicationDocumentsInline, ]

    def fsm_transition_view_extra_context(self, obj):
        return {'obj': obj}


    def my_custom_sql(self):
        with connection.cursor() as cursor:
            # All Status instead Completed and Not Interested
            cursor.execute("SELECT date(created_on) as created_on, status, count(*) as cnt FROM connection_app_connectionapplication where status not in ('COMPLETED', 'NOT_INTERESTED') group by date(created_on), status", [])
            rows = dictfetchall(cursor)
            
            cursor.execute("SELECT min(date(created_on)) as min_date, max(date(created_on)) as max_date FROM connection_app_connectionapplication where status not in ('COMPLETED', 'NOT_INTERESTED')", [])
            min_max = dictfetchall(cursor)
            min_max = min_max[0]
            min_max['data'] = rows
            return min_max
            
    
    def my_custom_sql_completed(self):
        with connection.cursor() as cursor:
                        
            # Completed
            cursor.execute("SELECT date(created_on) as created_on, status, count(*) as cnt FROM connection_app_connectionapplication where status in ('COMPLETED', 'NOT_INTERESTED') group by date(created_on), status", [])
            rows = dictfetchall(cursor)


            cursor.execute("SELECT min(date(created_on)) as min_date, max(date(created_on)) as max_date FROM connection_app_connectionapplication where status in ('COMPLETED', 'NOT_INTERESTED')", [])
            min_max = dictfetchall(cursor)
            min_max = min_max[0]
            min_max['data'] = rows
            return min_max


    def get_urls(self):
        urls = super().get_urls()
        extra_urls = [
            path("chart_data/", self.admin_site.admin_view(self.chart_data_endpoint)),
        ]
        # NOTE! Our custom urls have to go before the default urls, because they
        # default ones match anything.
        return extra_urls + urls

    # JSON endpoint for generating chart data that is used for dynamic loading
    # via JS.
    def chart_data_endpoint(self, request):
        data = {
            'pending': self.chart_data(),
            'completed': self.chart_data_completed()
        }
        return JsonResponse(data, safe=False)


    def chart_data(self):
        sql_data = self.my_custom_sql()
        sql_data['data'] = [{'label': status, 'data': list(values)} for status, values in groupby(sql_data['data'], lambda x: x['status'])]
        return sql_data

    def chart_data_completed(self):
        sql_data = self.my_custom_sql_completed()
        sql_data['data'] = [{'label': status, 'data': list(values)} for status, values in groupby(sql_data['data'], lambda x: x['status'])]
        return sql_data
