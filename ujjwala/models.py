import datetime
import re

import requests
from django.conf import settings
from django.contrib.auth.models import User
from django.contrib.contenttypes.models import ContentType
from django.core import signals
from django.db import models
from django.dispatch import receiver
from django.template import loader
from django.urls import reverse
from django.utils.safestring import mark_safe
from django_currentuser.middleware import get_current_user
from django_fsm import FSMField, transition, GET_STATE
from django_fsm_log.decorators import fsm_log_description, fsm_log_by
from organizations.models import Organization

from communication_log.models import CommunicationLog
from teams.models import ServiceLocations
from ujjwala.communication_models import UjjwalaWhatsappCommunication
from ujjwala.enums import MaritalStatusEnum, ResidentialStatusEnum, UjjwalaUidMobileStatusEnum, \
	UjjwalaV2ApplicationStatus, UjjwalaApplicationDocumentsEnum, FamilyMemberRelationEnum, \
	RejectionTypeEnum, RoboSdmsDedeupStatusEnum, UserDocumentsEnum, OtpStatusEnum, PreInspectionStatusEnum, \
	ConnectionDisbursementStatusEnum, PreInspectionTypeEnum
from ujjwala.forms import UjjwalaLegalDocumentsUpload, \
	ConnectionStatusApproved, ApplicationRejected, \
	EkycAccepted, PreInspectionReviewForm, PreInspectionReviewAdminForm, LegalDocumentsUpload, \
	LegalDocumentsReviewAdminForm, NicUpdateAddressForm
from ujjwala.ujjwala_functions import download_ujjwala_physical_legal_docs
from utils.global_functions import move_file_to_minio_bucket, upload_file_to_minio_bucket, old_address_to_description


class UjjwalaV2Application(models.Model, UjjwalaWhatsappCommunication):
	created_on = models.DateTimeField(auto_now_add=True)
	updated_on = models.DateTimeField(auto_now=True)
	sdms_last_updated_on = models.DateTimeField(null=True)
	rejection_type = models.CharField(max_length=64, choices=RejectionTypeEnum.choices, null=True, blank=True)
	marital_status = models.CharField(max_length=25, choices=MaritalStatusEnum.choices)
	residential_status = models.CharField(max_length=25, choices=ResidentialStatusEnum.choices, blank=True, null=True)
	name = models.CharField(max_length=50)
	address = models.TextField(null=True, blank=True)
	address_json = models.JSONField(null=True, blank=True)
	contact_mobile = models.CharField(max_length=10)
	consumer_id = models.CharField(max_length=16, null=True, blank=True)
	uid_linked_mobile = models.CharField(max_length=10, null=True, blank=True)
	sdms_mobile_number = models.CharField(max_length=10, null=True, blank=True)
	uid_mobile_status = models.CharField(max_length=25, choices=UjjwalaUidMobileStatusEnum.choices, blank=True, null=True)
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
		max_length=25, choices=RoboSdmsDedeupStatusEnum.choices,
		default=RoboSdmsDedeupStatusEnum.NOT_PROCESSED
	)
	status = FSMField(
		default=UjjwalaV2ApplicationStatus.DOCUMENTS_UPLOADED,
		choices=UjjwalaV2ApplicationStatus.choices
	)
	manual_operation_code = models.CharField(max_length=25, null=True, blank=True)
	legal_documents_upload_status = models.CharField(max_length=25, null=True, blank=True)
	sv = models.CharField(max_length=25, null=True, blank=True)
	documents_required_for_reupload = models.JSONField(null=True, blank=True)
	last_execution_state = models.CharField(max_length=50, null=True, blank=True)
	pre_inspection_accepted = models.OneToOneField("PreInspection", on_delete=models.CASCADE, null=True, blank=True)
	sync_with_sdms = models.BooleanField(default=True)
	applicant_verified = models.BooleanField(default=False)
	applicant_verified_on = models.DateTimeField(null=True, blank=True)
	audit_points = models.TextField(null=True, blank=True)

	class Meta:
		permissions = (
			("can_edit_record_transition", "Can edit record transition"),
			("can_do_ekyc", "Can do ekyc"),
			("can_upload_legal_docs", "Can upload legal docs"),
			("can_approve_connection", "Can approve connection"),
			("can_reject_connection", "Can reject connection"),
			("can_collect_legal_documents", "Can collect legal documents"),
			("can_release_connection", "Can release connection"),
			("can_upload_post_installation", "Can upload post installation"),
			("can_reject_application", "Can reject application")
		)

	def pre_inspection_form(self):
		# if self.status == UjjwalaV2ApplicationStatus.PRE_INSPECTION_SUBMITTED:
		# 	template = loader.get_template("ujjwala/pre_inspection_form_view.html")
		# 	html = template.render({'obj': self})
		# 	return mark_safe(html)
		return mark_safe("")

	def whatsapp_nic_error_update_address(self):
		url = reverse('ujjwala:whatsapp_nic_error_update_address', kwargs={'pk': self.pk})
		html = '''
		<a href="{}">Whatsapp Nic Error Update Address</a>
		'''.format(url)
		return mark_safe(html)


	@property
	def formatted_address(self):
		if self.version in ('V1', 'V2'):
			return self.address
		self.address_json['city'] = 'Ludhiana'
		return ' '.join([self.address_json.get(r, '') for r in [
			'room_no', 'floor', 'street_no', 'landmark', 'village', 'post_office', 'pincode'
		]])

	@property
	def all_contacts(self):
		phones = set([i for i in [
			self.contact_mobile,
			self.uid_linked_mobile,
			self.sdms_mobile_number
		] if i])
		return list(phones)

	def document_self(self):
		return self.documents.filter(type=UjjwalaApplicationDocumentsEnum.CUSTOMER_PHOTO).first().link

	def document_kitchen_photo(self):
		return self.documents.filter(type=UjjwalaApplicationDocumentsEnum.KITCHEN_PHOTO).first().link

	def document_customer_in_kitchen(self):
		return self.documents.filter(type=UjjwalaApplicationDocumentsEnum.CUSTOMER_IN_KITCHEN).first().link

	def document_mechanic_photo(self):
		return self.documents.filter(type=UjjwalaApplicationDocumentsEnum.MECHANIC_PHOTO).first().link

	def document_customer_signature(self):
		return self.documents.filter(type=UjjwalaApplicationDocumentsEnum.CUSTOMER_SIGNATURE).first().link

	def document_witness_photo(self):
		return self.documents.filter(type=UjjwalaApplicationDocumentsEnum.WITNESS_PHOTO).first().link

	def physical_legal_document_link(self):
		record = self.pre_inspection_accepted.documents.filter(
			type=UjjwalaApplicationDocumentsEnum.PHYSICAL_LEGAL_DOCUMENT
		).first()
		if record: return record.link
		return ''

	def is_sv_uploaded(self):
		connection_disbursement = ConnectionDisbursement.objects.filter(parent_id=self.id).first()
		connection_disbursement_invitation = ConnectionDisbursementInvitation.objects.filter(
			parent_id=connection_disbursement.id
		).first()
		if connection_disbursement_invitation:
			if connection_disbursement_invitation.sv_link:
				return "SV Uploaded"
		return "SV Not Uploaded"

	def get_consumer_number(self):
		return re.sub('([0-9]{2})0*([0-9]*)', '\\1\\2', self.consumer_id)

	def get_sdms_consumer_details(self):
		return self.family_members.get(relation='SELF').uid_check_result

	def get_physical_legal_documents_status(self):
		connection_disbursement = ConnectionDisbursement.objects.filter(parent_id=self.id).first()
		if connection_disbursement:
			if connection_disbursement.status == ConnectionDisbursementStatusEnum.LEGAL_DOCUMENTS_PENDING:
				return "Form A B C not uploaded"
			elif connection_disbursement.status == ConnectionDisbursementStatusEnum.LEGAL_DOCUMENTS_REVIEW:
				return "Form A B C uploaded, Review pending"
			elif connection_disbursement.status == ConnectionDisbursementStatusEnum.LEGAL_DOCUMENTS_ACCEPTED:
				return "Form A B C uploaded and accepted"
			else:
				return "Connection Disbursement Status: {}".format(connection_disbursement.status)
		else:
			return "Connection Disbursement not initiated. Make sure Pre Inspection is done and accepted"


	@fsm_log_description
	@fsm_log_by
	@transition(
		field=status,
		source=UjjwalaV2ApplicationStatus.DOCUMENTS_UPLOADED,
		target=UjjwalaV2ApplicationStatus.EKYC_ACCEPTED,
		custom=dict(short_description='E-KYC Accepted', admin=True, form=EkycAccepted),
		permission='ujjwala.can_do_ekyc'
	)
	def ekyc_accepted_or_rejected(self, *args, **kwargs):
		pass

	@fsm_log_description
	@fsm_log_by
	@transition(
		field=status,
		source=[
			UjjwalaV2ApplicationStatus.DOCUMENTS_UPLOADED,
			UjjwalaV2ApplicationStatus.DOCUMENTS_REUPLOAD,
			UjjwalaV2ApplicationStatus.LEGAL_DOCUMENTS_UPLOAD,
			UjjwalaV2ApplicationStatus.EKYC_ACCEPTED,
			UjjwalaV2ApplicationStatus.AUDIT_APPLICATION
		],
		target=UjjwalaV2ApplicationStatus.APPLICATION_REJECTED,
		custom=dict(short_description='Reject Application', admin=True, form=ApplicationRejected),
		permission='ujjwala.can_reject_application'
	)
	def application_rejected(self, *args, **kwargs):
		pass

	@fsm_log_description
	@fsm_log_by
	@transition(
		field=status,
		source=[
			UjjwalaV2ApplicationStatus.EKYC_ACCEPTED,
			UjjwalaV2ApplicationStatus.DO_MANUAL_OPERATION,
			UjjwalaV2ApplicationStatus.MANUAL_LEGAL_DOCUMENTS_UPLOAD,
		],
		target=UjjwalaV2ApplicationStatus.LEGAL_DOCUMENTS_UPLOAD,
		custom=dict(
			short_description='Legal Documents Upload', admin=True, form=LegalDocumentsUpload
		),
		permission='ujjwala.can_upload_legal_docs',
	)
	def legal_documents_upload(self, *args, **kwargs):
		pass

	@fsm_log_description
	@fsm_log_by
	@transition(
		field=status,
		source=UjjwalaV2ApplicationStatus.EKYC_ACCEPTED,
		target=UjjwalaV2ApplicationStatus.MANUAL_LEGAL_DOCUMENTS_UPLOAD,
		custom=dict(short_description='Update Legal Documents', admin=False),
	)
	def robo_manual_legal_documents_upload(self, *args, **kwargs):
		self.manual_operation_code = kwargs.get('manual_operation_code')

	@fsm_log_description
	@fsm_log_by
	@transition(
		field=status,
		source=UjjwalaV2ApplicationStatus.EKYC_ACCEPTED,
		target=UjjwalaV2ApplicationStatus.DO_MANUAL_OPERATION,
		custom=dict(short_description='Do Manual Operation', admin=False),
	)
	def do_manual_operations(self, *args, **kwargs):
		self.manual_operation_code = kwargs.get('manual_operation_code')


	@fsm_log_description
	@fsm_log_by
	@transition(
		field=status,
		source=UjjwalaV2ApplicationStatus.LEGAL_DOCUMENTS_UPLOAD,
		target=UjjwalaV2ApplicationStatus.OMC_CLEARED,
		custom=dict(
			short_description='Set As OMC Cleared', admin=True, form=ConnectionStatusApproved
		),
		permission='ujjwala.can_approve_connection',
	)
	def transition_omc_clear(self, *args, **kwargs):
		pass

	@fsm_log_description
	@fsm_log_by
	@transition(
		field=status,
		source=UjjwalaV2ApplicationStatus.LEGAL_DOCUMENTS_UPLOAD,
		target=UjjwalaV2ApplicationStatus.OMC_REJECTED,
		custom=dict(
			short_description='Set As OMC Rejected', admin=True
		),
		permission='ujjwala.can_approve_connection',
	)
	def transition_omc_reject(self, *args, **kwargs):
		pass

	@fsm_log_description
	@fsm_log_by
	@transition(
		field=status,
		source=UjjwalaV2ApplicationStatus.OMC_CLEARED,
		target=UjjwalaV2ApplicationStatus.NIC_CLEARED,
		custom=dict(
			short_description='Set As NIC Cleared', admin=True, form=ConnectionStatusApproved
		),
		permission='ujjwala.can_approve_connection',
	)
	def transition_nic_cleared(self, *args, **kwargs):
		pass

	# @fsm_log_description
	# @fsm_log_by
	# @transition(
	# 	field=status,
	# 	source=UjjwalaV2ApplicationStatus.NIC_CLEARED,
	# 	target=UjjwalaV2ApplicationStatus.PRE_INSPECTION_ACCEPTED,
	# 	custom=dict(
	# 		short_description='Pre Inspection Accepted', admin=True
	# 	),
	# )
	# def transition_pre_inspection_accepted(self, *args, **kwargs):
	# 	pre_inspection_id = kwargs.get('pre_inspection_id')
	# 	pre_inspection = PreInspection.objects.get(pk=pre_inspection_id)
	# 	self.latitude = pre_inspection.latitude
	# 	self.longitude = pre_inspection.longitude
	# 	self.accuracy = pre_inspection.accuracy
	# 	self.pre_inspection_accepted = pre_inspection
	# 	self.save()
	# 	self.event_legal_documents_upload_channel_whatsapp()

	@fsm_log_description
	@fsm_log_by
	@transition(
		field=status,
		source=UjjwalaV2ApplicationStatus.OMC_CLEARED,
		target=UjjwalaV2ApplicationStatus.NIC_ERROR,
		custom=dict(
			short_description='Set As NIC Error', admin=True, form=ConnectionStatusApproved
		),
		permission='ujjwala.can_approve_connection',
	)
	def transition_nic_error(self, *args, **kwargs):
		self.manual_operation_code = kwargs.get('error_code')


	@old_address_to_description
	@fsm_log_description
	@fsm_log_by
	@transition(
		field=status,
		source=UjjwalaV2ApplicationStatus.NIC_ERROR,
		target=UjjwalaV2ApplicationStatus.NIC_ERROR_UPDATE_ADDRESS,
		custom=dict(
			short_description='Update Address', admin=True, form=NicUpdateAddressForm
		),
		permission='ujjwala.can_approve_connection',
	)
	def transition_nic_address_updated(self, *args, **kwargs):
		self.address_json = kwargs['address_json']

	# @fsm_log_description
	# @fsm_log_by
	# @transition(
	# 	field=status,
	# 	source=UjjwalaV2ApplicationStatus.PRE_INSPECTION_ACCEPTED,
	# 	target=UjjwalaV2ApplicationStatus.LEGAL_DOCUMENTS_COLLECTED,
	# 	custom=dict(
	# 		short_description='Legal Documents Collection', admin=True,
	# 	),
	# 	permission='ujjwala.can_approve_connection',
	# )
	# def transition_legal_documents_collected(self, *args, **kwargs):
	# 	pass

	@fsm_log_description
	@fsm_log_by
	@transition(
		field=status,
		source=UjjwalaV2ApplicationStatus.NIC_CLEARED,
		target=UjjwalaV2ApplicationStatus.READY_FOR_DISBURSEMENT,
		custom=dict(
			short_description='Ready For Disbursement', admin=True,
		),
		permission='ujjwala.can_approve_connection',
	)
	def transition_ready_for_disbrusement(self, *args, **kwargs):
		pass

	@fsm_log_description
	@fsm_log_by
	@transition(
		field=status,
		source=[
			UjjwalaV2ApplicationStatus.READY_FOR_DISBURSEMENT,
			UjjwalaV2ApplicationStatus.NIC_CLEARED
		],
		target=UjjwalaV2ApplicationStatus.MATERIAL_DELIVERED,
		custom=dict(
			short_description='Material Delivered', admin=False,
		),
	)
	def transition_material_delivered(self, *args, **kwargs):
		pass

	@fsm_log_description
	@fsm_log_by
	@transition(
		field=status,
		source=UjjwalaV2ApplicationStatus.MATERIAL_DELIVERED,
		target=UjjwalaV2ApplicationStatus.INSTALLED,
		custom=dict(
			short_description='Material Installed', admin=False,
		),
	)
	def transition_installed(self, *args, **kwargs):
		pass

	@fsm_log_description
	@fsm_log_by
	@transition(
		field=status,
		source=[
			UjjwalaV2ApplicationStatus.DOCUMENTS_UPLOADED,
			UjjwalaV2ApplicationStatus.EKYC_ACCEPTED,
		],
		target=UjjwalaV2ApplicationStatus.AUDIT_APPLICATION,
		custom=dict(
			short_description='Audit Application', admin=False,
		),
	)
	def transition_audit_application(self, audit_points, *args, **kwargs):
		self.last_execution_state = self.status
		self.audit_points = audit_points

	@fsm_log_description
	@fsm_log_by
	@transition(
		field=status,
		source=UjjwalaV2ApplicationStatus.AUDIT_APPLICATION,
		target=GET_STATE(
			lambda self, **kwargs: self.last_execution_state,
		),
		custom=dict(
			short_description='Audit Accepted', admin=True,
		),
	)
	def transition_audit_accepted(self, audit_points, *args, **kwargs):
		self.last_execution_state = self.status
		self.audit_points = audit_points

	@fsm_log_description
	@fsm_log_by
	@transition(
		field=status,
		source=[
			UjjwalaV2ApplicationStatus.DOCUMENTS_UPLOADED,
			UjjwalaV2ApplicationStatus.DOCUMENTS_REUPLOAD,
			UjjwalaV2ApplicationStatus.EKYC_ACCEPTED,
			UjjwalaV2ApplicationStatus.LEGAL_DOCUMENTS_UPLOAD
		],
		target=UjjwalaV2ApplicationStatus.EDIT_APPLICATION,
		custom=dict(
			short_description='Edit Application', admin=True
		),
		permission='ujjwala.change_ujjwalav2application',
	)
	def edit(self, *args, **kwargs):
		self.last_execution_state = self.status

	@fsm_log_description
	@fsm_log_by
	@transition(
		field=status,
		source=UjjwalaV2ApplicationStatus.EDIT_APPLICATION,
		target=GET_STATE(
			lambda self, **kwargs: self.last_execution_state,
		),
		custom=dict(
			short_description='Update Edits To Application', admin=True
		),
	)
	def restore_edit(self, *args, **kwargs):
		pass

	def submit(self, *args, **kwargs):
		"""
		Called when application is uploaded via api to change state to submitted
		"""
		self.event_submit_channel_whatsapp()

	def event_connection_accepted_whatsapp(self):
		pass


class FamilyMembers(models.Model):
	parent = models.ForeignKey(UjjwalaV2Application, on_delete=models.CASCADE, related_name='family_members', null=True)
	name = models.CharField(max_length=50)
	relation = models.CharField(max_length=25, choices=FamilyMemberRelationEnum.choices)
	dob = models.DateField()
	uid_no = models.CharField(max_length=12, null=True, blank=True)
	uid_front_link = models.URLField()
	uid_back_link = models.URLField()
	uid_check_result = models.JSONField(blank=True, null=True)
	uid_front_compressed = models.BooleanField(default=False)
	uid_back_compressed = models.BooleanField(default=False)
	uid_front_file_size = models.CharField(max_length=16, default='0')
	uid_back_file_size = models.CharField(max_length=16, default='0')
	additional_details = models.JSONField(null=True, blank=True)
	is_valid_uid = models.BooleanField(null=True, blank=True)

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
		'''.format(self.uid_front_link, settings.THUMBOR_URL, self.uid_front_link,
		           self.uid_back_link, settings.THUMBOR_URL, self.uid_back_link, )
		return mark_safe(html)


class UjjwalaApplicationDocuments(models.Model):
	parent = models.ForeignKey(UjjwalaV2Application, on_delete=models.CASCADE, related_name='documents', null=True)
	type = models.CharField(max_length=32, choices=UjjwalaApplicationDocumentsEnum.choices)
	link = models.URLField()
	compressed = models.BooleanField(default=False)
	file_size = models.CharField(max_length=16, default='0')

	def download_links(self):
		html = '''
		<a href="{}" target="blank">Ori. File</a>&nbsp||&nbsp<a href="{}{}" target="blank">Download Comp.</a>
		'''.format(self.link, settings.THUMBOR_URL, self.link)
		return mark_safe(html)


class UserDocuments(models.Model):
	parent = models.ForeignKey(User, on_delete=models.CASCADE, related_name='documents', null=True)
	type = models.CharField(max_length=32, choices=UserDocumentsEnum.choices)
	link = models.URLField()

	def download_links(self):
		html = '''
		<a href="{}" target="blank">View</a>&nbsp||&nbsp<a href="{}" target="blank">Download Comp.</a>
		'''.format(self.link, self.link)
		return mark_safe(html)


class PreInspection(models.Model):
	parent = models.ForeignKey(
		UjjwalaV2Application, on_delete=models.PROTECT, related_name='pre_inspection'
	)
	created_on = models.DateTimeField(auto_now_add=True, null=True)
	updated_on = models.DateTimeField(auto_now=True, null=True)
	latitude = models.CharField(max_length=32, null=True, blank=True)
	longitude = models.CharField(max_length=32, null=True, blank=True)
	accuracy = models.CharField(max_length=24, null=True, blank=True)
	witness_name = models.CharField(max_length=256, null=True, blank=True)
	witness_mobile_number = models.CharField(max_length=10, null=True, blank=True)
	mechanic = models.ForeignKey(User, on_delete=models.PROTECT, null=True, blank=True)
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

	def document_kitchen_photo(self):
		return self.documents.filter(type=UjjwalaApplicationDocumentsEnum.KITCHEN_PHOTO).first().link

	def document_main_gate_photo(self):
		return self.documents.filter(type=UjjwalaApplicationDocumentsEnum.MAIN_GATE).first().link

	@fsm_log_description
	@fsm_log_by
	@transition(
		field=status,
		source=[
			PreInspectionStatusEnum.ALLOCATED,
			PreInspectionStatusEnum.REJECTED
		],
		target=PreInspectionStatusEnum.CHANGE_ADDRESS,
		custom=dict(short_description='Verify Otp', admin=False),
	)
	def pre_inspection_otp_verified(self, *args, **kwargs):
		# Deleting existing documents
		if self.status == PreInspectionStatusEnum.REJECTED:
			self.documents.delete()


	@fsm_log_description
	@fsm_log_by
	@transition(
		field=status,
		source=PreInspectionStatusEnum.CHANGE_ADDRESS,
		target=PreInspectionStatusEnum.KITCHEN_PHOTO,
		custom=dict(short_description='Change Address', admin=False),
	)
	def pre_inspection_change_address(self, *args, **kwargs):
		pass

	@fsm_log_description
	@fsm_log_by
	@transition(
		field=status,
		source=PreInspectionStatusEnum.KITCHEN_PHOTO,
		target=PreInspectionStatusEnum.PREVIEW_INSPECTION,
		custom=dict(short_description='Upload Main Gate Pic & Location', admin=False),
	)
	def pre_inspection_kitchen_photo_uploaded_skip_safety(self, *args, **kwargs):
		pass

	@fsm_log_description
	@fsm_log_by
	@transition(
		field=status,
		source=PreInspectionStatusEnum.KITCHEN_PHOTO,
		target=PreInspectionStatusEnum.SAFETY_AUDIO,
		custom=dict(short_description='Upload Safety Audio', admin=False),
	)
	def pre_inspection_kitchen_photo_uploaded(self, *args, **kwargs):
		pass

	@fsm_log_description
	@fsm_log_by
	@transition(
		field=status,
		source=PreInspectionStatusEnum.SAFETY_AUDIO,
		target=PreInspectionStatusEnum.PREVIEW_INSPECTION,
		custom=dict(short_description='Upload Main Gate Pic & Location', admin=False),
	)
	def pre_inspection_safety_audio_uploaded(self, *args, **kwargs):
		pass

	@fsm_log_description
	@fsm_log_by
	@transition(
		field=status,
		source=PreInspectionStatusEnum.PREVIEW_INSPECTION,
		target=PreInspectionStatusEnum.SUBMITTED,
		custom=dict(short_description='Submit Pre-Inspection', admin=False),
	)
	def transition_pre_inspection_submit(self, *args, **kwargs):
		self.submitted_on = datetime.datetime.now()
		self.save()

	@fsm_log_description
	@fsm_log_by
	@transition(
		field=status,
		source=PreInspectionStatusEnum.SUBMITTED,
		target=GET_STATE(
			lambda self, **kwargs: \
					PreInspectionStatusEnum.ACCEPTED \
							if kwargs.get("review_status") == 'ACCEPTED' \
							else PreInspectionStatusEnum.REJECTED,
			states=[
				PreInspectionStatusEnum.ACCEPTED,
				PreInspectionStatusEnum.REJECTED
			]
		),
		custom=dict(
			short_description='Pre-Inspection Review', admin=True, form=PreInspectionReviewAdminForm
		),
	)
	def pre_inspection_review(self, *args, **kwargs):
		if kwargs.get('review_status') == 'ACCEPTED':
			ConnectionDisbursement.objects.create(
				parent=self.parent,
				mechanic=self.mechanic
			)
			# Bucket Name: ujjwaladocuments
			physical_legal_document = download_ujjwala_physical_legal_docs(self.parent)
			upload_url = upload_file_to_minio_bucket(
				physical_legal_document,
				"ujjwaladocuments",
				"ujjwala_{}_physical_legal_document".format(self.parent_id)
			)
			PreInspectionDocuments.objects.create(
				type=UjjwalaApplicationDocumentsEnum.PHYSICAL_LEGAL_DOCUMENT,
				link=upload_url,
				parent=self
			)
			# self.parent.transition_pre_inspection_accepted(
			# 	pre_inspection_id=self.pk, by=get_current_user()
			# )
			# self.parent.save()
			self.parent.latitude = self.latitude
			self.parent.longitude = self.longitude
			self.parent.accuracy = self.accuracy
			self.parent.pre_inspection_accepted = self
			self.parent.save()
			self.parent.event_legal_documents_upload_channel_whatsapp()
		else:
			if self.type == PreInspectionTypeEnum.SELF:
				# Send Whatsapp Message
				pass


class PreInspectionDocuments(models.Model):
	parent = models.ForeignKey(PreInspection, on_delete=models.CASCADE, related_name='documents', null=True)
	type = models.CharField(max_length=32, choices=UjjwalaApplicationDocumentsEnum.choices)
	link = models.URLField()
	compressed = models.BooleanField(default=False)
	file_size = models.CharField(max_length=16, default='0')

	def download_links(self):
		html = '''
		<a href="{}" target="blank">View File</a>
		'''.format(self.link)
		return mark_safe(html)


class Evykati(models.Model):
	parent = models.ForeignKey(
		UjjwalaV2Application, on_delete=models.PROTECT, related_name='evyakti'
	)
	information = models.JSONField(null=True, blank=True)


class ConnectionDisbursement(models.Model):
	parent = models.OneToOneField(
		UjjwalaV2Application, on_delete=models.PROTECT, related_name='connection_disbursement'
	)
	created_on = models.DateTimeField(auto_now_add=True, null=True)
	updated_on = models.DateTimeField(auto_now=True, null=True)
	# sv_uploaded = models.BooleanField(default=False)
	# sv_uploaded_on = models.DateTimeField(null=True, blank=True)
	location_data = models.JSONField(null=True, blank=True)
	walk_in_date = models.DateTimeField(null=True, blank=True)
	sequence = models.CharField(max_length=16, null=True, blank=True)
	mechanic = models.ForeignKey(User, on_delete=models.PROTECT, null=True, blank=True)

	status = FSMField(
		default=ConnectionDisbursementStatusEnum.LEGAL_DOCUMENTS_PENDING,
		choices=ConnectionDisbursementStatusEnum.choices
	)

	def invite(self):
		invite_url = reverse('admin:ujjwala_connectiondisbursement_invite', kwargs={'pk': self.pk})
		html = '''
		<a href="{}">Send Invitation</a>
		'''.format(invite_url)
		return mark_safe(html)


	def legal_document_upload_link(self):
		html = '''
		<a href="https://dca.arungas.com/ujjwala/portal/legal_documents_upload/{}/" target="blank">Upload Physical Legal Documents</a>				
		'''.format(self.pk)
		return mark_safe(html)

	def valid_sv_link(self):
		valid_invitation = self.invitation.filter(parent=self).first()

		if valid_invitation:
			return valid_invitation.sv_link


	@fsm_log_description
	@fsm_log_by
	@transition(
		field=status,
		source=ConnectionDisbursementStatusEnum.LEGAL_DOCUMENTS_PENDING,
		target=ConnectionDisbursementStatusEnum.LEGAL_DOCUMENTS_REVIEW,
		custom=dict(short_description='Legal Documents Upload', admin=False),
	)
	def transition_legal_documents_uploaded(self, *args, **kwargs):
		pass

	@fsm_log_description
	@fsm_log_by
	@transition(
		field=status,
		source=ConnectionDisbursementStatusEnum.LEGAL_DOCUMENTS_REVIEW,
		target=GET_STATE(
					lambda self, **kwargs: \
							ConnectionDisbursementStatusEnum.LEGAL_DOCUMENTS_ACCEPTED \
									if kwargs.get('review_status') == 'ACCEPTED' \
									else ConnectionDisbursementStatusEnum.LEGAL_DOCUMENTS_PENDING,
					states=[
						ConnectionDisbursementStatusEnum.LEGAL_DOCUMENTS_ACCEPTED,
						ConnectionDisbursementStatusEnum.LEGAL_DOCUMENTS_PENDING
					]
				),
		custom=dict(
			short_description='Legal Documents Review', admin=True, form=LegalDocumentsReviewAdminForm
		),
	)
	def transition_legal_documents_reviewed(self, *args, **kwargs):
		if kwargs.get('review_status') == 'ACCEPTED':
			pass
			# self.parent.transition_legal_documents_collected(connection_disbursement_id=self.pk)
			# self.parent.save()
		else:
			self.documents.all().delete()

	@fsm_log_description
	@fsm_log_by
	@transition(
		field=status,
		source=ConnectionDisbursementStatusEnum.LEGAL_DOCUMENTS_ACCEPTED,
		target=ConnectionDisbursementStatusEnum.SV_LABEL_PRINT,
		custom=dict(short_description='SV & Label Print', admin=False),
	)
	def transition_sv_label_printed(self, *args, **kwargs):
		pass

	@fsm_log_description
	@fsm_log_by
	@transition(
		field=status,
		source=ConnectionDisbursementStatusEnum.SV_LABEL_PRINT,
		target=ConnectionDisbursementStatusEnum.SOCIAL_MEDIA_UPDATES,
		custom=dict(short_description='Social Media Updates', admin=False),
	)
	def transition_social_media_updates_done(self, *args, **kwargs):
		pass

	@fsm_log_description
	@fsm_log_by
	@transition(
		field=status,
		source=ConnectionDisbursementStatusEnum.SOCIAL_MEDIA_UPDATES,
		# target=ConnectionDisbursementStatusEnum.DISBURSEMENT_PHOTO_UPLOAD,
		target=ConnectionDisbursementStatusEnum.MATERIAL_DELIVERY_OTP_VERIFIED,
		custom=dict(short_description='Material Delivery OTP Verification', admin=False),
	)
	def transition_material_delivery_otp_verified(self, *args, **kwargs):
		pass

	@fsm_log_description
	@fsm_log_by
	@transition(
		field=status,
		source=ConnectionDisbursementStatusEnum.MATERIAL_DELIVERY_OTP_VERIFIED,
		target=ConnectionDisbursementStatusEnum.MATERIAL_DELIVERED,
		custom=dict(short_description='Material Delivery', admin=False),
	)
	def transition_material_delivered(self, *args, **kwargs):
		self.parent.transition_material_delivered(by=get_current_user())
		self.parent.save()

	@fsm_log_description
	@fsm_log_by
	@transition(
		field=status,
		source=ConnectionDisbursementStatusEnum.MATERIAL_DELIVERED,
		target=ConnectionDisbursementStatusEnum.INSTALLATION_MAIN_GATE,
		custom=dict(short_description='Upload Installation Kitchen Photo', admin=False),
	)
	def transition_installation_kitchen_upload(self, *args, **kwargs):
		pass

	@fsm_log_description
	@fsm_log_by
	@transition(
		field=status,
		source=ConnectionDisbursementStatusEnum.INSTALLATION_MAIN_GATE,
		target=ConnectionDisbursementStatusEnum.INSTALLATION_UPLOADED,
		custom=dict(short_description='Upload Main Gate Photo', admin=False),
	)
	def transition_main_gate(self, *args, **kwargs):
		self.parent.transition_installed(by=get_current_user())
		self.parent.save()
		pass


class ConnectionDisbursementDocuments(models.Model):
	parent = models.ForeignKey(ConnectionDisbursement, on_delete=models.CASCADE, related_name='documents', null=True)
	type = models.CharField(max_length=32, choices=UjjwalaApplicationDocumentsEnum.choices)
	link = models.URLField()
	compressed = models.BooleanField(default=False)
	file_size = models.CharField(max_length=16, default='0')

	def download_links(self):
		html = '''
		<a href="{}" target="blank">View File</a>
		'''.format(self.link)
		return mark_safe(html)


class ConnectionDisbursementInvitation(models.Model):
	parent = models.ForeignKey(ConnectionDisbursement, on_delete=models.CASCADE, related_name='invitation', null=True)
	invited_for = models.DateTimeField(null=True, blank=True)
	invite_accepted = models.BooleanField(default=False)
	sv_link = models.URLField(null=True, blank=True)
	sv_uploaded_on = models.DateTimeField(null=True, blank=True)
	booking_id = models.CharField(max_length=16, null=True, blank=True)
	status = models.CharField(max_length=32, default='VALID')

	def download_links(self):
		html = '''
		<a href="{}" target="blank">View File</a>
		'''.format(self.sv_link)
		return mark_safe(html)
