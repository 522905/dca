# -*- coding: utf-8 -*-
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
