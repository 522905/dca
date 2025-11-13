import os

from django.contrib.contenttypes.models import ContentType
from django.core.files.storage import FileSystemStorage
from django.db import models
from django_comments.models import Comment
from django_comments_xtd.models import XtdComment

from reference_data.enums import TokenExcludeEnum, CommentTypeEnum, ProductUnitEnum, SDMSServiceRequestEnum


class TokensExcluded(models.Model):
	name = models.CharField(max_length=256)
	gender = models.CharField(max_length=32, choices=TokenExcludeEnum.choices, default=TokenExcludeEnum.MALE)


class IFSCodeList(models.Model):
	old_ifscode = models.CharField(max_length=32)
	new_ifscode = models.CharField(max_length=32)
	main_branch = models.BooleanField(default=False)


class RTGSList(models.Model):
	bank_name = models.CharField(max_length=255)
	ifscode = models.CharField(max_length=12)
	address = models.TextField()


class CommentX(XtdComment):
	comment_type = models.CharField(max_length=52, choices=CommentTypeEnum.choices, default=CommentTypeEnum.OTHERS)


class Form(models.Model):
	created_on = models.DateTimeField(auto_now_add=True)
	updated_on = models.DateTimeField(auto_now=True)
	enabled = models.BooleanField(default=True)
	name = models.CharField(max_length=128)
	html_content = models.TextField()
	variable_list = models.TextField(null=True, blank=True)


class ServiceType(models.Model):
	created_on = models.DateTimeField(auto_now_add=True)
	updated_on = models.DateTimeField(auto_now=True)
	enabled = models.BooleanField(default=True)
	name = models.CharField(max_length=48)
	description = models.CharField(max_length=128)
	# Many-to-Many relationship with Form
	forms = models.ManyToManyField(Form, related_name='service_types')

	def __str__(self):
		return self.name


class Product(models.Model):
	created_on = models.DateTimeField(auto_now_add=True)
	updated_on = models.DateTimeField(auto_now=True)
	enabled = models.BooleanField(default=True)
	code = models.CharField(max_length=48)
	name = models.CharField(max_length=128)
	unit = models.CharField(max_length=52, choices=ProductUnitEnum.choices, default=ProductUnitEnum.NOS)
	price = models.FloatField()
	description = models.TextField(null=True, blank=True)


class SDMSServiceRequest(models.Model):
	created_on = models.DateTimeField(auto_now_add=True)
	updated_on = models.DateTimeField(auto_now=True)
	enabled = models.BooleanField(default=True)
	type = models.CharField(max_length=52, choices=SDMSServiceRequestEnum.choices)
	description = models.TextField(null=True, blank=True)


class Distributor(models.Model):
	code = models.CharField(max_length=48)
	name = models.CharField(max_length=128)
	address = models.TextField()

	def __str__(self):
		return f"{self.code} - {self.name}"


class HTMLTemplate(models.Model):
	template_name = models.CharField(max_length=52)
	html_file_name = models.CharField(max_length=254)


class HTMLTemplateVariable(models.Model):
	parent = models.ForeignKey(HTMLTemplate, on_delete=models.CASCADE)
	name = models.CharField(max_length=52)


# Custom storage outside Django project
ration_card_storage = FileSystemStorage(
	location='/opt/data/dca.arungas.com/',
	base_url='/ration_card_files/'
)


def ration_card_file_upload_path(instance, filename):
	"""
	Upload path: ration_cards/{ration_no}/filename
	"""
	return os.path.join(
		'ration_cards',
		instance.ration_no or 'unknown',
		filename
	)


class RationCard(models.Model):
	"""Store ration card details extracted from Camunda"""

	# Core identifiers
	uid = models.CharField(max_length=255, db_index=True)
	ration_no = models.CharField(max_length=255, unique=True, db_index=True)

	# Ration card fields from JSON
	scheme = models.CharField(max_length=100, null=True, blank=True)
	conn_type = models.CharField(max_length=255, null=True, blank=True)
	gas_no = models.CharField(max_length=255, null=True, blank=True)
	gas_company = models.CharField(max_length=255, null=True, blank=True)
	owner_name = models.CharField(max_length=255, null=True, blank=True)
	gas_agency = models.CharField(max_length=255, null=True, blank=True)
	head_of_family = models.CharField(max_length=255, null=True, blank=True)
	address = models.TextField(null=True, blank=True)
	annual_income = models.CharField(max_length=100, null=True, blank=True)
	fps_no = models.CharField(max_length=100, null=True, blank=True)
	fps_name_address = models.TextField(null=True, blank=True)
	mapped = models.BooleanField(null=True, blank=True)
	content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE, null=True)
	object_id = models.PositiveIntegerField(null=True)

	# Screenshot file - uses custom storage
	screenshot_file = models.FileField(
		upload_to=ration_card_file_upload_path,
		storage=ration_card_storage,
		null=True,
		blank=True
	)

	raw_html = models.FileField(
		upload_to=ration_card_file_upload_path,
		storage=ration_card_storage,
		null=True,
		blank=True
	)

	# Raw data dump
	raw_variables = models.JSONField(default=dict)

	# Timestamps
	created_at = models.DateTimeField(auto_now_add=True)
	updated_at = models.DateTimeField(auto_now=True)

	def __str__(self):
		return f"{self.ration_no} - {self.head_of_family}"


class RationCardFamilyMember(models.Model):
	"""Store family members from ration card"""

	ration_card = models.ForeignKey(
		RationCard,
		on_delete=models.CASCADE,
		related_name='family_members'
	)

	sr = models.CharField(max_length=10, null=True, blank=True)
	name = models.CharField(max_length=255, null=True, blank=True)
	aadhar = models.CharField(max_length=10, null=True, blank=True)
	sex = models.CharField(max_length=1, null=True, blank=True)
	age = models.CharField(max_length=10, null=True, blank=True)

	created_at = models.DateTimeField(auto_now_add=True)
	updated_at = models.DateTimeField(auto_now=True)

	def __str__(self):
		return f"{self.name} - {self.ration_card.ration_no}"


class UIDNotHavingRationCard(models.Model):
	created_at = models.DateTimeField(auto_now_add=True)
	updated_at = models.DateTimeField(auto_now=True)
	uid = models.CharField(max_length=18)
	auto_checked = models.BooleanField(null=True, blank= True)
	mapped = models.BooleanField(null=True, blank=True)
