from django.contrib import admin

# Register your models here.
from django.utils.html import format_html

from domestic_app.settings import CAMUNDA_WEB_ROOT_URL
from service_request.models import ServiceRequest


@admin.register(ServiceRequest)
class ServiceRequestAdmin(admin.ModelAdmin):
	list_display = (
		'id',
		'created_on',
		'updated_on',
		'service_request_type',
		'content_type',
		'object_id',
		'cockpit_link',
		'request_by',
		# 'form_data',
		'status',
	)

	list_filter = ('service_request_type', 'request_by', 'status',)
	fsm_fields = ['status', ]
	search_fields = ('form_data', 'created_on')

	def cockpit_link(self, obj=None):
		if not obj:
			return
		if not obj.camunda_process_id:
			return

		camunda_url = "{}/camunda/app/cockpit/default/#/history/process-instance/{}".format(
			CAMUNDA_WEB_ROOT_URL, obj.camunda_process_id
		)

		return format_html('<a target="blank" href="{}">View Process</a>'.format(camunda_url))
