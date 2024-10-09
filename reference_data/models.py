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
