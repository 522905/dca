import datetime
import re
from functools import partial

import django_rq
from django.conf import settings
from django.contrib.auth.models import User
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ValidationError
from django.db import models, transaction
from django.urls import reverse
from django.utils.safestring import mark_safe
from django_currentuser.middleware import get_current_user
from django_fsm import FSMField, transition, GET_STATE
from django_fsm_log.decorators import fsm_log_description, fsm_log_by
from organizations.models import Organization

from communication_log.models import CommunicationLog
from teams.models import ServiceLocations, ServiceArea, FormFillArea
from ujjwala.communication_models import UjjwalaWhatsappCommunication
from ujjwala.enums import MaritalStatusEnum, ResidentialStatusEnum, UjjwalaUidMobileStatusEnum, \
	UjjwalaV2ApplicationStatus, UjjwalaApplicationDocumentsEnum, FamilyMemberRelationEnum, \
	RejectionTypeEnum, RoboSdmsDedeupStatusEnum, UserDocumentsEnum, PreInspectionStatusEnum, \
	ConnectionDisbursementStatusEnum, PreInspectionTypeEnum, SchemeOnboardingStatusEnum, NicClearedCustomerRemarksEnum, \
	DisbursementDriveStatusEnum
from ujjwala.forms import ConnectionStatusApproved, ApplicationRejected, \
	EkycAccepted, PreInspectionReviewAdminForm, LegalDocumentsUpload, \
	LegalDocumentsReviewAdminForm, NicUpdateAddressForm, ReviewNicErrorUpdatedAddressForm, NewRelationCreated, \
	CancelWalkInForm, MoveForManualOperationForm, MaterialDeliveryOtpOverrideForm, OnHoldForm, \
	ReleaseApplicationForm, CompleteDisbursementDriveForm, \
	InstallationReviewAdminForm
from ujjwala.ujjwala_functions import download_ujjwala_physical_legal_docs, is_application_ready_for_disbursement, \
	fsm_custom_audit_points_description
from utils.global_functions import upload_file_to_minio_bucket, old_address_to_description, \
	old_walk_in_to_description


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
	consumer_id = models.CharField(max_length=16, null=True, blank=True, unique=True)
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
		max_length=32, choices=RoboSdmsDedeupStatusEnum.choices,
		default=RoboSdmsDedeupStatusEnum.NOT_PROCESSED
	)
	status = FSMField(
		default=UjjwalaV2ApplicationStatus.DOCUMENTS_UPLOADED,
		choices=UjjwalaV2ApplicationStatus.choices
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
		max_length=64, choices=NicClearedCustomerRemarksEnum.choices,
		null=True, blank=True
	)
	scheduled_date = models.DateTimeField(null=True, blank=True)
	additional_remarks = models.TextField(null=True, blank=True)
	ekyc_cleared = models.BooleanField(default=False)
	robo_execution_failed_count = models.IntegerField(default=0, blank=True, null=True)
	# form_fill_area = models.ForeignKey(
	# 	FormFillArea, on_delete=models.CASCADE, related_name='form_fill_area', null=True, blank=True
	# )

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
			("can_reject_application", "Can reject application"),
			("can_fill_old_ujjwala_form", "Can fill old ujjwala form"),
			("can_do_connection_disbursement", "Can do connection disbursement"),
			("can_cancel_walk_in", "Can cancel walk in"),
			("robo_manager_permission", "Robo Manager Permission"),
		)

	def pre_inspection_accepted(self):
		return self.pre_inspection


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


	def whatsapp_pre_inspection_type_self(self):
		url = reverse('ujjwala:whatsapp_pre_inspection_type_self', kwargs={'pk': self.pk})
		html = '''
		<a href="{}">Whatsapp Pre Inspection Type Self</a>
		'''.format(url)
		return mark_safe(html)


	def whatsapp_form_a_b_c(self):
		# WhatsappUploadLegalForms
		url = reverse('ujjwala:whatsapp_form_abc', kwargs={'pk': self.pk})
		html = '''
		<a href="{}">Whatsapp Form A B C</a>
		'''.format(url)
		return mark_safe(html)


	def reset_robo_execution_failed_count(self):
		# WhatsappUploadLegalForms
		url = reverse('ujjwala:reset_robo_failed_count', kwargs={'pk': self.pk})
		html = '''
		<a href="{}">Reset Robo Failed Count</a>
		'''.format(url)
		return mark_safe(html)


	def set_primary_phone_number(self):
		# WhatsappUploadLegalForms
		url = reverse('ujjwala:set_primary_phone_number', kwargs={'pk': self.pk})
		html = '''
		<a href="{}">Set Primary Phone Number</a>
		'''.format(url)
		return mark_safe(html)

	def whatsapp_update_bank_details(self):
		if not self.bank_account_number:
			url = reverse('ujjwala:whatsapp_update_bank_details', kwargs={'pk': self.pk})
			html = '''
			<a href="{}">Whatsapp Update Bank Details</a>
			'''.format(url)
			return mark_safe(html)
		else:
			return mark_safe("Bank Details Updated")

	@property
	def formatted_address(self):
		if self.version in ('V1', 'V2'):
			return self.address
		self.address_json['city'] = 'Ludhiana'
		return ' '.join([self.address_json.get(r, '') for r in [
			'room_no', 'floor', 'street_no', 'landmark', 'village', 'post_office', 'pincode'
		]])

	def get_address_for_sdms_upload(self):
		if not self.address_json:
			return self.address

		# addr_str = 'hNo {house_no} '\
		# 'StNo {street_no} {village}'.format(
		# 	**self.address_json
		# )
		addr_str = 'hNo {} '\
		'StNo {} {} '.format(
			self.address_json.get('house_no', ''),
			self.address_json.get('street_no', ''),
			self.address_json.get('village', ''),
		)

		# addr_tokens = [i for i in addr_str.replace(',', ' ').split(' ').split(',') if i]

		addr_tokens = []
		tokens = addr_str.replace(',', ' ').split(' ')

		for token in tokens:
			sub_tokens = token.split(',')
			for sub_token in sub_tokens:
				addr_tokens.append(sub_token.strip(' '))

		seen = []
		rs = []

		for i in addr_tokens:
			if i.lower() in seen: continue
			rs.append(i)
			seen.append(i.lower())

		return {
			'addr_str': ' '.join(rs),
			'pincode': self.address_json.get('pincode', '141001')
		}

	@property
	def all_contacts(self):
		phones = set([i for i in [
			self.contact_mobile,
			self.uid_linked_mobile,
			self.sdms_mobile_number
		] if i])
		return list(phones)

	def document_self(self):
		sd = self.documents.filter(type=UjjwalaApplicationDocumentsEnum.CUSTOMER_PHOTO).first()
		return sd.link if sd else ''

	def document_kitchen_photo(self):
		return self.documents.filter(
			type=UjjwalaApplicationDocumentsEnum.KITCHEN_PHOTO
		).order_by('-id').first().link

	def document_customer_in_kitchen(self):
		return self.documents.filter(
			type=UjjwalaApplicationDocumentsEnum.CUSTOMER_IN_KITCHEN
		).order_by('-id').first().link

	def document_mechanic_photo(self):
		return self.documents.filter(type=UjjwalaApplicationDocumentsEnum.MECHANIC_PHOTO).first().link

	def document_customer_signature(self):
		return self.documents.filter(type=UjjwalaApplicationDocumentsEnum.CUSTOMER_SIGNATURE).first().link

	def document_witness_photo(self):
		return self.documents.filter(type=UjjwalaApplicationDocumentsEnum.WITNESS_PHOTO).first().link

	def physical_legal_document_link(self):
		record = self.pre_inspection.documents.filter(
			type=UjjwalaApplicationDocumentsEnum.PHYSICAL_LEGAL_DOCUMENT
		).first()
		if record:
			return record.link
		return ''

	def get_form_abc(self):
		return {
			"form_a_link": self.connection_disbursement.documents.filter(
				type=UjjwalaApplicationDocumentsEnum.LEGAL_DOC_PRE_INSPECTION
			).order_by('-id').first().link,
			"form_b_link": self.connection_disbursement.documents.filter(
				type=UjjwalaApplicationDocumentsEnum.LEGAL_DOC_FAMILY_OCCUPANCY
			).order_by('-id').first().link,
			"form_c_link": self.connection_disbursement.documents.filter(
				type=UjjwalaApplicationDocumentsEnum.LEGAL_DOC_ANNEXURE_14_POINTS
			).order_by('-id').first().link
		}

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
		source=[
			UjjwalaV2ApplicationStatus.DOCUMENTS_UPLOADED,
			UjjwalaV2ApplicationStatus.DOCUMENTS_REUPLOAD,
			UjjwalaV2ApplicationStatus.LEGAL_DOCUMENTS_UPLOAD,
			UjjwalaV2ApplicationStatus.EKYC_ACCEPTED,
			UjjwalaV2ApplicationStatus.AUDIT_APPLICATION,
			UjjwalaV2ApplicationStatus.NIC_CLEARED,
			UjjwalaV2ApplicationStatus.READY_FOR_DISBURSEMENT,
		],
		target=UjjwalaV2ApplicationStatus.ON_HOLD,
		custom=dict(short_description='Hold Application', admin=True, form=OnHoldForm),
		permission='ujjwala.robo_manager_permission'
	)
	def transition_on_hold(self, *args, **kwargs):
		self.last_execution_state = self.status

	@fsm_log_description
	@fsm_log_by
	@transition(
		field=status,
		source=UjjwalaV2ApplicationStatus.ON_HOLD,
		target=GET_STATE(
			lambda self, **kwargs: self.last_execution_state,
		),
		custom=dict(
			short_description='Release Application', admin=True, form=ReleaseApplicationForm
		),
	)
	def transition_release_application(self, *args, **kwargs):
		pass


	@fsm_log_description
	@fsm_log_by
	@transition(
		field=status,
		source=UjjwalaV2ApplicationStatus.DOCUMENTS_UPLOADED,
		target=UjjwalaV2ApplicationStatus.EKYC_ACCEPTED,
		custom=dict(short_description='E-KYC Accepted', admin=True, form=EkycAccepted),
		permission='ujjwala.robo_manager_permission'
	)
	def ekyc_accepted_or_rejected(self, *args, **kwargs):
		self.robo_execution_failed_count = 0
		if kwargs.get('sdms_consumer_id', ''):
			self.consumer_id = kwargs.get('sdms_consumer_id')
		self.sdms_mobile_number = kwargs.get('sdms_mobile_number')


	@fsm_log_description
	@fsm_log_by
	@transition(
		field=status,
		source=[
			UjjwalaV2ApplicationStatus.DOCUMENTS_UPLOADED,
			UjjwalaV2ApplicationStatus.DOCUMENTS_REUPLOAD,
			UjjwalaV2ApplicationStatus.LEGAL_DOCUMENTS_UPLOAD,
			UjjwalaV2ApplicationStatus.EKYC_ACCEPTED,
			UjjwalaV2ApplicationStatus.AUDIT_APPLICATION,
			UjjwalaV2ApplicationStatus.NIC_CLEARED,
			UjjwalaV2ApplicationStatus.READY_FOR_DISBURSEMENT
		],
		# target=UjjwalaV2ApplicationStatus.APPLICATION_REJECTED,
		target=GET_STATE(
			lambda self, **kwargs: \
					UjjwalaV2ApplicationStatus.DOCUMENTS_REUPLOAD \
						if kwargs.get('rejected_reason') == RejectionTypeEnum.INSUFFICIENT_DATA \
						else UjjwalaV2ApplicationStatus.APPLICATION_REJECTED,
			states=[
				UjjwalaV2ApplicationStatus.APPLICATION_REJECTED,
				UjjwalaV2ApplicationStatus.DOCUMENTS_REUPLOAD
			]
		),
		custom=dict(short_description='Reject Application', admin=True, form=ApplicationRejected),
		permission='ujjwala.can_reject_application'
	)
	def application_rejected(self, *args, **kwargs):
		pass


	@fsm_log_description
	@fsm_log_by
	@transition(
		field=status,
		source=UjjwalaV2ApplicationStatus.LEGAL_DOCUMENTS_UPLOAD,
		target=UjjwalaV2ApplicationStatus.DO_MANUAL_OPERATION,
		custom=dict(short_description='Move For Manual Operation', admin=True, form=MoveForManualOperationForm),
		permission='ujjwala.robo_manager_permission'
	)
	def transition_move_for_manual_operation(self, *args, **kwargs):
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
		# permission='ujjwala.can_upload_legal_docs',
		permission='ujjwala.robo_manager_permission',
	)
	def legal_documents_upload(self, *args, **kwargs):
		self.robo_execution_failed_count = 0
		pass

	@fsm_log_description
	@fsm_log_by
	@transition(
		field=status,
		source=UjjwalaV2ApplicationStatus.EKYC_ACCEPTED,
		target=UjjwalaV2ApplicationStatus.MANUAL_LEGAL_DOCUMENTS_UPLOAD,
		custom=dict(short_description='Update Legal Documents', admin=False),
		permission='ujjwala.robo_manager_permission',
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
		permission='ujjwala.robo_manager_permission',
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
		# permission='ujjwala.can_approve_connection',
		permission='ujjwala.robo_manager_permission',
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
		# permission='ujjwala.can_approve_connection',
		permission='ujjwala.robo_manager_permission',
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
		# permission='ujjwala.can_approve_connection',
		permission='ujjwala.robo_manager_permission',
	)
	def transition_nic_cleared(self, *args, **kwargs):
		try:
			is_application_ready_for_disbursement(self)
		except self.RelatedObjectDoesNotExist:
			obj = PreInspection.objects.create(
				parent_id=self.pk,
				status=PreInspectionStatusEnum.KITCHEN_PHOTO,
				type=PreInspectionTypeEnum.SELF
			)
			obj.parent.event_whatsapp_pre_inspection_type_self(obj.pk)


	@fsm_log_description
	@fsm_log_by
	@transition(
		field=status,
		source=UjjwalaV2ApplicationStatus.OMC_CLEARED,
		target=UjjwalaV2ApplicationStatus.NIC_ERROR,
		custom=dict(
			short_description='Set As NIC Error', admin=True, form=ConnectionStatusApproved
		),
		# permission='ujjwala.can_approve_connection',
		permission='ujjwala.robo_manager_permission',
	)
	def transition_nic_error(self, *args, **kwargs):
		self.manual_operation_code = kwargs.get('error_code')

	@fsm_log_description
	@fsm_log_by
	@transition(
		field=status,
		source=[
			UjjwalaV2ApplicationStatus.OMC_CLEARED,
			UjjwalaV2ApplicationStatus.NIC_ERROR_UPDATE_ADDRESS
		],
		target=UjjwalaV2ApplicationStatus.NIC_ERROR_INSUFFICIENT_ADDRESS,
		custom=dict(
			short_description='NIC Error Insufficient Address', admin=False
		),
		permission='ujjwala.can_approve_connection',
	)
	def transition_nic_error_insufficient_address(self, *args, **kwargs):
		self.manual_operation_code = kwargs.get('error_code')
		self.event_whatsapp_nic_error_update_address()

	@fsm_log_description
	@fsm_log_by
	@transition(
		field=status,
		source=UjjwalaV2ApplicationStatus.NIC_ERROR,
		target=UjjwalaV2ApplicationStatus.NIC_ERROR_APPROVED,
		custom=dict(
			short_description='Nic Error Distributor Approved', admin=False
		),
		permission='ujjwala.can_approve_connection',
	)
	def transition_nic_error_distributor_approved(self, *args, **kwargs):
		pass

	@fsm_log_description
	@fsm_log_by
	@transition(
		field=status,
		source=UjjwalaV2ApplicationStatus.NIC_ERROR_APPROVED,
		target=UjjwalaV2ApplicationStatus.NIC_CLEARED,
		custom=dict(
			short_description='Nic Error Approved To Nic Clear', admin=False
		),
		permission='ujjwala.can_approve_connection',
	)
	def transition_nic_error_approved_to_nic_clear(self, *args, **kwargs):
		pass

	@fsm_log_description
	@fsm_log_by
	@transition(
		field=status,
		source=UjjwalaV2ApplicationStatus.NIC_ERROR_ADDRESS_ACCEPTED,
		target=UjjwalaV2ApplicationStatus.LEGAL_DOCUMENTS_UPLOAD,
		custom=dict(
			short_description='Address Updated, New relation initiated', admin=True, form=NewRelationCreated
		),

		permission='ujjwala.can_approve_connection',
	)
	def transition_create_new_relation_after_nic_error_insufficent_address(self, *args, **kwargs):
		self.consumer_id = kwargs.get('consumer_id')

	@old_address_to_description
	@fsm_log_description
	@fsm_log_by
	@transition(
		field=status,
		source=[
			UjjwalaV2ApplicationStatus.NIC_ERROR_INSUFFICIENT_ADDRESS
		],
		target=UjjwalaV2ApplicationStatus.NIC_ERROR_UPDATE_ADDRESS,
		custom=dict(
			short_description='Update Address', admin=True, form=NicUpdateAddressForm
		),
		permission='ujjwala.can_approve_connection',
	)
	def transition_nic_address_updated(self, *args, **kwargs):
		self.address_json = kwargs['address_json']

	@fsm_log_description
	@fsm_log_by
	@transition(
		field=status,
		source=UjjwalaV2ApplicationStatus.NIC_ERROR_UPDATE_ADDRESS,
		target=GET_STATE(
			lambda self, **kwargs: \
					UjjwalaV2ApplicationStatus.NIC_ERROR_ADDRESS_ACCEPTED \
							if kwargs.get("review_status") == 'ACCEPTED' \
							else UjjwalaV2ApplicationStatus.NIC_ERROR_INSUFFICIENT_ADDRESS,
			states=[
				UjjwalaV2ApplicationStatus.NIC_ERROR_ADDRESS_ACCEPTED,
				UjjwalaV2ApplicationStatus.NIC_ERROR_INSUFFICIENT_ADDRESS
			]
		),
		custom=dict(
			short_description='Review Nic Error Updated Address', admin=True, form=ReviewNicErrorUpdatedAddressForm
		),
	)
	def transition_review_nic_address_updated(self, *args, **kwargs):
		if kwargs.get('review_status') == 'ACCEPTED':
			self.address_json = kwargs['address_json']
		else:
			self.transition_nic_error_insufficient_address(
				error_code='', description="User Entered In-correct Address"
			)


	@fsm_log_description
	@fsm_log_by
	@transition(
		field=status,
		source=UjjwalaV2ApplicationStatus.NIC_CLEARED,
		target=UjjwalaV2ApplicationStatus.READY_FOR_DISBURSEMENT,
		custom=dict(
			short_description='Ready For Disbursement', admin=False,
		),
		permission='ujjwala.can_approve_connection',
	)
	def transition_ready_for_disbursement(self, *args, **kwargs):
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

	@fsm_custom_audit_points_description
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
	def transition_audit_accepted(self, *args, **kwargs):
		self_fm = self.family_members.get(relation=FamilyMemberRelationEnum.SELF)

		for fm in self.family_members.all():
			fm.validated = True
			fm.save()

		self.name = self_fm.name


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
	parent = models.ForeignKey(UjjwalaV2Application, on_delete=models.CASCADE, related_name='documents', null=True)
	type = models.CharField(max_length=32, choices=UjjwalaApplicationDocumentsEnum.choices)
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
	parent = models.ForeignKey(User, on_delete=models.CASCADE, related_name='documents', null=True)
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
			PreInspectionStatusEnum.OTP_VERIFIED,
			PreInspectionStatusEnum.CHANGE_ADDRESS,
			PreInspectionStatusEnum.KITCHEN_PHOTO,
			PreInspectionStatusEnum.PREVIEW_INSPECTION,
			PreInspectionStatusEnum.REUPLOAD,
			PreInspectionStatusEnum.REJECTED,
			PreInspectionStatusEnum.SAFETY_AUDIO,
		],
		target=GET_STATE(
			lambda self, **kwargs: \
					PreInspectionStatusEnum.KITCHEN_PHOTO \
						if kwargs.get('convert_to_type') == 'self' \
						else PreInspectionStatusEnum.ALLOCATED,
			states=[
				PreInspectionStatusEnum.KITCHEN_PHOTO,
				PreInspectionStatusEnum.ALLOCATED
			]
		),
		custom=dict(short_description='Convert Inspection Type', admin=False),
	)
	def convert_inspection_type(self, convert_to_type='', *args, **kwargs):
		if convert_to_type == 'mech':
			self.type = PreInspectionTypeEnum.MECHANIC
			self.mechanic = get_current_user()
		else:
			self.type = PreInspectionTypeEnum.SELF
			self.mechanic = None

		self.documents.all().delete()

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
			self.documents.all().delete()


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
		source=[PreInspectionStatusEnum.KITCHEN_PHOTO, PreInspectionStatusEnum.REJECTED],
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
		if self.type == PreInspectionTypeEnum.SELF:
			self.mechanic = None
		else:
			self.mechanic = get_current_user()
		self.submitted_on = datetime.datetime.now()
		self.save()
		#Commented For Exif Evaluation
		create_txn_status_job_function = partial(
			django_rq.enqueue,
			"ujjwala.jobs.compress_pre_inspection_documents",
			parent_id=self.id
		)
		transaction.on_commit(create_txn_status_job_function)

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

			self.parent.latitude = self.latitude
			self.parent.longitude = self.longitude
			self.parent.accuracy = self.accuracy
			self.parent.save()
			self.parent.event_legal_documents_upload_channel_whatsapp()
			is_application_ready_for_disbursement(self.parent)
		else:
			self.parent.event_whatsapp_pre_inspection_reject(self.id, kwargs.get('rejected_reason'))


class PreInspectionDocuments(models.Model):
	parent = models.ForeignKey(PreInspection, on_delete=models.CASCADE, related_name='documents', null=True)
	type = models.CharField(max_length=32, choices=UjjwalaApplicationDocumentsEnum.choices)
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


class Evykati(models.Model):
	parent = models.ForeignKey(
		UjjwalaV2Application, on_delete=models.PROTECT, related_name='evyakti'
	)
	information = models.JSONField(null=True, blank=True)


class DisbursementDrive(models.Model):
	created_on = models.DateTimeField(auto_now_add=True)
	updated_on = models.DateTimeField(auto_now=True)
	manager = models.ForeignKey(User, on_delete=models.PROTECT, related_name="owned_disbursement_drives")
	team_members = models.ManyToManyField(User)
	description = models.TextField()
	date = models.DateField()
	max_walk_ins = models.IntegerField()
	status = FSMField(
		default=DisbursementDriveStatusEnum.ACTIVE,
		choices=DisbursementDriveStatusEnum.choices
	)

	class Meta:
		permissions = (
			("disbursement_manager", "Disbursement Manager"),
		)

	# @fsm_log_description
	# @fsm_log_by
	# @transition(
	# 	field=status,
	# 	source=DisbursementDriveStatusEnum.ACTIVE,
	# 	target=DisbursementDriveStatusEnum.CANCELED,
	# 	custom=dict(short_description='Cancel Disbursement Drive', admin=True, form=CancelDisbursementDriveForm),
	# )
	# def transition_cancel_disbursement_drive(self, *args, **kwargs):
	# 	if self.connectiondisbursement_set.filter(
	# 		status=ConnectionDisbursementStatusEnum.MATERIAL_DELIVERED
	# 	):
	# 		raise ValidationError("Not Valid Disbursement Drive For Cancellation")


	@fsm_log_description
	@fsm_log_by
	@transition(
		field=status,
		source=DisbursementDriveStatusEnum.ACTIVE,
		target=DisbursementDriveStatusEnum.COMPLETED,
		custom=dict(short_description='Complete Disbursement Drive', admin=True, form=CompleteDisbursementDriveForm),
	)
	def transition_complete_disbursement_drive(self, *args, **kwargs):
		if self.connectiondisbursement_set.filter().exclude(status=ConnectionDisbursementStatusEnum.MATERIAL_DELIVERED):
			raise ValidationError("Please Complete All Material Deliveries")


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
	material_delivered_on = models.DateTimeField(null=True, blank=True)
	dac_code = models.CharField(max_length=4, null=True, blank=True)

	status = FSMField(
		default=ConnectionDisbursementStatusEnum.LEGAL_DOCUMENTS_PENDING,
		choices=ConnectionDisbursementStatusEnum.choices
	)
	disbursement_drive = models.ForeignKey(DisbursementDrive, on_delete=models.SET_NULL, blank=True, null=True)

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

	def whatsapp_form_a_b_c(self):
		# WhatsappUploadLegalForms
		url = reverse('ujjwala:whatsapp_form_abc', kwargs={'pk': self.parent.pk})
		html = '''
		<a href="{}">Whatsapp Form A B C</a>
		'''.format(url)
		return mark_safe(html)

	def valid_sv_link(self):
		valid_invitation = self.invitation.filter(parent=self).first()

		if valid_invitation:
			return valid_invitation.sv_link

	def form_d_link(self):
		if self.documents.filter(type=UjjwalaApplicationDocumentsEnum.INSTALLATION_DOCUMENT):
			return self.documents.filter(type=UjjwalaApplicationDocumentsEnum.INSTALLATION_DOCUMENT).first().link

	def sv_exist(self):
		valid_invitation = self.invitation.filter(status='VALID').first()

		if valid_invitation and valid_invitation.sv_link:
			return True
		return False

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
			self.parent.event_legal_documents_reupload_channel_whatsapp(kwargs.get('description'))


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
		source=ConnectionDisbursementStatusEnum.SOCIAL_MEDIA_UPDATES,
		target=ConnectionDisbursementStatusEnum.MATERIAL_DELIVERY_OTP_VERIFIED,
		custom=dict(
			short_description='Material Delivery OTP Override',
		    admin=True, form=MaterialDeliveryOtpOverrideForm
		),
	)
	def transition_material_delivery_otp_override(self, *args, **kwargs):
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
		self.material_delivered_on = datetime.datetime.now()
		self.parent.save()
		create_txn_status_job_function = partial(
			django_rq.enqueue,
			"ujjwala.jobs.compress_connection_disbursement_documents",
			parent_id=self.id
		)
		transaction.on_commit(create_txn_status_job_function)

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
		pass


	@fsm_log_description
	@fsm_log_by
	@transition(
		field=status,
		source=ConnectionDisbursementStatusEnum.INSTALLATION_UPLOADED,
		target=GET_STATE(
					lambda self, **kwargs: \
							ConnectionDisbursementStatusEnum.INSTALLATION_ACCEPTED \
									if kwargs.get('review_status') == 'ACCEPTED' \
									else ConnectionDisbursementStatusEnum.INSTALLATION_REJECTED,
					states=[
						ConnectionDisbursementStatusEnum.INSTALLATION_ACCEPTED,
						ConnectionDisbursementStatusEnum.INSTALLATION_REJECTED
					]
				),
		custom=dict(
			short_description='Installation Review', admin=True, form=InstallationReviewAdminForm
		),
	)
	def transition_installation_reviewed(self, *args, **kwargs):
		if kwargs.get('review_status') == 'REJECTED':
			self.documents.filter(
				type__in=[
					UjjwalaApplicationDocumentsEnum.INSTALLATION_KITCHEN_PHOTO,
					UjjwalaApplicationDocumentsEnum.INSTALLATION_STOVE_WITH_STICKER
				]
			).delete()
		else:
			self.parent.transition_installed(by=get_current_user())
			self.parent.save()
			# self.parent.event_installation_reupload_channel_whatsapp(kwargs.get('description'))


	@old_walk_in_to_description
	@fsm_log_description
	@fsm_log_by
	@transition(
		field=status,
		source=[
			ConnectionDisbursementStatusEnum.LEGAL_DOCUMENTS_REVIEW,
			ConnectionDisbursementStatusEnum.LEGAL_DOCUMENTS_PENDING,
			ConnectionDisbursementStatusEnum.LEGAL_DOCUMENTS_ACCEPTED,
			ConnectionDisbursementStatusEnum.SV_LABEL_PRINT,
			ConnectionDisbursementStatusEnum.SOCIAL_MEDIA_UPDATES,
			ConnectionDisbursementStatusEnum.MATERIAL_DELIVERY_OTP_VERIFIED,
		],
		target=GET_STATE(
					lambda self, **kwargs: \
							ConnectionDisbursementStatusEnum.LEGAL_DOCUMENTS_PENDING \
									if self.status == ConnectionDisbursementStatusEnum.LEGAL_DOCUMENTS_PENDING \
									else ConnectionDisbursementStatusEnum.LEGAL_DOCUMENTS_REVIEW,
					states=[
						ConnectionDisbursementStatusEnum.LEGAL_DOCUMENTS_REVIEW,
						ConnectionDisbursementStatusEnum.LEGAL_DOCUMENTS_PENDING
					]
				),
		custom=dict(
			short_description='Cancel Walk-In', admin=True, form=CancelWalkInForm
		),
		conditions=[
			lambda self: self.walk_in_date is not None
		],
		permission="ujjwala.can_cancel_walk_in"
	)
	def transition_cancel_walk_in(self, *args, **kwargs):
		self.disbursement_drive = None
		self.walk_in_date = None
		self.invitation.all().delete()
		self.save()


class ConnectionDisbursementDocuments(models.Model):
	parent = models.ForeignKey(ConnectionDisbursement, on_delete=models.CASCADE, related_name='documents', null=True)
	type = models.CharField(max_length=32, choices=UjjwalaApplicationDocumentsEnum.choices)
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


class ConnectionDisbursementInvitation(models.Model):
	parent = models.ForeignKey(
		ConnectionDisbursement, on_delete=models.CASCADE, related_name='invitation', null=True
	)
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
