from django.contrib import admin

# Register your models here.
from service_request.models import ServiceRequest


@admin.register(ServiceRequest)
class ServiceRequestAdmin(admin.ModelAdmin):
	pass
