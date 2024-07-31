from django.contrib.auth.models import User
from django.db import models
from djgeojson.fields import PointField, PolygonField
from organizations.models import Organization
from treenode.models import TreeNodeModel

from reference_data.models import Distributor
from teams.enums import UserProfileTypeEnum, UserProfileDocumentsEnum


class LocationTypeEnum(models.TextChoices):
	FIXED = 'FIXED', 'Fixed'
	PORTABLE = 'PORTABLE', 'Portable'


class UserProfile(models.Model):
	user = models.OneToOneField(User, on_delete=models.PROTECT)
	type = models.CharField(max_length=32, choices=UserProfileTypeEnum.choices)
	vehicle_no = models.CharField(max_length=10, null=True, blank=True)
	phone_number = models.CharField(max_length=10, null=True, blank=True)
	sdms_service_areas = models.ManyToManyField("SDMSServiceArea", blank=True, null=True)


class SDMSUser(models.Model):
	parent = models.ForeignKey(UserProfile, on_delete=models.PROTECT)
	distributor = models.ForeignKey(Distributor, on_delete=models.PROTECT)
	delivery_boy_login = models.CharField(max_length=32)
	delivery_boy_full_name = models.CharField(max_length=256, null=True, blank=True)


class UserProfileDocuments(models.Model):
	parent = models.ForeignKey(UserProfile, on_delete=models.PROTECT)
	type = models.CharField(max_length=128, choices=UserProfileDocumentsEnum.choices)
	link = models.URLField()


class ServiceLocations(models.Model):
	parent = models.ForeignKey(
		Organization, on_delete=models.CASCADE, related_name='service_locations', null=True, blank=True
	)
	title = models.CharField(max_length=128, null=True, blank=True)
	type = models.CharField(max_length=25, choices=LocationTypeEnum.choices)
	start_working_hours = models.TimeField()
	end_working_hours = models.TimeField()
	phone_numbers = models.JSONField(null=True, blank=True)
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
	# user_profile = models.ManyToOneRel(UserProfile, on_delete=models.SET_NULL)

	class Meta(TreeNodeModel.Meta):
		verbose_name = "Service Area"
		verbose_name_plural = "Service Areas"


class ServiceAreaUserProfile(models.Model):
	parent = models.ForeignKey(ServiceArea, on_delete=models.CASCADE, related_name='service_area')
	user_profile = models.ForeignKey(UserProfile, on_delete=models.CASCADE, related_name='user_profile', null=True)


class FormFillArea(models.Model):
	name = models.CharField(max_length=256)
	service_location = models.ForeignKey(
		ServiceLocations, on_delete=models.CASCADE, related_name='service_locations', null=True, blank=True
	)


class ServiceAreaHex(models.Model):
	hex_bound = models.CharField(max_length=512, blank=True, null=True)
	hex_centroid = models.CharField(max_length=512, blank=True, null=True)
	public_place_point = models.CharField(max_length=512, blank=True, null=True)
	public_place_name = models.CharField(max_length=512, blank=True, null=True)
	public_place_link = models.CharField(max_length=512, blank=True, null=True)
	hex_id = models.CharField(max_length=64, blank=True, null=True)  # This field type is a guess.
	cluster_name = models.CharField(max_length=256, blank=True, null=True)
	hex_resolution = models.IntegerField(blank=True, null=True)
	id = models.IntegerField(primary_key=True)
	service_area = models.CharField(max_length=256, blank=True, null=True)

	class Meta:
		managed = False
		db_table = 'service_area_hex'


class SDMSServiceArea(models.Model):
	created_on = models.DateTimeField(auto_now_add=True, null=True)
	updated_on = models.DateTimeField(auto_now=True, null=True)
	area_name = models.CharField(max_length=128)

	def __str__(self):
		return self.area_name
