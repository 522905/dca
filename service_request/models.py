from django.db import models

from service_request.enums import ServiceRequestTypeEnum


class ServiceRequest(models.Model):
	created_on = models.DateTimeField(auto_now_add=True)
	updated_on = models.DateTimeField(auto_now=True)
	service_request_type = models.CharField(max_length=128, choices=ServiceRequestTypeEnum.choices)
	camunda_process_id = models.CharField(max_length=128, null=True, blank=True)
