from django.contrib import admin

# Register your models here.
# -*- coding: utf-8 -*-
from django.contrib import admin
from django.utils.html import format_html

from .models import TokensExcluded, IFSCodeList, ServiceType, Distributor, HTMLTemplate, HTMLTemplateVariable, Product, \
    Form, RationCardFamilyMember, RationCard


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


@admin.register(Form)
class FormAdmin(admin.ModelAdmin):
    list_display = ('id', 'enabled', 'created_on', 'updated_on', 'name',)
    search_fields = ('name',)


@admin.register(ServiceType)
class ServiceTypeAdmin(admin.ModelAdmin):
    list_display = ('id', 'enabled', 'created_on', 'updated_on', 'name', 'description')
    search_fields = ('name', 'description')
    filter_horizontal = ['forms', ]


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ('id', 'enabled', 'created_on', 'updated_on', 'name', 'unit', 'price', 'description')
    search_fields = ('name', 'description')


@admin.register(Distributor)
class DistributorAdmin(admin.ModelAdmin):
    list_display = ('id', 'code', 'name')
    search_fields = ('code', 'name')


class RationCardFamilyMemberInline(admin.TabularInline):
    model = RationCardFamilyMember
    extra = 0
    readonly_fields = ('created_at',)
    fields = ('sr', 'name', 'aadhar', 'sex', 'age', 'created_at')


@admin.register(RationCard)
class RationCardAdmin(admin.ModelAdmin):
    list_display = (
        'ration_no',
        'uid',
        'head_of_family',
        'scheme',
        'gas_company',
        'has_screenshot',
        'created_at'
    )

    list_filter = (
        'scheme',
        'gas_company',
        'created_at',
    )

    search_fields = (
        'ration_no',
        'uid',
        'head_of_family',
        'owner_name',
        'address'
    )

    readonly_fields = (
        'uid',
        'ration_no',
        'screenshot_preview',
        'raw_variables_display',
        'created_at',
        'updated_at'
    )

    fieldsets = (
        ('Identifiers', {
            'fields': ('uid', 'ration_no')
        }),
        ('Ration Card Details', {
            'fields': (
                'scheme',
                'conn_type',
                'gas_no',
                'gas_company',
                'owner_name',
                'gas_agency',
                'head_of_family',
                'address',
                'annual_income',
                'fps_no',
                'fps_name_address'
            )
        }),
        ('Screenshot', {
            'fields': ('screenshot_file', 'screenshot_preview')
        }),
        ('Raw Data', {
            'fields': ('raw_variables_display',),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        })
    )

    inlines = [RationCardFamilyMemberInline]

    def has_screenshot(self, obj):
        return bool(obj.screenshot_file)

    has_screenshot.boolean = True
    has_screenshot.short_description = 'Screenshot'

    def screenshot_preview(self, obj):
        if obj.screenshot_file:
            return format_html(
                '<a href="{}" target="_blank"><img src="{}" style="max-width: 300px; max-height: 300px;"/></a>',
                obj.screenshot_file.url,
                obj.screenshot_file.url
            )
        return "No screenshot"

    screenshot_preview.short_description = 'Screenshot Preview'

    def raw_variables_display(self, obj):
        import json
        return format_html(
            '<pre>{}</pre>',
            json.dumps(obj.raw_variables, indent=2, ensure_ascii=False)
        )

    raw_variables_display.short_description = 'Raw Variables (JSON)'


@admin.register(RationCardFamilyMember)
class RationCardFamilyMemberAdmin(admin.ModelAdmin):
    list_display = ('name', 'ration_card', 'sr', 'sex', 'age', 'aadhar')
    list_filter = ('sex', 'aadhar')
    search_fields = ('name', 'ration_card__ration_no', 'ration_card__head_of_family')
    readonly_fields = ('created_at', 'updated_at')

    fieldsets = (
        (None, {
            'fields': ('ration_card', 'sr', 'name', 'aadhar', 'sex', 'age')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        })
    )
