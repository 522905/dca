import io
import zipfile
from datetime import datetime

import magic
import requests
from django.conf import settings
from django.contrib import admin
from django.http import HttpResponse
from django.template import loader
from django.utils.safestring import mark_safe
from django_admin_listfilter_dropdown.filters import DropdownFilter
from django_fsm_log.admin import StateLogInline
from import_export.admin import ExportActionMixin
from rangefilter.filters import DateRangeFilter

from fsm_admin2_custom.admin import FSMTransitionCustomMixin
from .enums import ResidentialStatusEnum, UjjwalaApplicationDocumentsEnum, FamilyMemberRelationEnum, MaritalStatusEnum
from .models import UjjwalaV2Application, FamilyMembers, UjjwalaApplicationDocuments, UjjwalaV2ApplicationStatus, \
	UserDocuments, PreInspectionDocuments, PreInspection, ConnectionDisbursementDocuments, ConnectionDisbursement
from .ujjwala_functions import download_ujjwala_documents
from advanced_filters.admin import AdminAdvancedFiltersMixin


class UjjwalaApplicationDocumentsInline(admin.TabularInline):
	extra = 0
	model = UjjwalaApplicationDocuments
	fields = ('type', 'download_links', 'link', 'file_size')
	readonly_fields = ('download_links',)
# template = 'connection_app/admin/document-inline.html'


class FamilyMembersInline(admin.TabularInline):
	extra = 0
	model = FamilyMembers
	fields = ('name', 'relation', 'dob', 'uid_no', 'download_links', 'uid_front_link', 'uid_back_link',
			  'uid_check_result', 'uid_front_file_size', 'uid_back_file_size',)
	readonly_fields = ('download_links', 'uid_check_result', 'uid_front_file_size',
					   'uid_back_file_size',
					   )


@admin.register(UjjwalaV2Application)
class UjjwalaV2Admin(AdminAdvancedFiltersMixin, ExportActionMixin, FSMTransitionCustomMixin, admin.ModelAdmin):
	fsm_transition_form_template = 'ujjwala/transaction_form_template.html'
	list_display = (
		'id',
		'name',
		'address',
		'address_json',
		'contact_mobile',
		'referral_code',
		'robo_sdms_dedup',
		'status',
		'consumer_id'
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

	def has_change_permission(self, request, obj=None):
		if not obj:
			return True
		return obj.status == UjjwalaV2ApplicationStatus.EDIT_APPLICATION

	def get_fields(self, request, obj=None):
		# fields = super().get_fields(request, obj)
		# return fields
		if obj and obj.status in (
				UjjwalaV2ApplicationStatus.EDIT_APPLICATION
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
			]
		else:
			return super().get_fields(request, obj)

	def get_readonly_fields(self, request, obj=None):
		readonly_fields = super().get_readonly_fields(request, obj)

		if obj and obj.status in (
				UjjwalaV2ApplicationStatus.EKYC_ACCEPTED, UjjwalaV2ApplicationStatus.DOCUMENTS_UPLOADED
		):
			readonly_fields = readonly_fields + ['download_legal_docs']

		return readonly_fields

	def download_legal_docs(self, obj=None):
		return mark_safe("""
			<input type="submit" value="Download Legal Docs" name="_download-legal-doc-pdf">
		""")

	def download_legal_documents_pdf(self, obj):
		return download_ujjwala_documents(obj)

	def change_view(self, request, object_id, form_url='', extra_context=None):
		if "_download-legal-doc-pdf" in request.POST:
			obj = UjjwalaV2Application.objects.get(pk=object_id)
			return self.download_legal_documents_pdf(obj)
		return super().change_view(request, object_id, form_url=form_url, extra_context=extra_context)

	def fsm_transition_view_extra_context(self, obj):
		return {'obj': obj}


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
		'mechanic',
		'status',
	)
	list_filter = ('parent', 'mechanic')
	inlines = (PreInspectionDocumentsAdmin, StateLogInline,)
	fsm_fields = ['status', ]

	def has_change_permission(self, request, obj=None):
		if not obj:
			return True

	# def fsm_transition_view_extra_context(self, obj):
	# 	return {'obj': obj}


class ConnectionDisbursementDocumentsAdmin(admin.TabularInline):
	fields = (
		'type',
		'download_links',
		'compressed',
		'file_size',
	)
	model = ConnectionDisbursementDocuments
	extra = 0

	readonly_fields = ('type', 'download_links', 'compressed', 'file_size',)


@admin.register(ConnectionDisbursement)
class ConnectionDisbursementAdmin(FSMTransitionCustomMixin, admin.ModelAdmin):
	list_display = (
		'id',
		'created_on',
		'updated_on',
		'status',
	)
	list_filter = ('parent', 'status')
	inlines = (ConnectionDisbursementDocumentsAdmin, StateLogInline,)
	fsm_fields = ['status', ]

	def has_change_permission(self, request, obj=None):
		if not obj:
			return True
