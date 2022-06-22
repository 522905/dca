import datetime

import requests
from django.conf import settings
from django.contrib.auth.models import User
from django.contrib.contenttypes.models import ContentType
from django.core import signals
from django.db import models
from django.dispatch import receiver
from django.template import loader
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
	ConnectionDisbursementStatusEnum
from ujjwala.forms import UjjwalaLegalDocumentsUpload, \
	ConnectionStatusApproved, ApplicationRejected, \
	EkycAccepted, PreInspectionReviewForm, PreInspectionReviewAdminForm, LegalDocumentsUpload, \
	LegalDocumentsReviewAdminForm
from ujjwala.ujjwala_functions import download_ujjwala_physical_legal_docs
from utils.global_functions import move_file_to_minio_bucket, upload_file_to_minio_bucket


class UjjwalaV2Application(models.Model, UjjwalaWhatsappCommunication):
	created_on = models.DateTimeField(auto_now_add=True)
	updated_on = models.DateTimeField(auto_now=True)
	sdms_last_updated_on = models.DateTimeField(null=True)
	rejection_type = models.CharField(max_length=25, choices=RejectionTypeEnum.choices, null=True, blank=True)
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
	pre_inspection_accepted = models.ForeignKey("PreInspection", on_delete=models.CASCADE, null=True, blank=True)
	connection_disbursement_obj = models.ForeignKey(
		"ConnectionDisbursement", on_delete=models.CASCADE, null=True, blank=True
	)

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
		if self.status == UjjwalaV2ApplicationStatus.PRE_INSPECTION_SUBMITTED:
			template = loader.get_template("ujjwala/pre_inspection_form_view.html")
			html = template.render({'obj': self})
			return mark_safe(html)
		return mark_safe("")

	@property
	def formatted_address(self):
		if self.version in ('V1', 'V2'):
			return self.address
		return ' '.join([self.address_json.get(r, '') for r in self.address_json])

	@property
	def all_contacts(self):
		phones = set([i for i in [
			self.contact_mobile,
			self.uid_linked_mobile,
			self.sdms_mobile_number
		] if not i])
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
		source=UjjwalaV2ApplicationStatus.EKYC_ACCEPTED,
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

	@fsm_log_description
	@fsm_log_by
	@transition(
		field=status,
		source=UjjwalaV2ApplicationStatus.NIC_CLEARED,
		target=UjjwalaV2ApplicationStatus.PRE_INSPECTION_ACCEPTED,
		custom=dict(
			short_description='Pre Inspection Accepted', admin=True
		),
	)
	def transition_pre_inspection_accepted(self, *args, **kwargs):
		pre_inspection_id = kwargs.get('pre_inspection_id')
		pre_inspection = PreInspection.objects.get(pk=pre_inspection_id)
		self.latitude = pre_inspection.latitude
		self.longitude = pre_inspection.longitude
		self.accuracy = pre_inspection.accuracy
		self.pre_inspection_accepted = pre_inspection
		self.save()
		self.event_legal_documents_upload_channel_whatsapp()

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

	@fsm_log_description
	@fsm_log_by
	@transition(
		field=status,
		source=UjjwalaV2ApplicationStatus.PRE_INSPECTION_ACCEPTED,
		target=UjjwalaV2ApplicationStatus.LEGAL_DOCUMENTS_COLLECTED,
		custom=dict(
			short_description='Legal Documents Collection', admin=True,
		),
		permission='ujjwala.can_approve_connection',
	)
	def transition_legal_documents_collected(self, *args, **kwargs):
		pass

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
	mechanic = models.ForeignKey(User, on_delete=models.PROTECT)
	submitted_on = models.DateTimeField(null=True)

	status = FSMField(
		default=PreInspectionStatusEnum.ALLOCATED,
		choices=PreInspectionStatusEnum.choices
	)

	def mechanic_name(self):
		return self.mechanic.get_full_name()

	def document_kitchen_photo(self):
		return self.documents.filter(type=UjjwalaApplicationDocumentsEnum.KITCHEN_PHOTO).first().link

	def document_main_gate_photo(self):
		return self.documents.filter(type=UjjwalaApplicationDocumentsEnum.MAIN_GATE).first().link

	@fsm_log_description
	@fsm_log_by
	@transition(
		field=status,
		source=PreInspectionStatusEnum.ALLOCATED,
		target=PreInspectionStatusEnum.CHANGE_ADDRESS,
		custom=dict(short_description='Verify Otp', admin=True),
	)
	def pre_inspection_otp_verified(self, *args, **kwargs):
		pass


	@fsm_log_description
	@fsm_log_by
	@transition(
		field=status,
		source=PreInspectionStatusEnum.CHANGE_ADDRESS,
		target=PreInspectionStatusEnum.KITCHEN_PHOTO,
		custom=dict(short_description='Change Address', admin=True),
	)
	def pre_inspection_change_address(self, *args, **kwargs):
		pass


	@fsm_log_description
	@fsm_log_by
	@transition(
		field=status,
		source=PreInspectionStatusEnum.KITCHEN_PHOTO,
		target=PreInspectionStatusEnum.SAFETY_AUDIO,
		custom=dict(short_description='Upload Safety Audio', admin=True),
	)
	def pre_inspection_kitchen_photo_uploaded(self, *args, **kwargs):
		pass

	@fsm_log_description
	@fsm_log_by
	@transition(
		field=status,
		source=PreInspectionStatusEnum.SAFETY_AUDIO,
		target=PreInspectionStatusEnum.PREVIEW_INSPECTION,
		custom=dict(short_description='Preview Inspection', admin=True),
	)
	def pre_inspection_safety_audio_uploaded(self, *args, **kwargs):
		pass


	@fsm_log_description
	@fsm_log_by
	@transition(
		field=status,
		source=PreInspectionStatusEnum.PREVIEW_INSPECTION,
		target=PreInspectionStatusEnum.SUBMITTED,
		custom=dict(short_description='Submit Pre-Inspection', admin=True),
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
			)
			self.parent.save()
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
			self.parent.transition_pre_inspection_accepted(pre_inspection_id=self.pk)
		self.save()


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
	parent = models.ForeignKey(
		UjjwalaV2Application, on_delete=models.PROTECT, related_name='connection_disbursement'
	)
	created_on = models.DateTimeField(auto_now_add=True, null=True)
	updated_on = models.DateTimeField(auto_now=True, null=True)
	status = FSMField(
		default=ConnectionDisbursementStatusEnum.LEGAL_DOCUMENTS_PENDING,
		choices=ConnectionDisbursementStatusEnum.choices
	)

	def legal_document_upload_link(self):
		html = '''
		<a href="https://dca.arungas.com/ujjwala/portal/legal_documents_upload/{}/" target="blank">Upload Physical Legal Documents</a>				
		'''.format(self.pk)
		return mark_safe(html)

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
			self.parent.transition_legal_documents_collected(connection_disbursement_id=self.pk)
			self.parent.save()
		else:
			self.documents.all().delete()

	@fsm_log_description
	@fsm_log_by
	@transition(
		field=status,
		source=ConnectionDisbursementStatusEnum.LEGAL_DOCUMENTS_ACCEPTED,
		target=ConnectionDisbursementStatusEnum.OTP_VERIFIED,
		custom=dict(short_description='Verify Otp', admin=True),
	)
	def transition_connection_disbursement_otp_verified(self, *args, **kwargs):
		pass

	@fsm_log_description
	@fsm_log_by
	@transition(
		field=status,
		source=ConnectionDisbursementStatusEnum.OTP_VERIFIED,
		target=ConnectionDisbursementStatusEnum.SV_LABEL_PRINT,
		custom=dict(short_description='SV & Label Print', admin=True),
	)
	def transition_sv_label_printed(self, *args, **kwargs):
		pass

	@fsm_log_description
	@fsm_log_by
	@transition(
		field=status,
		source=ConnectionDisbursementStatusEnum.SV_LABEL_PRINT,
		target=ConnectionDisbursementStatusEnum.DISBURSEMENT_PHOTO_UPLOAD,
		custom=dict(short_description='Disbursement Photo Upload', admin=True),
	)
	def transition_disbursement_photo_uploaded(self, *args, **kwargs):
		pass

	@fsm_log_description
	@fsm_log_by
	@transition(
		field=status,
		source=ConnectionDisbursementStatusEnum.DISBURSEMENT_PHOTO_UPLOAD,
		target=ConnectionDisbursementStatusEnum.MATERIAL_DELIVERED_UPLOAD_INSTALLATION,
		custom=dict(short_description='Disbursement Photo', admin=True),
	)
	def transition_material_delivered(self, *args, **kwargs):
		pass

	@fsm_log_description
	@fsm_log_by
	@transition(
		field=status,
		source=ConnectionDisbursementStatusEnum.MATERIAL_DELIVERED_UPLOAD_INSTALLATION,
		target=ConnectionDisbursementStatusEnum.INSTALLATION_MAIN_GATE,
		custom=dict(short_description='Upload Installation Kitchen Photo', admin=True),
	)
	def transition_installation_kitchen_upload(self, *args, **kwargs):
		pass

	@fsm_log_description
	@fsm_log_by
	@transition(
		field=status,
		source=ConnectionDisbursementStatusEnum.INSTALLATION_MAIN_GATE,
		target=ConnectionDisbursementStatusEnum.INSTALLATION_UPLOADED,
		custom=dict(short_description='Upload Main Gate Photo', admin=True),
	)
	def transition_main_gate(self, *args, **kwargs):
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
