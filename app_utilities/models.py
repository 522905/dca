from django.db import models

from app_utilities.enums import AppUtilitiesErrorApplicationEnum


class UjjwalaApplicationOcrErrorLogs(models.Model):
	generated_on = models.DateTimeField()
	wait_time = models.FloatField(null=True, blank=True)
	status = models.CharField(max_length=48, null=True, blank=True)
	uid_front_url = models.URLField(null=True, blank=True)
	uid_back_url = models.URLField(null=True, blank=True)
	data = models.JSONField(null=True, blank=True)


