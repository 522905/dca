from django.db import models
from organizations.models import Organization


class LocationTypeEnum(models.TextChoices):
	FIXED = 'FIXED', 'Fixed'
	PORTABLE = 'PORTABLE', 'Portable'


class ServiceLocations(models.Model):
	parent = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name='service_locations')
	type = models.CharField(max_length=25, choices=LocationTypeEnum.choices)
	start_working_hours = models.TimeField()
	end_working_hours = models.TimeField()
	address = models.TextField()
	lat_long = models.CharField(max_length=256)
	enabled = models.BooleanField(default=True)

	def __str__(self):
		return "{} {} {}".format(self.start_working_hours, self.end_working_hours, self.address[:200])

