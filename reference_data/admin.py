from django.contrib import admin

# Register your models here.
# -*- coding: utf-8 -*-
from django.contrib import admin

from .models import TokensExcluded, IFSCodeList


@admin.register(TokensExcluded)
class TokensExcludedAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'gender')
    search_fields = ('name', 'gender')


@admin.register(IFSCodeList)
class IFSCodeListAdmin(admin.ModelAdmin):
    list_display = ('id', 'old_ifscode', 'new_ifscode')
    search_fields = ('old_ifscode', 'new_ifscode')
