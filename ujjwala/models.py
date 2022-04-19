from django.db import models
from django_fsm import FSMField, transition, GET_STATE
from django_fsm_log.decorators import fsm_log_description, fsm_log_by
from organizations.models import Organization

from teams.models import ServiceLocations
from ujjwala.enums import MaritalStatusEnum, ResidentialStatusEnum, UjjwalaUidMobileStatusEnum, \
	UjjwalaPreInspectionStatus, UjjwalaV2ApplicationStatus, UjjwalaApplicationDocumentsEnum, FamilyMemberRelationEnum
from ujjwala.forms import EkycAcceptedOrRejected, \
	LegalDocumentsCollected, LegalDocumentsUpload, ConnectionStatusUpdate, \
	ConnectionRelease, PostInstallationUpload


class UjjwalaV2Application(models.Model):
	created_on = models.DateTimeField(auto_now_add=True)
	updated_on = models.DateTimeField(auto_now=True)
	marital_status = models.CharField(max_length=25, choices=MaritalStatusEnum.choices)
	residential_status = models.CharField(max_length=25, choices=ResidentialStatusEnum.choices)
	name = models.CharField(max_length=50)
	address = models.TextField()
	contact_mobile = models.CharField(max_length=10)
	uid_linked_mobile = models.CharField(max_length=10, null=True, blank=True)
	uid_mobile_status = models.CharField(max_length=25, choices=UjjwalaUidMobileStatusEnum.choices)
	referral_code = models.CharField(max_length=16, null=True, blank=True)
	service_team = models.ForeignKey(Organization, on_delete=models.CASCADE, null=True, blank=True)
	service_location = models.ForeignKey(ServiceLocations, on_delete=models.CASCADE, null=True, blank=True)
	version = models.CharField(max_length=2, default='V1')

	status = FSMField(
		default=UjjwalaV2ApplicationStatus.DOCUMENTS_UPLOADED,
		choices=UjjwalaV2ApplicationStatus.choices
	)

	pre_inspection_status = FSMField(
		default=UjjwalaPreInspectionStatus.PENDING,
		choices=UjjwalaPreInspectionStatus.choices
	)

	sv = models.CharField(max_length=25, null=True, blank=True)
	last_execution_state = models.CharField(max_length=50, null=True, blank=True)

	# def submit(self, *args, **kwargs):
	# 	"""
	# 	Called when application is uploaded via api to change state to submitted
	# 	"""
	#
	# # self.event_submit_channel_whatsapp()
	# # self.send_reminder_for_installation_upload()

	@fsm_log_description
	@fsm_log_by
	@transition(
		field=status,
		source=UjjwalaV2ApplicationStatus.DOCUMENTS_UPLOADED,
		target=GET_STATE(
			lambda self, **kwargs: \
					UjjwalaV2ApplicationStatus.EKYC_ACCEPTED \
							if kwargs.get(
						"ekyc_accepted") == 'ACCEPTED' else UjjwalaV2ApplicationStatus.EKYC_REJECTED,
			states=[
				UjjwalaV2ApplicationStatus.EKYC_ACCEPTED,
				UjjwalaV2ApplicationStatus.EKYC_REJECTED
			]
		),
		custom=dict(short_description='E-KYC Accepted Or Rejected', admin=True, form=EkycAcceptedOrRejected),
	)
	def ekyc_accepted_or_rejected(self, *args, **kwargs):
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
	)
	def legal_documents_upload(self, *args, **kwargs):
		pass

	@fsm_log_description
	@fsm_log_by
	@transition(
		field=status,
		source=UjjwalaV2ApplicationStatus.LEGAL_DOCUMENTS_UPLOAD,
		target=GET_STATE(
			lambda self, **kwargs: \
					UjjwalaV2ApplicationStatus.CONNECTION_APPROVED \
							if kwargs.get(
						"connection_approved") == 'APPROVED' else UjjwalaV2ApplicationStatus.CONNECTION_REJECTED,
			states=[
				UjjwalaV2ApplicationStatus.CONNECTION_APPROVED,
				UjjwalaV2ApplicationStatus.CONNECTION_REJECTED
			]
		),
		custom=dict(
			short_description='Update Connection Status', admin=True, form=ConnectionStatusUpdate
		),
	)
	def update_connection_status(self, *args, **kwargs):
		pass

	@fsm_log_description
	@fsm_log_by
	@transition(
		field=status,
		source=UjjwalaV2ApplicationStatus.CONNECTION_APPROVED,
		target=UjjwalaV2ApplicationStatus.LEGAL_DOCUMENTS_COLLECTED,
		custom=dict(short_description='Legal Documents Collected', admin=True, form=LegalDocumentsCollected),
	)
	def legal_documents_collected(self, *args, **kwargs):
		pass

	@fsm_log_description
	@fsm_log_by
	@transition(
		field=status,
		source=UjjwalaV2ApplicationStatus.LEGAL_DOCUMENTS_COLLECTED,
		target=UjjwalaV2ApplicationStatus.CONNECTION_RELEASE,
		custom=dict(short_description='Connection Release', admin=True, form=ConnectionRelease),
	)
	def connection_release(self, *args, **kwargs):
		pass

	@fsm_log_description
	@fsm_log_by
	@transition(
		field=status,
		source=UjjwalaV2ApplicationStatus.CONNECTION_RELEASE,
		target=UjjwalaV2ApplicationStatus.POST_INSTALLATION_UPLOAD,
		custom=dict(short_description='Post Installation Upload', admin=True, form=PostInstallationUpload),
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


class FamilyMembers(models.Model):
	parent = models.ForeignKey(UjjwalaV2Application, on_delete=models.CASCADE, related_name='family_members', null=True)
	name = models.CharField(max_length=50)
	relation = models.CharField(max_length=25, choices=FamilyMemberRelationEnum.choices)
	dob = models.DateField()
	uid_no = models.CharField(max_length=12, null=True, blank=True)
	uid_front_link = models.URLField()
	uid_back_link = models.URLField()

	def get_gender(self):
		if self.relation in (
				FamilyMemberRelationEnum.SELF,
				FamilyMemberRelationEnum.MOTHER,
				FamilyMemberRelationEnum.DAUGHTER
		):
			return "Female"
		else:
			return "Male"


class UjjwalaApplicationDocuments(models.Model):
	parent = models.ForeignKey(UjjwalaV2Application, on_delete=models.CASCADE, related_name='documents', null=True)
	type = models.CharField(max_length=25, choices=UjjwalaApplicationDocumentsEnum.choices)
	link = models.URLField()
