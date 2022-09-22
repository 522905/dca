from django.db import models
from import_export import resources
from import_export.fields import Field


class SdmsCustomerRecord(models.Model):
	consumer_id = models.CharField(max_length=64, primary_key=True)
	kyc_date = models.DateField()
	name = models.CharField(max_length=256)

	waitlist_status = models.CharField(max_length=64)
	nic_status = models.CharField(max_length=64)
	omc_status = models.CharField(max_length=64)
	address = models.TextField()
	contact_number = models.CharField(max_length=10, null=True)


class SdmsFamilyMemberRecord(models.Model):
	consumer_id = models.CharField(max_length=64)
	relation = models.CharField(max_length=64)

	first_name = models.CharField(max_length=128)
	last_name = models.CharField(max_length=128)


class BookResource(resources.ModelResource):
	consumer_id = Field(attribute='consumer_id', column_name='Consumer ID')
	kyc_date = Field(attribute='kyc_date', column_name='KYC Date')
	name = Field(attribute='name', column_name='Name')
	waitlist_status = Field(attribute='waitlist_status', column_name='Waitlist Status')
	nic_status = Field(attribute='nic_status', column_name='NIC Status')
	omc_status = Field(attribute='omc_status', column_name='OMC Status')
	address = Field(attribute='address', column_name='Address')

	class Meta:
		model = SdmsCustomerRecord
		# import_id_fields =

	def before_import_row(self, row, row_number=None, **kwargs):
		row['Consumer ID'] = row['Consumer ID'].replace(' ', '')

	def get_import_id_fields(self):
		return ['consumer_id']

	# def get_or_init_instance(self, instance_loader, row):
	# 	pass
