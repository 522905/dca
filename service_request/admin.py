from django.contrib import admin

# Register your models here.
from service_request.models import ServiceRequest


@admin.register(ServiceRequest)
class ServiceRequestAdmin(admin.ModelAdmin):
	list_display = (
		'created_on',
		'updated_on',
		'service_request_type',
		'content_type',
		'object_id',
		'camunda_process_id',
		'request_by',
		'form_data',
		'status',
	)
