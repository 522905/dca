import track
from django import template
from django.conf import settings
from django.contrib.contenttypes.models import ContentType
from django.db import models
from django.template import loader
from django.utils.safestring import mark_safe
from django_fsm import FSMField, transition, GET_STATE
from django_fsm_log.decorators import fsm_log_description, fsm_log_by
from organizations.models import Organization

from communication_log.models import CommunicationLog
from teams.models import ServiceLocations
from ujjwala.communication_models import UjjwalaWhatsappCommunication
from ujjwala.enums import MaritalStatusEnum, ResidentialStatusEnum, UjjwalaUidMobileStatusEnum, \
	UjjwalaPreInspectionStatus, UjjwalaV2ApplicationStatus, UjjwalaApplicationDocumentsEnum, FamilyMemberRelationEnum, \
	RejectionTypeEnum, RoboSdmsDedeupStatusEnum
from ujjwala.forms import EkycAcceptedOrRejected, \
	LegalDocumentsCollected, LegalDocumentsUpload, \
	ConnectionRelease, PostInstallationUpload, ConnectionStatusApproved, ConnectionStatusRejected, ApplicationRejected, \
	EkycAccepted


class UjjwalaV2Application(models.Model, UjjwalaWhatsappCommunication):
	created_on = models.DateTimeField(auto_now_add=True)
	updated_on = models.DateTimeField(auto_now=True)
	rejection_type = models.CharField(max_length=25, choices=RejectionTypeEnum.choices, null=True, blank=True)
	marital_status = models.CharField(max_length=25, choices=MaritalStatusEnum.choices)
	residential_status = models.CharField(max_length=25, choices=ResidentialStatusEnum.choices, blank=True, null=True)
	name = models.CharField(max_length=50)
	address = models.TextField(null=True, blank=True)
	address_json = models.JSONField(null=True, blank=True)
	contact_mobile = models.CharField(max_length=10)
	consumer_id = models.CharField(max_length=16, null=True, blank=True)
	uid_linked_mobile = models.CharField(max_length=10, null=True, blank=True)
	uid_mobile_status = models.CharField(max_length=25, choices=UjjwalaUidMobileStatusEnum.choices)
	application_id_kyc_no = models.CharField(max_length=24, null=True, blank=True)
	referral_code = models.CharField(max_length=16, null=True, blank=True)
	service_team = models.ForeignKey(Organization, on_delete=models.CASCADE, null=True, blank=True)
	service_location = models.ForeignKey(ServiceLocations, on_delete=models.CASCADE, null=True, blank=True)
	version = models.CharField(max_length=2, default='V1')
	latitude = models.CharField(max_length=16, null=True, blank=True)
	longitude = models.CharField(max_length=16, null=True, blank=True)

	robo_sdms_dedup = models.CharField(
		max_length=25, choices=RoboSdmsDedeupStatusEnum.choices,
		default=RoboSdmsDedeupStatusEnum.NOT_PROCESSED
	)

	status = FSMField(
		default=UjjwalaV2ApplicationStatus.DOCUMENTS_UPLOADED,
		choices=UjjwalaV2ApplicationStatus.choices
	)

	pre_inspection_status = FSMField(
		default=UjjwalaPreInspectionStatus.PENDING,
		choices=UjjwalaPreInspectionStatus.choices
	)
	manual_operation_code = models.CharField(max_length=25, null=True, blank=True)
	legal_documents_upload_status = models.CharField(max_length=25, null=True, blank=True)
	sv = models.CharField(max_length=25, null=True, blank=True)
	last_execution_state = models.CharField(max_length=50, null=True, blank=True)

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
		target=UjjwalaV2ApplicationStatus.CONNECTION_APPROVED,
		custom=dict(
			short_description='Connection Status Approved', admin=True, form=ConnectionStatusApproved
		),
		permission='ujjwala.can_approve_connection',
	)
	def connection_status_approved(self, *args, **kwargs):
		pass


	@fsm_log_description
	@fsm_log_by
	@transition(
		field=status,
		source=UjjwalaV2ApplicationStatus.CONNECTION_APPROVED,
		target=UjjwalaV2ApplicationStatus.LEGAL_DOCUMENTS_COLLECTED,
		custom=dict(short_description='Legal Documents Collected', admin=True, form=LegalDocumentsCollected),
		permission='ujjwala.can_collect_legal_documents',
	)
	def legal_documents_collected(self, *args, **kwargs):
		pass

	@fsm_log_description
	@fsm_log_by
	@transition(
		field=status,
		source=UjjwalaV2ApplicationStatus.LEGAL_DOCUMENTS_COLLECTED,
		target=UjjwalaV2ApplicationStatus.CONNECTION_RELEASED,
		custom=dict(short_description='Connection Release', admin=True, form=ConnectionRelease),
		permission='can_release_connection',
	)
	def connection_release(self, *args, **kwargs):
		pass

	@fsm_log_description
	@fsm_log_by
	@transition(
		field=status,
		source=UjjwalaV2ApplicationStatus.CONNECTION_RELEASED,
		target=UjjwalaV2ApplicationStatus.POST_INSTALLATION_UPLOAD,
		custom=dict(short_description='Post Installation Upload', admin=True, form=PostInstallationUpload),
		permission='ujjwala.can_upload_post_installation',
	)
	def post_installation_upload(self, *args, **kwargs):
		pass

	@fsm_log_description
	@fsm_log_by
	@transition(
		field=status,
		source=UjjwalaV2ApplicationStatus.POST_INSTALLATION_UPLOAD,
		target=UjjwalaV2ApplicationStatus.COMPLETED,
		custom=dict(short_description='Completed', admin=True),
	)
	def completed(self, *args, **kwargs):
		pass

	def send_reminder_for_pre_inspection_upload(self):
		if self.pre_inspection_status in (
				UjjwalaPreInspectionStatus.REUPLOAD,
				UjjwalaPreInspectionStatus.PENDING
		):
			# self.event_installation_upload_channel_whatsapp()
			return True
		return False

	@fsm_log_description
	@fsm_log_by
	@transition(
		field=pre_inspection_status,
		source=[UjjwalaPreInspectionStatus.PENDING, UjjwalaPreInspectionStatus.REUPLOAD],
		target=UjjwalaPreInspectionStatus.SUBMITTED,
		custom=dict(
			short_description='Upload Pre Inspection', admin=False
		),
	)
	def upload_pre_inspection(self, *args, **kwargs):
		pass

	@fsm_log_description
	@fsm_log_by
	@transition(
		field=pre_inspection_status,
		source=UjjwalaPreInspectionStatus.SUBMITTED,
		target=GET_STATE(
			lambda self, **kwargs: \
					UjjwalaPreInspectionStatus.ACCEPTED \
							if kwargs.get("verified") else UjjwalaPreInspectionStatus.REUPLOAD,
			states=[
				UjjwalaPreInspectionStatus.ACCEPTED,
				UjjwalaPreInspectionStatus.REUPLOAD
			]
		),
		custom=dict(
			short_description='Review Pre Inspection', admin=True
		),
	)
	def accept_pre_inspection(self, *args, **kwargs):
		self.documents_reupload_remarks = kwargs.get('remarks')
		self.documents_required_for_reupload = kwargs.get('documents_required_for_reupload')

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
