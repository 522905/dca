import datetime
from functools import partial

import django_rq
from django.contrib.auth.models import User
from django.db import models, transaction
from django.utils.safestring import mark_safe
from django_fsm import FSMField, transition, GET_STATE
from django_fsm_log.decorators import fsm_log_description, fsm_log_by
from organizations.models import Organization

from domestic.enums import DomesticApplicationRejectionTypeEnum
from domestic_app import settings
from teams.models import ServiceLocations, ServiceArea
from ujjwala.enums import ResidentialStatusEnum
from utils.enums import MaritalStatusEnum, UidMobileStatusEnum, RoboSdmsDedeupStatusEnum, \
	DomesticConnectionApplicationStatus, SchemeOnboardingStatusEnum, OmcClearedCustomerRemarksEnum, \
	FamilyMemberRelationEnum, DomesticConnectionApplicationDocumentsEnum, UserDocumentsEnum, PreInspectionTypeEnum, \
	PreInspectionStatusEnum, ConnectionDisbursementStatusEnum, InstallationTypeEnum


class DomesticConnectionApplication(models.Model):
	created_on = models.DateTimeField(auto_now_add=True)
	updated_on = models.DateTimeField(auto_now=True)
	sdms_last_updated_on = models.DateTimeField(null=True)
	rejection_type = models.CharField(max_length=64, choices=DomesticApplicationRejectionTypeEnum.choices, null=True, blank=True)
	marital_status = models.CharField(max_length=25, choices=MaritalStatusEnum.choices)
	residential_status = models.CharField(max_length=25, choices=ResidentialStatusEnum.choices, blank=True, null=True)
	name = models.CharField(max_length=50)
	address = models.TextField(null=True, blank=True)
	address_json = models.JSONField(null=True, blank=True)
	contact_mobile = models.CharField(max_length=10)
	consumer_id = models.CharField(max_length=16, null=True, blank=True, unique=True)
	uid_linked_mobile = models.CharField(max_length=10, null=True, blank=True)
	sdms_mobile_number = models.CharField(max_length=10, null=True, blank=True)
	uid_mobile_status = models.CharField(max_length=25, choices=UidMobileStatusEnum.choices, blank=True,
	                                     null=True)
	application_id_kyc_no = models.CharField(max_length=24, null=True, blank=True)
	referral_code = models.CharField(max_length=64, null=True, blank=True)
	service_team = models.ForeignKey(Organization, on_delete=models.CASCADE, null=True, blank=True)
	service_location = models.ForeignKey(ServiceLocations, on_delete=models.CASCADE, null=True, blank=True)
	version = models.CharField(max_length=2, default='V1')
	latitude = models.CharField(max_length=32, null=True, blank=True)
	longitude = models.CharField(max_length=32, null=True, blank=True)
	accuracy = models.CharField(max_length=24, null=True, blank=True)
	product = models.CharField(max_length=256, null=True, blank=True)
	robo_sdms_dedup = models.CharField(
		max_length=32, choices=RoboSdmsDedeupStatusEnum.choices,
		default=RoboSdmsDedeupStatusEnum.NOT_PROCESSED
	)
	status = FSMField(
		default=DomesticConnectionApplicationStatus.DOCUMENTS_UPLOADED,
		choices=DomesticConnectionApplicationStatus.choices
	)
	manual_operation_code = models.CharField(max_length=256, null=True, blank=True)
	legal_documents_upload_status = models.CharField(max_length=256, null=True, blank=True)
	sv = models.CharField(max_length=25, null=True, blank=True)
	documents_required_for_reupload = models.JSONField(null=True, blank=True)
	last_execution_state = models.CharField(max_length=50, null=True, blank=True)
	sync_with_sdms = models.BooleanField(default=True)
	applicant_verified = models.BooleanField(default=False)
	applicant_verified_on = models.DateTimeField(null=True, blank=True)
	audit_points = models.TextField(null=True, blank=True)
	ifsc_code = models.CharField(max_length=16, null=True, blank=True)
	bank_account_number = models.CharField(max_length=24, null=True, blank=True)
	scheme_onboarding_status = models.CharField(
		max_length=64, choices=SchemeOnboardingStatusEnum.choices, blank=True, null=True
	)
	filled_by = models.ForeignKey(User, on_delete=models.PROTECT, null=True, blank=True)
	service_area = models.ForeignKey(
		ServiceArea, on_delete=models.PROTECT, null=True, blank=True
	)
	customer_remarks = models.CharField(
		max_length=64, choices=OmcClearedCustomerRemarksEnum.choices,
		null=True, blank=True
	)
	scheduled_date = models.DateTimeField(null=True, blank=True)
	additional_remarks = models.TextField(null=True, blank=True)
	ekyc_cleared = models.BooleanField(default=False)
	robo_execution_failed_count = models.IntegerField(default=0, blank=True, null=True)


class FamilyMembers(models.Model):
	parent = models.ForeignKey(DomesticConnectionApplication, on_delete=models.CASCADE, related_name='family_members', null=True)
	name = models.CharField(max_length=50)
	relation = models.CharField(max_length=25, choices=FamilyMemberRelationEnum.choices)
	dob = models.DateField()
	uid_no = models.CharField(max_length=12, null=True, blank=True)
	uid_front_link = models.URLField()
	uid_back_link = models.URLField()
	# Fields To Store Original Tus Link
	uid_original_front_link = models.URLField(null=True, blank=True)
	uid_original_back_link = models.URLField(null=True, blank=True)
	uid_check_result = models.JSONField(blank=True, null=True)
	uid_front_compressed = models.BooleanField(default=False)
	uid_back_compressed = models.BooleanField(default=False)
	uid_front_file_size = models.CharField(max_length=16, default='0')
	uid_back_file_size = models.CharField(max_length=16, default='0')
	additional_details = models.JSONField(null=True, blank=True)
	is_valid_uid = models.BooleanField(null=True, blank=True)
	validated = models.BooleanField(default=False)

	def get_gender(self):
		if self.relation in (
				FamilyMemberRelationEnum.SELF,
				FamilyMemberRelationEnum.MOTHER,
				FamilyMemberRelationEnum.DAUGHTER
		):
			return "Female"
		else:
			return "Male"

	def download_links(self):
		html = '''
		<a href="{}" target="blank">View Ori.</a> UID Front <a href="{}{}" target="blank">Download Comp.</a><br><br>
		<a href="{}" target="blank">View Ori.</a> UID Back <a href="{}{}" target="blank">Download Comp.</a>
		'''.format(
			self.uid_front_link, settings.THUMBOR_URL, self.uid_front_link,
			self.uid_back_link, settings.THUMBOR_URL, self.uid_back_link,
		)
		return mark_safe(html)


class UjjwalaApplicationDocuments(models.Model):
	parent = models.ForeignKey(DomesticConnectionApplication, on_delete=models.CASCADE, related_name='documents', null=True)
	type = models.CharField(max_length=32, choices=DomesticConnectionApplicationDocumentsEnum.choices)
	link = models.URLField()
	# Fields To Store Original Tus Link
	original_link = models.URLField(null=True, blank=True)
	compressed = models.BooleanField(default=False)
	file_size = models.CharField(max_length=16, default='0')

	def download_links(self):
		html = '''
		<a href="{}" target="blank">Ori. File</a>&nbsp||&nbsp<a href="{}{}" target="blank">Download Comp.</a>
		'''.format(self.link, settings.THUMBOR_URL, self.link)
		return mark_safe(html)


class UserDocuments(models.Model):
	parent = models.ForeignKey(User, on_delete=models.CASCADE, related_name='domestic_documents', null=True)
	type = models.CharField(max_length=32, choices=UserDocumentsEnum.choices)
	link = models.URLField()
	# Fields To Store Original Tus Link
	original_link = models.URLField(null=True, blank=True)

	def download_links(self):
		html = '''
		<a href="{}" target="blank">View</a>&nbsp||&nbsp<a href="{}" target="blank">Download Comp.</a>
		'''.format(self.link, self.link)
		return mark_safe(html)


class PreInspection(models.Model):
	parent = models.OneToOneField(
		DomesticConnectionApplication, on_delete=models.PROTECT, related_name='pre_inspection'
	)
	created_on = models.DateTimeField(auto_now_add=True, null=True)
	updated_on = models.DateTimeField(auto_now=True, null=True)
	latitude = models.CharField(max_length=32, null=True, blank=True)
	longitude = models.CharField(max_length=32, null=True, blank=True)
	accuracy = models.CharField(max_length=24, null=True, blank=True)
	witness_name = models.CharField(max_length=256, null=True, blank=True)
	witness_mobile_number = models.CharField(max_length=10, null=True, blank=True)
	mechanic = models.ForeignKey(
		User, on_delete=models.PROTECT, null=True, blank=True, related_name="domestic_pre_inspection"
	)
	submitted_on = models.DateTimeField(null=True)
	type = models.CharField(max_length=32, choices=PreInspectionTypeEnum.choices, default=PreInspectionTypeEnum.SELF)


	status = FSMField(
		default=PreInspectionStatusEnum.ALLOCATED,
		choices=PreInspectionStatusEnum.choices
	)

	def mechanic_name(self):
		if self.mechanic:
			return self.mechanic.get_full_name()
		else:
			self.parent.name


class PreInspectionDocuments(models.Model):
	parent = models.ForeignKey(PreInspection, on_delete=models.CASCADE, related_name='documents', null=True)
	type = models.CharField(max_length=32, choices=DomesticConnectionApplicationDocumentsEnum.choices)
	compressed = models.BooleanField(default=False)
	file_size = models.CharField(max_length=16, default='0')
	link = models.URLField(null=True, blank=True)
	# Fields To Store Original Tus Link
	original_link = models.URLField(null=True, blank=True)

	def download_links(self):
		html = '''
		<a href="{}" target="blank">View File</a>
		'''.format(self.link)
		return mark_safe(html)


class ConnectionDisbursement(models.Model):
	parent = models.OneToOneField(
		DomesticConnectionApplication, on_delete=models.PROTECT, related_name='connection_disbursement'
	)
	created_on = models.DateTimeField(auto_now_add=True, null=True)
	updated_on = models.DateTimeField(auto_now=True, null=True)
	# sv_uploaded = models.BooleanField(default=False)
	# sv_uploaded_on = models.DateTimeField(null=True, blank=True)
	location_data = models.JSONField(null=True, blank=True)
	walk_in_date = models.DateTimeField(null=True, blank=True)
	sequence = models.CharField(max_length=16, null=True, blank=True)
	mechanic = models.ForeignKey(
		User, on_delete=models.PROTECT, null=True, blank=True, related_name="domestic_connection_disbursement"
	)
	material_delivered_on = models.DateTimeField(null=True, blank=True)
	first_cylinder_delivered_on = models.DateTimeField(null=True, blank=True)
	second_cylinder_delivered_on = models.DateTimeField(null=True, blank=True)
	dac_code = models.CharField(max_length=4, null=True, blank=True)
	pending_quantity = models.IntegerField(default=0)
	item_code = models.CharField(default='FC5', max_length=52)
	installation_type = models.CharField(
		max_length=32, choices=InstallationTypeEnum.choices, default=InstallationTypeEnum.MECHANIC
	)
	status = FSMField(
		default=ConnectionDisbursementStatusEnum.LEGAL_DOCUMENTS_PENDING,
		choices=ConnectionDisbursementStatusEnum.choices
	)


class ConnectionDisbursementDocuments(models.Model):
	parent = models.ForeignKey(ConnectionDisbursement, on_delete=models.CASCADE, related_name='documents', null=True)
	type = models.CharField(max_length=32, choices=DomesticConnectionApplicationDocumentsEnum.choices)
	link = models.URLField()
	# Fields To Store Original Tus Link
	original_link = models.URLField(null=True, blank=True)
	compressed = models.BooleanField(default=False)
	file_size = models.CharField(max_length=16, default='0')

	def download_links(self):
		html = '''
		<a href="{}" target="blank">View File</a>
		'''.format(self.link)
		return mark_safe(html)
