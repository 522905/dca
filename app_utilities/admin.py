from django.contrib import admin

# Register your models here.
# -*- coding: utf-8 -*-
from django.contrib import admin

from .models import UjjwalaApplicationOcrErrorLogs


@admin.register(UjjwalaApplicationOcrErrorLogs)
class UjjwalaApplicationOcrErrorLogsAdmin(admin.ModelAdmin):
    list_display = (
        'id',
        'user',
        'generated_on',
        'wait_time',
        'status',
        'uid_front_url',
        'uid_back_url',
        'data',
    )
    list_filter = ('generated_on', 'wait_time', 'status',)
