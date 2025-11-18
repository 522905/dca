"""
Django Admin Interface for Ujjwala V3 Application

This module provides comprehensive admin interfaces for managing Ujjwala V3
applications, addresses, family members, and documents.
"""

from django.contrib import admin
from django.db.models import Count
from django.utils.html import format_html
from django.urls import reverse
from django.utils.safestring import mark_safe

from .models import (
    UjjwalaV3Application,
    UjjwalaV3Address,
    UjjwalaV3FamilyMember,
    UjjwalaV3Document,
    UjjwalaV3AuditLog
)
from .enums import ApplicationStatus, AddressType, RelationToApplicant


class UjjwalaV3AddressInline(admin.TabularInline):
    """Inline admin for addresses."""
    model = UjjwalaV3Address
    extra = 0
    fields = [
        'address_type', 'house_flat_no', 'floor_number', 'building_colony',
        'city_town', 'district', 'state', 'pincode', 'poa_code'
    ]
    readonly_fields = ['created_at', 'updated_at']


class UjjwalaV3FamilyMemberInline(admin.TabularInline):
    """Inline admin for family members."""
    model = UjjwalaV3FamilyMember
    extra = 0
    fields = [
        'full_name', 'relation_to_applicant', 'gender',
        'aadhaar_number', 'dob', 'age_at_application',
        'uid_photos_display', 'is_valid_uid', 'validated'
    ]
    readonly_fields = ['age_at_application', 'uid_photos_display', 'created_at', 'updated_at']

    def uid_photos_display(self, obj):
        """Display UID photo links."""
        if obj and obj.pk:
            return mark_safe(obj.download_links())
        return '-'
    uid_photos_display.short_description = 'UID Photos'


class UjjwalaV3DocumentInline(admin.TabularInline):
    """Inline admin for documents."""
    model = UjjwalaV3Document
    extra = 0
    fields = [
        'doc_type', 'file_name', 'file_size', 'is_verified',
        'uploaded_by', 'created_at'
    ]
    readonly_fields = ['file_size', 'uploaded_by', 'created_at']


class UjjwalaV3AuditLogInline(admin.TabularInline):
    """Inline admin for audit logs."""
    model = UjjwalaV3AuditLog
    extra = 0
    fields = ['action', 'actor', 'remarks', 'created_at']
    readonly_fields = ['action', 'actor', 'remarks', 'created_at', 'ip_address']
    can_delete = False

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(UjjwalaV3Application)
class UjjwalaV3ApplicationAdmin(admin.ModelAdmin):
    """Admin interface for Ujjwala V3 Applications."""

    list_display = [
        'application_number', 'applicant_full_name', 'applicant_mobile',
        'status_badge', 'caste', 'lpg_connection_type',
        'submitted_at', 'is_complete_badge', 'created_at'
    ]

    list_filter = [
        'status', 'caste', 'lpg_connection_type', 'is_migrant',
        'family_doc_issuing_state', 'aadhaar_verification_status',
        'bank_verification_status', 'address_verification_status',
        ('created_at', admin.DateFieldListFilter),
        ('submitted_at', admin.DateFieldListFilter),
    ]

    search_fields = [
        'application_number', 'applicant_full_name', 'applicant_mobile',
        'applicant_aadhaar_number', 'applicant_email'
    ]

    readonly_fields = [
        'id', 'application_number', 'applicant_age', 'is_complete',
        'is_migrant_verified', 'created_at', 'updated_at',
        'submitted_at', 'verified_at', 'approved_at', 'connection_issued_at'
    ]

    fieldsets = (
        ('Application Information', {
            'fields': (
                'id', 'application_number', 'status', 'is_complete',
                'created_at', 'updated_at'
            )
        }),
        ('Applicant Details', {
            'fields': (
                ('applicant_full_name', 'applicant_gender'),
                ('applicant_first_name', 'applicant_middle_name', 'applicant_last_name'),
                ('applicant_dob', 'applicant_age'),
                ('applicant_aadhaar_number', 'applicant_mobile'),
                'applicant_email',
                ('caste', 'is_migrant'),
            )
        }),
        ('Family Composition Document', {
            'fields': (
                ('family_doc_type', 'family_doc_number'),
                'family_doc_issuing_state',
                'is_deprivation_decl_signed',
            )
        }),
        ('Bank Details', {
            'fields': (
                'bank_account_name',
                ('bank_name', 'bank_branch'),
                ('bank_ifsc', 'bank_account_number'),
            )
        }),
        ('LPG Connection', {
            'fields': (
                'lpg_connection_type',
                'is_new_connection',
                'connection_remarks',
            )
        }),
        ('Consents & Declarations', {
            'classes': ('collapse',),
            'fields': (
                'aadhaar_consent_signed',
                'agrees_to_dbtl',
                'agrees_pre_installation_check',
                'agrees_mandatory_inspections',
                'declares_no_existing_lpg_or_png_connection',
                'declares_use_for_domestic_cooking_only',
                'consent_data_sharing_omc_bank',
            )
        }),
        ('Verification Status', {
            'fields': (
                'aadhaar_verification_status',
                'bank_verification_status',
                'address_verification_status',
                'is_migrant_verified',
            )
        }),
        ('Workflow Tracking', {
            'fields': (
                'rejection_reason',
                ('submitted_at', 'submitted_by'),
                ('verified_at', 'verified_by'),
                ('approved_at', 'approved_by'),
                'connection_issued_at',
            )
        }),
    )

    inlines = [
        UjjwalaV3AddressInline,
        UjjwalaV3FamilyMemberInline,
        UjjwalaV3DocumentInline,
        UjjwalaV3AuditLogInline,
    ]

    actions = ['mark_as_submitted', 'mark_as_under_verification', 'approve_applications']

    def status_badge(self, obj):
        """Display status as colored badge."""
        colors = {
            ApplicationStatus.DRAFT: '#6c757d',
            ApplicationStatus.SUBMITTED: '#007bff',
            ApplicationStatus.UNDER_VERIFICATION: '#ffc107',
            ApplicationStatus.VERIFICATION_FAILED: '#dc3545',
            ApplicationStatus.REJECTED: '#dc3545',
            ApplicationStatus.APPROVED: '#28a745',
            ApplicationStatus.CONNECTION_ISSUED: '#17a2b8',
            ApplicationStatus.CANCELLED: '#6c757d',
            ApplicationStatus.ON_HOLD: '#fd7e14',
        }
        color = colors.get(obj.status, '#6c757d')
        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 10px; '
            'border-radius: 3px; font-weight: bold;">{}</span>',
            color,
            obj.get_status_display()
        )
    status_badge.short_description = 'Status'

    def is_complete_badge(self, obj):
        """Display completion status as badge."""
        if obj.is_complete:
            return format_html(
                '<span style="color: green; font-weight: bold;">✓ Complete</span>'
            )
        return format_html(
            '<span style="color: red; font-weight: bold;">✗ Incomplete</span>'
        )
    is_complete_badge.short_description = 'Complete?'
    is_complete_badge.admin_order_field = 'id'

    def mark_as_submitted(self, request, queryset):
        """Bulk action to mark applications as submitted."""
        from django.utils import timezone
        count = queryset.filter(status=ApplicationStatus.DRAFT).update(
            status=ApplicationStatus.SUBMITTED,
            submitted_at=timezone.now(),
            submitted_by=request.user
        )
        self.message_user(request, f'{count} applications marked as submitted.')
    mark_as_submitted.short_description = 'Mark selected as Submitted'

    def mark_as_under_verification(self, request, queryset):
        """Bulk action to mark applications as under verification."""
        count = queryset.filter(status=ApplicationStatus.SUBMITTED).update(
            status=ApplicationStatus.UNDER_VERIFICATION
        )
        self.message_user(request, f'{count} applications marked as under verification.')
    mark_as_under_verification.short_description = 'Mark selected as Under Verification'

    def approve_applications(self, request, queryset):
        """Bulk action to approve applications."""
        from django.utils import timezone
        count = queryset.filter(status=ApplicationStatus.UNDER_VERIFICATION).update(
            status=ApplicationStatus.APPROVED,
            approved_at=timezone.now(),
            approved_by=request.user
        )
        self.message_user(request, f'{count} applications approved.')
    approve_applications.short_description = 'Approve selected applications'

    def get_queryset(self, request):
        """Optimize queryset with select_related."""
        qs = super().get_queryset(request)
        return qs.select_related(
            'submitted_by', 'verified_by', 'approved_by'
        ).prefetch_related(
            'addresses', 'family_members', 'documents'
        )


@admin.register(UjjwalaV3Address)
class UjjwalaV3AddressAdmin(admin.ModelAdmin):
    """Admin interface for Addresses."""

    list_display = [
        'application_link', 'address_type_badge', 'city_town',
        'district', 'state_display', 'pincode', 'poa_code', 'created_at'
    ]

    list_filter = [
        'address_type', 'state', 'district',
        ('created_at', admin.DateFieldListFilter),
    ]

    search_fields = [
        'application__application_number', 'application__applicant_full_name',
        'city_town', 'district', 'pincode', 'village_panchayat_area'
    ]

    readonly_fields = ['id', 'created_at', 'updated_at']

    fieldsets = (
        ('Link to Application', {
            'fields': ('id', 'application', 'address_type')
        }),
        ('Address Details', {
            'fields': (
                ('house_flat_no', 'floor_number'),
                'building_colony',
                'street_road',
                'village_panchayat_area',
                'block_sub_district',
                ('city_town', 'district'),
                ('state', 'pincode'),
                'landmark',
                'area_post_office_name',
            )
        }),
        ('Proof of Address', {
            'fields': ('poa_code',)
        }),
        ('Geolocation (Optional)', {
            'classes': ('collapse',),
            'fields': (('latitude', 'longitude'),)
        }),
        ('Timestamps', {
            'fields': (('created_at', 'updated_at'),)
        }),
    )

    def application_link(self, obj):
        """Link to parent application."""
        url = reverse('admin:ujjwala_v3_ujjwalav3application_change', args=[obj.application.pk])
        return format_html('<a href="{}">{}</a>', url, obj.application.application_number or obj.application.id)
    application_link.short_description = 'Application'

    def address_type_badge(self, obj):
        """Display address type as badge."""
        colors = {
            AddressType.CURRENT: '#007bff',
            AddressType.PERMANENT: '#28a745',
            AddressType.OTHER: '#6c757d',
        }
        color = colors.get(obj.address_type, '#6c757d')
        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 8px; '
            'border-radius: 3px;">{}</span>',
            color,
            obj.get_address_type_display()
        )
    address_type_badge.short_description = 'Type'

    def state_display(self, obj):
        """Display state full name."""
        return obj.get_state_display()
    state_display.short_description = 'State'
    state_display.admin_order_field = 'state'


@admin.register(UjjwalaV3FamilyMember)
class UjjwalaV3FamilyMemberAdmin(admin.ModelAdmin):
    """Admin interface for Family Members."""

    list_display = [
        'application_link', 'full_name', 'relation_badge',
        'gender_display', 'dob', 'age_at_application',
        'uid_status_display', 'created_at'
    ]

    list_filter = [
        'relation_to_applicant', 'gender', 'is_valid_uid', 'validated',
        ('created_at', admin.DateFieldListFilter),
    ]

    search_fields = [
        'application__application_number', 'application__applicant_full_name',
        'full_name', 'aadhaar_number'
    ]

    readonly_fields = [
        'id', 'age_at_application', 'uid_photos_display',
        'ocr_result_display', 'created_at', 'updated_at'
    ]

    fieldsets = (
        ('Link to Application', {
            'fields': ('id', 'application')
        }),
        ('Member Details', {
            'fields': (
                'full_name',
                ('relation_to_applicant', 'gender'),
                ('aadhaar_number', 'dob'),
                'age_at_application',
            )
        }),
        ('UID/Aadhaar Photos', {
            'fields': (
                'uid_photos_display',
                ('uid_front_link', 'uid_back_link'),
                ('uid_original_front_link', 'uid_original_back_link'),
                ('uid_front_compressed', 'uid_back_compressed'),
                ('uid_front_file_size', 'uid_back_file_size'),
            )
        }),
        ('OCR & Validation', {
            'fields': (
                'ocr_result_display',
                ('is_valid_uid', 'validated'),
            )
        }),
        ('Additional Information', {
            'classes': ('collapse',),
            'fields': (
                'additional_details',
                'ration_card_available',
            )
        }),
        ('Timestamps', {
            'fields': (('created_at', 'updated_at'),)
        }),
    )

    def uid_photos_display(self, obj):
        """Display UID photo links with preview."""
        if not obj:
            return '-'

        html_parts = []
        if obj.uid_front_link:
            html_parts.append(
                f'<div style="margin: 10px 0;">'
                f'<strong>Front:</strong> <a href="{obj.uid_front_link}" target="_blank">View</a><br>'
                f'<a href="{obj.uid_front_link}" target="_blank">'
                f'<img src="{obj.uid_front_link}" style="max-width: 200px; max-height: 150px; border: 1px solid #ddd; margin-top: 5px;" />'
                f'</a></div>'
            )

        if obj.uid_back_link:
            html_parts.append(
                f'<div style="margin: 10px 0;">'
                f'<strong>Back:</strong> <a href="{obj.uid_back_link}" target="_blank">View</a><br>'
                f'<a href="{obj.uid_back_link}" target="_blank">'
                f'<img src="{obj.uid_back_link}" style="max-width: 200px; max-height: 150px; border: 1px solid #ddd; margin-top: 5px;" />'
                f'</a></div>'
            )

        return mark_safe(''.join(html_parts)) if html_parts else '-'
    uid_photos_display.short_description = 'UID Photos'

    def ocr_result_display(self, obj):
        """Display OCR result in formatted JSON."""
        if obj and obj.uid_check_result:
            import json
            try:
                formatted = json.dumps(obj.uid_check_result, indent=2)
                return mark_safe(f'<pre style="background: #f5f5f5; padding: 10px; border-radius: 5px;">{formatted}</pre>')
            except:
                return str(obj.uid_check_result)
        return '-'
    ocr_result_display.short_description = 'OCR Results'

    def uid_status_display(self, obj):
        """Display UID validation status."""
        if obj.is_valid_uid:
            return format_html(
                '<span style="color: green; font-weight: bold;">✓ Valid</span>'
            )
        elif obj.uid_front_link and obj.uid_back_link:
            return format_html(
                '<span style="color: orange; font-weight: bold;">⧗ Pending</span>'
            )
        return format_html(
            '<span style="color: red; font-weight: bold;">✗ Missing</span>'
        )
    uid_status_display.short_description = 'UID Status'

    def application_link(self, obj):
        """Link to parent application."""
        url = reverse('admin:ujjwala_v3_ujjwalav3application_change', args=[obj.application.pk])
        return format_html('<a href="{}">{}</a>', url, obj.application.application_number or obj.application.id)
    application_link.short_description = 'Application'

    def relation_badge(self, obj):
        """Display relation as badge."""
        color = '#dc3545' if obj.relation_to_applicant == RelationToApplicant.SELF else '#17a2b8'
        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 8px; '
            'border-radius: 3px;">{}</span>',
            color,
            obj.get_relation_to_applicant_display()
        )
    relation_badge.short_description = 'Relation'

    def gender_display(self, obj):
        """Display gender."""
        return obj.get_gender_display()
    gender_display.short_description = 'Gender'
    gender_display.admin_order_field = 'gender'


@admin.register(UjjwalaV3Document)
class UjjwalaV3DocumentAdmin(admin.ModelAdmin):
    """Admin interface for Documents."""

    list_display = [
        'application_link', 'doc_type_badge', 'file_name',
        'file_size_display', 'is_verified_badge', 'uploaded_by',
        'created_at'
    ]

    list_filter = [
        'doc_type', 'is_verified',
        ('created_at', admin.DateFieldListFilter),
        ('verified_at', admin.DateFieldListFilter),
    ]

    search_fields = [
        'application__application_number', 'application__applicant_full_name',
        'file_name', 'description'
    ]

    readonly_fields = [
        'id', 'file_size', 'mime_type', 'uploaded_by',
        'verified_by', 'verified_at', 'created_at', 'updated_at',
        'file_preview'
    ]

    fieldsets = (
        ('Link to Application', {
            'fields': ('id', 'application', 'family_member', 'address')
        }),
        ('Document Details', {
            'fields': (
                'doc_type',
                'file',
                'file_preview',
                ('file_name', 'file_size'),
                'mime_type',
                'description',
            )
        }),
        ('Verification', {
            'fields': (
                'is_verified',
                ('verified_by', 'verified_at'),
            )
        }),
        ('Upload Info', {
            'fields': (
                'uploaded_by',
                ('created_at', 'updated_at'),
            )
        }),
    )

    actions = ['mark_as_verified']

    def application_link(self, obj):
        """Link to parent application."""
        url = reverse('admin:ujjwala_v3_ujjwalav3application_change', args=[obj.application.pk])
        return format_html('<a href="{}">{}</a>', url, obj.application.application_number or obj.application.id)
    application_link.short_description = 'Application'

    def doc_type_badge(self, obj):
        """Display document type as badge."""
        return format_html(
            '<span style="background-color: #6c757d; color: white; padding: 3px 8px; '
            'border-radius: 3px; font-size: 11px;">{}</span>',
            obj.get_doc_type_display()
        )
    doc_type_badge.short_description = 'Document Type'

    def file_size_display(self, obj):
        """Display file size in human-readable format."""
        if obj.file_size:
            size = obj.file_size
            for unit in ['B', 'KB', 'MB', 'GB']:
                if size < 1024.0:
                    return f'{size:.1f} {unit}'
                size /= 1024.0
        return '-'
    file_size_display.short_description = 'Size'
    file_size_display.admin_order_field = 'file_size'

    def is_verified_badge(self, obj):
        """Display verification status as badge."""
        if obj.is_verified:
            return format_html(
                '<span style="color: green; font-weight: bold;">✓ Verified</span>'
            )
        return format_html(
            '<span style="color: orange; font-weight: bold;">⧗ Pending</span>'
        )
    is_verified_badge.short_description = 'Verified?'
    is_verified_badge.admin_order_field = 'is_verified'

    def file_preview(self, obj):
        """Display file preview for images."""
        if obj.file:
            if obj.mime_type and obj.mime_type.startswith('image/'):
                return format_html(
                    '<a href="{}" target="_blank">'
                    '<img src="{}" style="max-width: 300px; max-height: 300px;" />'
                    '</a>',
                    obj.file.url, obj.file.url
                )
            return format_html(
                '<a href="{}" target="_blank">Download File</a>',
                obj.file.url
            )
        return '-'
    file_preview.short_description = 'Preview'

    def mark_as_verified(self, request, queryset):
        """Bulk action to mark documents as verified."""
        from django.utils import timezone
        count = queryset.filter(is_verified=False).update(
            is_verified=True,
            verified_by=request.user,
            verified_at=timezone.now()
        )
        self.message_user(request, f'{count} documents marked as verified.')
    mark_as_verified.short_description = 'Mark selected as Verified'


@admin.register(UjjwalaV3AuditLog)
class UjjwalaV3AuditLogAdmin(admin.ModelAdmin):
    """Admin interface for Audit Logs."""

    list_display = [
        'created_at', 'application_link', 'action_badge',
        'actor', 'ip_address'
    ]

    list_filter = [
        'action',
        ('created_at', admin.DateFieldListFilter),
    ]

    search_fields = [
        'application__application_number', 'application__applicant_full_name',
        'action', 'remarks', 'actor__username'
    ]

    readonly_fields = [
        'id', 'application', 'action', 'actor', 'changes',
        'remarks', 'ip_address', 'created_at'
    ]

    fieldsets = (
        ('Audit Information', {
            'fields': (
                'id',
                ('application', 'action'),
                ('actor', 'ip_address'),
                'created_at',
            )
        }),
        ('Details', {
            'fields': ('changes', 'remarks')
        }),
    )

    def has_add_permission(self, request):
        """Prevent manual addition of audit logs."""
        return False

    def has_delete_permission(self, request, obj=None):
        """Prevent deletion of audit logs."""
        return False

    def application_link(self, obj):
        """Link to parent application."""
        url = reverse('admin:ujjwala_v3_ujjwalav3application_change', args=[obj.application.pk])
        return format_html('<a href="{}">{}</a>', url, obj.application.application_number or obj.application.id)
    application_link.short_description = 'Application'

    def action_badge(self, obj):
        """Display action as badge."""
        return format_html(
            '<span style="background-color: #17a2b8; color: white; padding: 3px 8px; '
            'border-radius: 3px; font-family: monospace;">{}</span>',
            obj.action
        )
    action_badge.short_description = 'Action'
