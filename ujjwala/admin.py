import datetime
from datetime import datetime
from functools import update_wrapper

from django.conf.urls import url
from django.contrib import admin
from django.contrib.admin import SimpleListFilter
from django.db.models import F
from django.urls import reverse
from django.utils.safestring import mark_safe
from django_admin_listfilter_dropdown.filters import DropdownFilter
from django_fsm_log.admin import StateLogInline
from django_fsm_log.models import StateLog
from import_export import resources
from import_export.admin import ExportActionMixin, ImportMixin
from rangefilter.filters import DateRangeFilter

from fsm_admin2_custom.admin import FSMTransitionCustomMixin
from ujjwala.admin_forms import DisbursementDriveAdminForm
from .enums import PreInspectionStatusEnum, ConnectionDisbursementStatusEnum, DisbursementDriveStatusEnum
from .models import UjjwalaV2Application, FamilyMembers, UjjwalaApplicationDocuments, UjjwalaV2ApplicationStatus, \
    UserDocuments, PreInspectionDocuments, PreInspection, ConnectionDisbursementDocuments, ConnectionDisbursement, \
    ConnectionDisbursementInvitation, DisbursementDrive
from .ujjwala_functions import download_ujjwala_documents, download_ujjwala_physical_legal_docs, \
    re_create_legal_docs_pdf
from .views import SendInvitationView


def filter_walk_in_qs(queryset, state):
    queryset = queryset.order_by('walk_in_date')
    today = datetime.today()
    if state == 'WALK_IN_TODAY':
        return queryset.filter(walk_in_date__date=today.date())
    elif state == 'WALK_IN_NO_SV':
        return queryset.filter(walk_in_date__date=today.date()).\
            filter(invitation__sv_link__isnull=True).distinct()
    elif state == 'WALK_IN_SV_DONE':
        return queryset.filter(walk_in_date__date=today.date()).\
            filter(invitation__sv_link__isnull=False)
    elif state == 'WALK_IN_NO_DISBURSEMENT':
        return queryset.filter(walk_in_date__date=today.date()).\
            exclude(
                status=ConnectionDisbursementStatusEnum.MATERIAL_DELIVERED
            )


class WalkInFilter(SimpleListFilter):
    title = 'Walk In Filters'
    parameter_name = 'walk_in'

    def lookups(self, request, model_admin):
        return [
            ('WALK_IN_TODAY', 'Walk In Today'),
            ('WALK_IN_NO_SV', 'Walk In No Sv'),
            ('WALK_IN_SV_DONE', 'Walk In Sv Done'),
            ('WALK_IN_NO_DISBURSEMENT', 'Walk In No Disbursement'),
        ]

    def queryset(self, request, queryset):
        return filter_walk_in_qs(queryset, self.value())


class DisbursementDriveFilter(SimpleListFilter):
    title = 'Disbursement Drive Filter'
    parameter_name = 'disbursement'

    def lookups(self, request, model_admin):
        return [
            (i.id, f'{i.manager} ({i.id})') for i in
            DisbursementDrive.objects.filter(status=DisbursementDriveStatusEnum.ACTIVE)
        ]

    def queryset(self, request, queryset):
        if self.value():
            return queryset.filter(disbursement_drive_id=self.value())
        return queryset


class DisbursementDriveIdInputFilter(admin.SimpleListFilter):
    title = 'Disbursement Id'
    parameter_name = 'disbursement_drive_id'
    template = 'ujjwala/extra/admin_input_filter.html'

    def lookups(self, request, model_admin):
        return (
            (None, None),
        )

    def choices(self, changelist):
        query_params = changelist.get_filters_params()
        query_params.pop(self.parameter_name, None)
        all_choice = next(super().choices(changelist))
        all_choice['query_params'] = query_params
        yield all_choice

    def queryset(self, request, queryset):
        if self.value():
            return queryset.filter(disbursement_drive_id=self.value())
        return queryset


class UjjwalaApplicationDocumentsInline(admin.TabularInline):
    extra = 0
    model = UjjwalaApplicationDocuments
    fields = ('type', 'download_links', 'file_size')
    readonly_fields = ('download_links',)
# template = 'connection_app/admin/document-inline.html'


class FamilyMembersInline(admin.TabularInline):
    extra = 0
    model = FamilyMembers
    fields = ('name', 'relation', 'dob', 'uid_no', 'download_links',
              'uid_check_result', 'uid_front_file_size', 'uid_back_file_size',)
    readonly_fields = ('download_links', 'uid_check_result', 'uid_front_file_size', 'uid_back_file_size',)


class UjjwalaV2ApplicationResource(resources.ModelResource):

    class Meta:
        model = UjjwalaV2Application
        fields = ('id', 'service_area',)


@admin.register(UjjwalaV2Application)
class UjjwalaV2Admin(ImportMixin, ExportActionMixin, FSMTransitionCustomMixin, admin.ModelAdmin):
    fsm_transition_form_template = 'ujjwala/transaction_form_template.html'
    list_display = (
        'id',
        'name',
        'address',
        'address_json',
        'contact_mobile',
        'referral_code',
        'robo_sdms_dedup',
        'ekyc_cleared',
        'status',
        'consumer_id',
        'filled_by'
    )

    search_fields = ('id', 'name', 'referral_code', 'contact_mobile', 'consumer_id',)
    ordering = ('id',)

    list_filter = (
        ('created_on', DateRangeFilter),
        ('updated_on', DateRangeFilter),
        ('status', DropdownFilter),
        ('version', DropdownFilter),
        ('robo_sdms_dedup', DropdownFilter)
    )

    advanced_filter_fields = (
        'created_on',
        'updated_on',
        'status',
        'version',
        'robo_sdms_dedup',
        'id',
        'consumer_id',
        'referral_code',
        'name'
    )

    inlines = [
        FamilyMembersInline, UjjwalaApplicationDocumentsInline, StateLogInline
    ]
    fsm_fields = ['status', ]

    resource_class = UjjwalaV2ApplicationResource

    # autocomplete_fields = ('service_area',)

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if request.user.pk not in (97,):
            return qs
        return qs.filter(status='GIFT')

    def has_change_permission(self, request, obj=None):
        if not obj:
            return True
        return obj.status in (
            UjjwalaV2ApplicationStatus.EDIT_APPLICATION,
            UjjwalaV2ApplicationStatus.AUDIT_APPLICATION
        )

    def get_fields(self, request, obj=None):
        # fields = super().get_fields(request, obj)
        # return fields
        if obj and obj.status in (
                UjjwalaV2ApplicationStatus.EDIT_APPLICATION,
                UjjwalaV2ApplicationStatus.AUDIT_APPLICATION
        ):
            return [
                'marital_status',
                'residential_status',
                'name',
                'address_json',
                'contact_mobile',
                'uid_linked_mobile',
                'uid_mobile_status',
                'fsm_display_status',
                'referral_code',
                'audit_points',
            ]
        else:
            fields = super().get_fields(request, obj)
            fields = fields + ['connection_disbursement', 'pre_inspection', ]
            return fields

    def get_readonly_fields(self, request, obj=None):
        readonly_fields = super().get_readonly_fields(request, obj)

        if obj and obj.status in (
            UjjwalaV2ApplicationStatus.EKYC_ACCEPTED,
            UjjwalaV2ApplicationStatus.DO_MANUAL_OPERATION,
            UjjwalaV2ApplicationStatus.MANUAL_LEGAL_DOCUMENTS_UPLOAD
        ):
            readonly_fields = readonly_fields + ['download_legal_docs']
        elif obj and obj.status in (
            UjjwalaV2ApplicationStatus.NIC_ERROR_INSUFFICIENT_ADDRESS
        ):
            readonly_fields = readonly_fields + [
                'whatsapp_nic_error_update_address'
            ]
        elif obj and obj.status in (
            UjjwalaV2ApplicationStatus.AUDIT_APPLICATION
        ):
            readonly_fields = readonly_fields + [
                'audit_points'
            ]
        readonly_fields = readonly_fields + [
            'set_primary_phone_number', 'whatsapp_pre_inspection_type_self',
            'whatsapp_form_a_b_c', 'whatsapp_update_bank_details', 'reset_robo_execution_failed_count',
        ]
        return readonly_fields

    def download_legal_docs(self, obj=None):
        url = reverse('ujjwala:ujjwalav2application-download-ujjwala-legal-docs', kwargs={'pk': obj.id})
        return mark_safe("""
            <a href="{}" target="_blank">Download Legal Docs To Upload In SDMS</a>
        """.format(url))

    def download_legal_documents_pdf(self, obj):
        return download_ujjwala_documents(obj)

    def change_view(self, request, object_id, form_url='', extra_context=None):
        if "_download-legal-doc-pdf" in request.POST:
            obj = UjjwalaV2Application.objects.get(pk=object_id)
            return self.download_legal_documents_pdf(obj)
        return super().change_view(request, object_id, form_url=form_url, extra_context=extra_context)

    def fsm_transition_view_extra_context(self, obj):
        return {'obj': obj}

    def get_form_kwargs(self, form, *args, **kwargs):
        if form.__name__ == 'ReviewNicErrorUpdatedAddressForm':
            obj = args[0]
            return {
                'initial': obj.address_json
            }
        return super().get_form_kwargs(form, *args, **kwargs)


@admin.register(UserDocuments)
class UserDocumentsAdmin(admin.ModelAdmin):
    list_display = ('id', 'parent', 'type', 'link',)
    list_filter = ('parent',)


class PreInspectionDocumentsAdmin(admin.TabularInline):
    fields = (
        'type',
        'download_links',
        'compressed',
        'file_size',
    )
    model = PreInspectionDocuments
    extra = 0

    readonly_fields = ('type', 'download_links', 'compressed', 'file_size',)


@admin.register(PreInspection)
class PreInspectionAdmin(ExportActionMixin, FSMTransitionCustomMixin, admin.ModelAdmin):
    list_display = (
        'id',
        'parent',
        'witness_mobile_number',
        'type',
        'mechanic_name',
        'submitted_on',
        'status',
    )
    list_filter = ('mechanic', 'status', 'submitted_on', 'type')
    inlines = (PreInspectionDocumentsAdmin, StateLogInline,)
    fsm_fields = ['status', ]
    search_fields = ('id', 'parent__id', 'parent__consumer_id')

    def get_readonly_fields(self, request, obj=None):
        readonly_fields = super().get_readonly_fields(request, obj=obj)
        if obj:
            if obj.status == PreInspectionStatusEnum.ACCEPTED:
                readonly_fields = readonly_fields + ['download_physical_legal_docs', 'recreate_physical_legal_docs', ]

        return readonly_fields

    def has_change_permission(self, request, obj=None):
        if not obj:
            return True

    def download_physical_legal_docs(self, obj=None):
        return mark_safe("""
            <input type="submit" value="Download Physical Legal Docs" name="_download-physical-legal-doc-pdf">
        """)

    def recreate_physical_legal_docs(self, obj=None):
        return mark_safe("""
            <input type="submit" value="Recreate Physical Legal Docs" name="_recreate-physical-legal-doc-pdf">
        """)

    def recreate_legal_docs_pdf(self, obj):
        return re_create_legal_docs_pdf(obj)

    def download_physical_legal_documents_pdf(self, obj):
        return download_ujjwala_physical_legal_docs(obj)

    def change_view(self, request, object_id, form_url='', extra_context=None):
        if "_download-physical-legal-doc-pdf" in request.POST:
            pre_inspection_obj = PreInspection.objects.get(pk=object_id)
            return self.download_physical_legal_documents_pdf(pre_inspection_obj.parent)
        elif "_recreate-physical-legal-doc-pdf" in request.POST:
            pre_inspection_obj = PreInspection.objects.get(pk=object_id)
            return self.recreate_legal_docs_pdf(pre_inspection_obj.parent)
        return super().change_view(request, object_id, form_url=form_url, extra_context=extra_context)

    def fsm_transition_view_extra_context(self, obj):
        return {'obj': obj}


class ConnectionDisbursementDocumentsAdmin(admin.TabularInline):
    fields = (
        'type',
        'download_links',
        'compressed',
        'file_size',
    )
    model = ConnectionDisbursementDocuments
    extra = 0

    readonly_fields = ('type', 'download_links', 'compressed', 'file_size', )


class ConnectionDisbursementInvitationAdmin(admin.TabularInline):
    fields = (
        'parent',
        'invited_for',
        'invite_accepted',
        'sv_link',
        'sv_uploaded_on',
        'booking_id',
        'status'
    )
    model = ConnectionDisbursementInvitation
    extra = 0


@admin.register(ConnectionDisbursement)
class ConnectionDisbursementAdmin(ExportActionMixin, FSMTransitionCustomMixin, admin.ModelAdmin):
    list_display = (
        'id',
        'parent',
        'created_on',
        'updated_on',
        'status',
    )
    list_filter = ('status', WalkInFilter, DisbursementDriveFilter, DisbursementDriveIdInputFilter,)
    inlines = (ConnectionDisbursementDocumentsAdmin, ConnectionDisbursementInvitationAdmin, StateLogInline,)
    fsm_fields = ['status', ]
    readonly_fields = ['legal_document_upload_link', 'invite', 'whatsapp_form_a_b_c', ]
    search_fields = ('id', 'parent__id', 'parent__consumer_id',)

    def has_change_permission(self, request, obj=None):
        if not obj:
            return True

    def get_urls(self):
        urls = super().get_urls()
        info = self.model._meta.app_label, self.model._meta.model_name

        def wrap(view):
            def wrapper(*args, **kwargs):
                return self.admin_site.admin_view(view)(*args, **kwargs)

            wrapper.model_admin = self
            return update_wrapper(wrapper, view)

        my_urls = [
            url('(?P<pk>[^/.]+)/invite/', wrap(SendInvitationView.as_view()), name='%s_%s_invite' % info),
        ]
        return my_urls + urls


@admin.register(StateLog)
class StateLogAdmin(ExportActionMixin, admin.ModelAdmin):
    def has_add_permission(self, request, obj=None):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    fields = (
        'transition',
        'source_state',
        'state',
        'by',
        'description',
        'timestamp',
    )
    list_display = (
        'transition',
        'source_state',
        'state',
        'by',
        'description',
        'timestamp',
    )
    list_filter = (
        'transition',
        'by',
        'timestamp',
    )

    def get_readonly_fields(self, request, obj=None):
        return self.fields

    def get_queryset(self, request):
        return super().get_queryset(
            request
        ).order_by(F('timestamp').desc())


@admin.register(DisbursementDrive)
class DisbursementDriveAdmin(ExportActionMixin, FSMTransitionCustomMixin, admin.ModelAdmin):
    form = DisbursementDriveAdminForm
    list_display = (
        'id',
        'date',
        'manager',
        'updated_on',
        'status',
    )
    list_filter = ('status', 'date')
    filter_horizontal = ['team_members']
    fsm_fields = ['status', ]
    inlines = [StateLogInline, ]
