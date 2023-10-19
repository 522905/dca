from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.db import models

from django.db import models
from django.utils.timezone import now

from otp.enums import OtpChannels


class Otp(models.Model):
	# attempts = models.PositiveSmallIntegerField()
	# max_attempts = models.PositiveSmallIntegerField()
	created_on = models.DateTimeField(auto_now_add=True)
	updated_on = models.DateTimeField(auto_now=True)
	reference_number = models.CharField(max_length=32, primary_key=True)
	otp = models.CharField(max_length=8)

	mobile = models.CharField(max_length=16)
	channel = models.CharField(max_length=32, choices=OtpChannels.choices)

	extra = models.JSONField()
	variables = models.JSONField(null=True, blank=True)

	valid_till = models.DateTimeField()

	closed = models.BooleanField(default=False)

	content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE, null=True)
	object_id = models.PositiveIntegerField(null=True)
	content_object = GenericForeignKey('content_type', 'object_id')
	transition = models.CharField(max_length=256, null=True, blank=True)


	def verify_and_close(self, otp):
		if self.closed:
			return False, "Code already Used"
		elif now() >= self.valid_till:
			return False, "Code Expired"
		elif self.otp == otp:
			self.closed = True
			self.save(update_fields=['closed'])
			return True, "Success"
		else:
			return False, "Invalid Code"
