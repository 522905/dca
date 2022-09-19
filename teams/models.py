from django.contrib.auth.models import User
from django.db import models
from djgeojson.fields import PointField, PolygonField
from organizations.models import Organization
from treenode.models import TreeNodeModel


class LocationTypeEnum(models.TextChoices):
	FIXED = 'FIXED', 'Fixed'
	PORTABLE = 'PORTABLE', 'Portable'


class ServiceLocations(models.Model):
	parent = models.ForeignKey(
		Organization, on_delete=models.CASCADE, related_name='service_locations', null=True, blank=True
	)
	type = models.CharField(max_length=25, choices=LocationTypeEnum.choices)
	start_working_hours = models.TimeField()
	end_working_hours = models.TimeField()
	address = models.TextField()
	enabled = models.BooleanField(default=True)
	entry_point = PointField()
	location_polygon = PolygonField()

	def __str__(self):
		return "{} {} {}".format(self.start_working_hours, self.end_working_hours, self.address[:200])


class ServiceArea(TreeNodeModel):
	treenode_display_field = "name"
	name = models.CharField(max_length=64)
	description = models.CharField(max_length=256, null=True, blank=True)

	class Meta(TreeNodeModel.Meta):
		verbose_name = "Service Area"
		verbose_name_plural = "Service Areas"


class ServiceAreaMechanic(models.Model):
	parent = models.ForeignKey(ServiceArea, on_delete=models.CASCADE, related_name='service_area')
	mechanic = models.ForeignKey(User, on_delete=models.CASCADE, related_name='mechanic', null=True)
