# -*- coding: utf-8 -*-
from django.contrib import admin
from import_export.admin import ExportActionMixin
# from django.contrib.flatpages.admin import FlatPageAdmin
from fsm_admin2_custom.admin import FSMTransitionCustomMixin
from .enums import ConnectionApplicationLeadStatus
from .models import ConnectionApplication, ConnectionApplicationDocuments
from django_fsm_log.admin import StateLogInline


class ConnectionApplicationDocumentsInline(admin.TabularInline):
    extra = 0
    model = ConnectionApplicationDocuments
    template = 'connection_app/admin/document-inline.html'


# class FlatPageAdmin(FlatPageAdmin):
#     fieldsets = (
#         (None, {'fields': ('url', 'title', 'content', 'sites')}),
#         (_('Advanced options'), {
#             'classes': ('collapse',),
#             'fields': (
#                 'enable_comments',
#                 'registration_required',
#                 'template_name',
#             ),
#         }),
#     )

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
    )
    search_fields = ('name',)

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

        if obj and obj.status != ConnectionApplicationLeadStatus.DRAFT:
            return self.process_fieldsets
        else:
            return self.draft_fieldsets

    def get_inlines(self, request, obj):
        if obj and obj.status != ConnectionApplicationLeadStatus.DRAFT:
            return [StateLogInline, ]
        else:
            return [ConnectionApplicationDocumentsInline,]

    def fsm_transition_view_extra_context(self, obj):
        return {'obj': obj}
