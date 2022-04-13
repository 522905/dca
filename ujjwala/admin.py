from django.contrib import admin

# Register your models here.
# -*- coding: utf-8 -*-
from django.contrib import admin
from import_export.admin import ExportActionMixin

from fsm_admin2_custom.admin import FSMTransitionCustomMixin
from .models import UjjwalaV2Application, FamilyMembers, UjjwalaApplicationDocuments


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
        'marital_status',
        'name',
        'address',
        'contact_mobile',
        'uid_linked_mobile',
        'uid_mobile_status',
        'referral_code',
    )
    search_fields = ('name',)
    inlines = [
        FamilyMembersInline, UjjwalaApplicationDocumentsInline,
    ]
    fsm_fields = ['status', 'installation_status']
