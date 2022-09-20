from django.contrib import admin

# Register your models here.
# -*- coding: utf-8 -*-
from django.contrib import admin

from .models import TokensExcluded


@admin.register(TokensExcluded)
class TokensExcludedAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'gender')
    search_fields = ('name', 'gender')
