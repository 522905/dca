# -*- coding: utf-8 -*-
from django.contrib import admin
from import_export.admin import ExportActionMixin

from .models import CommunicationLog


@admin.register(CommunicationLog)
class CommunicationLogAdmin(ExportActionMixin, admin.ModelAdmin):
    def has_add_permission(self, request, obj=None):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    list_display = (
        'id',
        'created_on',
        'updated_on',
        'content_type',
        'object_id',
        'event',
        'channel',
        'channel_subscriber',
        'status',
    )
    list_filter = (
        'created_on',
        'updated_on',
        'content_type',
    )
