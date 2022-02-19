from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.db import models


class CommunicationLog(models.Model):
	created_on = models.DateTimeField(auto_now_add=True)
	updated_on = models.DateTimeField(auto_now=True)
	content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE, null=True)
	object_id = models.PositiveIntegerField(null=True)
	content_object = GenericForeignKey('content_type', 'object_id')
	event = models.CharField(max_length=25)
	channel = models.CharField(max_length=25)
	status = models.CharField(max_length=25, default="Initial")
	cron_processed = models.BooleanField(default=False)
	message_id = models.CharField(max_length=64, null=True)
