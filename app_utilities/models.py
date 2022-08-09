from django.contrib.auth.models import User
from django.db import models


class UjjwalaApplicationOcrErrorLogs(models.Model):
	generated_on = models.DateTimeField()
	wait_time = models.FloatField(null=True, blank=True)
	api_result = models.CharField(max_length=48, null=True, blank=True)
	status = models.CharField(max_length=48, null=True, blank=True)
	uid_front_url = models.URLField(null=True, blank=True)
	uid_back_url = models.URLField(null=True, blank=True)
	data = models.JSONField(null=True, blank=True)
	user = models.ForeignKey(User, on_delete=models.PROTECT, null=True, blank=True)
