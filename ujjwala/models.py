from django.conf import settings
from django.contrib.auth.models import User
from django.contrib.contenttypes.models import ContentType
from django.db import models
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
	RejectionTypeEnum, RoboSdmsDedeupStatusEnum, UserDocumentsEnum, OtpStatusEnum
from ujjwala.forms import LegalDocumentsCollected, LegalDocumentsUpload, \
	ConnectionRelease, PostInstallationUpload, ConnectionStatusApproved, ApplicationRejected, \
	EkycAccepted, PreInspectionReviewForm


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
	uid_mobile_status = models.CharField(max_length=25, choices=UjjwalaUidMobileStatusEnum.choices, blank=True, null=True)
	application_id_kyc_no = models.CharField(max_length=24, null=True, blank=True)
	referral_code = models.CharField(max_length=64, null=True, blank=True)
	service_team = models.ForeignKey(Organization, on_delete=models.CASCADE, null=True, blank=True)
	service_location = models.ForeignKey(ServiceLocations, on_delete=models.CASCADE, null=True, blank=True)
	version = models.CharField(max_length=2, default='V1')
	latitude = models.CharField(max_length=16, null=True, blank=True)
	longitude = models.CharField(max_length=16, null=True, blank=True)
	accuracy = models.CharField(max_length=24, null=True, blank=True)
	product = models.CharField(max_length=256, null=True, blank=True)
	witness_name = models.CharField(max_length=256, null=True, blank=True)
	witness_mobile_number = models.CharField(max_length=10, null=True, blank=True)
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
	pre_inspection_done_by = models.ForeignKey(
		User, on_delete=models.CASCADE, related_name='pre_inspection_done_by', null=True
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
		# self.consumer_id = kwargs.get('consumer_id')

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
		source=[
			UjjwalaV2ApplicationStatus.NIC_CLEARED,
			UjjwalaV2ApplicationStatus.PRE_INSPECTION_REUPLOAD,
		],
		target=UjjwalaV2ApplicationStatus.PRE_INSPECTION_SUBMITTED,
		custom=dict(
			short_description='Pre Inspection Submit', admin=True,
		),
		permission='ujjwala.can_approve_connection',
	)
	def transition_pre_inspection_submit(self, *args, **kwargs):
		self.latitude = kwargs.get('latitude')
		self.longitude = kwargs.get('longitude')
		self.accuracy = kwargs.get('accuracy')
		self.witness_name = kwargs.get('witness_name')
		self.witness_mobile_number = kwargs.get('witness_mobile_number')

		self.documents.create(
			type=UjjwalaApplicationDocumentsEnum.KITCHEN_PHOTO,
			link=kwargs.get('kitchen_photo')
		)
		self.documents.create(
			type=UjjwalaApplicationDocumentsEnum.MAIN_GATE,
			link=kwargs.get('main_gate')
		)
		self.documents.create(
			type=UjjwalaApplicationDocumentsEnum.CUSTOMER_IN_KITCHEN,
			link=kwargs.get('customer_in_kitchen')
		)
		self.documents.create(
			type=UjjwalaApplicationDocumentsEnum.WITNESS_PHOTO,
			link=kwargs.get('witness_photo')
		)
		self.documents.create(
			type=UjjwalaApplicationDocumentsEnum.MECHANIC_PHOTO,
			link=kwargs.get('mechanic_photo')
		)

	@fsm_log_description
	@fsm_log_by
	@transition(
		field=status,
		source=UjjwalaV2ApplicationStatus.PRE_INSPECTION_SUBMITTED,
		target=GET_STATE(
			lambda self, **kwargs: \
					UjjwalaV2ApplicationStatus.PRE_INSPECTION_ACCEPTED \
							if kwargs.get("verified") else UjjwalaV2ApplicationStatus.PRE_INSPECTION_REUPLOAD,
			states=[
				UjjwalaV2ApplicationStatus.PRE_INSPECTION_ACCEPTED,
				UjjwalaV2ApplicationStatus.PRE_INSPECTION_REUPLOAD
			]
		),
		custom=dict(
			short_description='Review Pre Inspection', admin=True, form=PreInspectionReviewForm
		),
	)
	def review_pre_inspection(self, *args, **kwargs):
		self.pre_inspection_done_by = get_current_user()
		self.documents_required_for_reupload = kwargs.get('documents_required_for_reupload')


	@fsm_log_description
	@fsm_log_by
	@transition(
		field=status,
		source=UjjwalaV2ApplicationStatus.PRE_INSPECTION_ACCEPTED,
		target=UjjwalaV2ApplicationStatus.CONNECTION_RELEASED,
		custom=dict(
			short_description='Pre Inspection Accept', admin=True,
		),
		permission='ujjwala.can_approve_connection',
	)
	def transition_pre_inspection_accept(self, *args, **kwargs):
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
	type = models.CharField(max_length=25, choices=UjjwalaApplicationDocumentsEnum.choices)
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
	type = models.CharField(max_length=25, choices=UserDocumentsEnum.choices)
	link = models.URLField()

	def download_links(self):
		html = '''
		<a href="{}" target="blank">View</a>&nbsp||&nbsp<a href="{}" target="blank">Download Comp.</a>
		'''.format(self.link, self.link)
		return mark_safe(html)
