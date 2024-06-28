from django.contrib.auth.models import User
from django.contrib.contenttypes.models import ContentType
from django.db import models

from service_request.enums import ServiceRequestTypeEnum, ServiceRequestTypeStatusEnum


class ServiceRequest(models.Model):
	created_on = models.DateTimeField(auto_now_add=True)
	updated_on = models.DateTimeField(auto_now=True)
	service_request_type = models.CharField(max_length=128, choices=ServiceRequestTypeEnum.choices)
	content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE, null=True)
	object_id = models.PositiveIntegerField(null=True)
	camunda_process_id = models.TextField(null=True, blank=True)
	request_by = models.ForeignKey(User, on_delete=models.PROTECT, null=True, blank=True)
	form_data = models.JSONField(null=True, blank=True)
	status = models.CharField(max_length=128, choices=ServiceRequestTypeStatusEnum.choices,
	                          default=ServiceRequestTypeStatusEnum.PENDING)
	remarks = models.TextField(null=True, blank=True)
	reviewed_by = models.ForeignKey(User, on_delete=models.PROTECT, null=True, related_name="reviewed_by")
	reviewed_on = models.DateTimeField(null=True)
	sdms_ticket_number = models.CharField(max_length=52, null=True, blank=True)

	class Meta:
		permissions = (
			("can_resolve_service_request", "Can Resolve Service Request"),
		)

	def get_object_status(self):
		return self.content_type.get_object_for_this_type(pk=self.object_id).status
