from django.contrib import admin

# Register your models here.
# -*- coding: utf-8 -*-
from django.contrib import admin

from .models import TokensExcluded, IFSCodeList, ServiceType, Distributor, HTMLTemplate, HTMLTemplateVariable


@admin.register(TokensExcluded)
class TokensExcludedAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'gender')
    search_fields = ('name', 'gender')


@admin.register(IFSCodeList)
class IFSCodeListAdmin(admin.ModelAdmin):
    list_display = ('id', 'old_ifscode', 'new_ifscode')
    search_fields = ('old_ifscode', 'new_ifscode')


class HTMLTemplateVariableInlineAdmin(admin.TabularInline):
    model = HTMLTemplateVariable
    extra = 1


@admin.register(HTMLTemplate)
class HTMLTemplateAdmin(admin.ModelAdmin):
    list_display = ('id', 'template_name',)
    search_fields = ('template_name',)
    inlines = [HTMLTemplateVariableInlineAdmin,]


@admin.register(ServiceType)
class ServiceTypeAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'description')
    search_fields = ('name', 'description')


@admin.register(Distributor)
class DistributorAdmin(admin.ModelAdmin):
    list_display = ('id', 'code', 'name')
    search_fields = ('code', 'name')


