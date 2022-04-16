from django.contrib import admin

# Register your models here.
# -*- coding: utf-8 -*-
from django.contrib import admin
from import_export.admin import ExportActionMixin

from fsm_admin2_custom.admin import FSMTransitionCustomMixin
from .models import UjjwalaV2Application, FamilyMembers, UjjwalaApplicationDocuments, UjjwalaV2ApplicationStatus
from rangefilter.filters import DateRangeFilter
from django_admin_listfilter_dropdown.filters import DropdownFilter


class UjjwalaApplicationDocumentsInline(admin.TabularInline):
	extra = 0
	model = UjjwalaApplicationDocuments
	# template = 'connection_app/admin/document-inline.html'


class FamilyMembersInline(admin.TabularInline):
	extra = 0
	model = FamilyMembers


@admin.register(UjjwalaV2Application)
class UjjwalaV2Admin(ExportActionMixin, FSMTransitionCustomMixin, admin.ModelAdmin):
	list_display = (
		'id',
		'name',
		'address',
		'contact_mobile',
		'referral_code',
		'status'
	)
	search_fields = ('name', 'referral_code', 'contact_mobile')
	ordering = ('id',)

	list_filter = (
		('created_on', DateRangeFilter),
		('updated_on', DateRangeFilter),
		('status', DropdownFilter)
	)

	inlines = [
		FamilyMembersInline, UjjwalaApplicationDocumentsInline,
	]
	fsm_fields = ['status', 'installation_status']

	def has_change_permission(self, request, obj=None):
		if not obj: return True
		return obj.status == UjjwalaV2ApplicationStatus.EDIT_APPLICATION
