from django.db import models
from django_fsm import FSMField, transition, GET_STATE
from django_fsm_log.decorators import fsm_log_description, fsm_log_by

from ujjwala.forms import EkycInitiated, EkycAcceptedOrRejected, NewConnectionAcceptedOrRejected, \
	LegalDocumentsCollected, SvReleased


class UjjwalaApplicationDocumentsEnum(models.TextChoices):
	CUSTOMER_PHOTO = 'CUSTOMER_PHOTO', 'Customer Photo'
	BANK_DETAIL = 'BANK_DETAIL', 'Bank Detail'
	OTHER_ID_PROOF = 'OTHER_ID_PROOF', 'Other Id Proof'
	SV = 'SV', 'Subscription Voucher'
	CONNECTION_DETAIL = 'CONNECTION_DETAIL', 'Connection Detail'
	KITCHEN_PHOTO = 'KITCHEN_PHOTO', 'Kitchen Photo'


class UjjwalaUidMobileStatusEnum(models.TextChoices):
	LINKED_WITH_SAME_MOBILE = 'LINKED_WITH_SAME_MOBILE', 'Linked With Same Mobile'
	LINKED_WITH_OTHER_MOBILE = 'LINKED_WITH_OTHER_MOBILE', 'Linked With Other Mobile'
	MOBILE_NOT_AVAILABLE = 'MOBILE_NOT_AVAILABLE', 'Mobile Not Available'


class FamilyMemberRelationEnum(models.TextChoices):
	SELF = 'SELF', 'Self'
	FATHER = 'FATHER', 'Father'
	MOTHER = 'MOTHER', 'Mother'
	HUSBAND = 'HUSBAND', 'Husband'
	SON = 'SON', 'Son'
	DAUGHTER = 'DAUGHTER', 'Daughter'


class MaritalStatusEnum(models.TextChoices):
	MARRIED = 'MARRIED', 'Married'
	UNMARRIED = 'UNMARRIED', 'Unmarried'
	DIVORCED = 'DIVORCED', 'Divorced'
	WIDOW = 'WIDOW', 'Widow'


class UjjwalaV2ApplicationStatus(models.TextChoices):
	DOCUMENTS_UPLOADED = 'DOCUMENTS_UPLOADED', 'Documents Uploaded'
	DOCUMENTS_REUPLOAD = 'DOCUMENTS_REUPLOAD', 'Documents Reupload'
	EKYC_INITIATED = 'EKYC_INITIATED', 'E-KYC Initiated'
	EKYC_REJECTED = 'EKYC_REJECTED', 'E-KYC Rejected'
	EKYC_ACCEPTED = 'EKYC_ACCEPTED', 'E-KYC Accepted'
	CONNECTION_REJECTED = 'CONNECTION_REJECTED', 'Connection Rejected'
	NEW_CONNECTION_ACCEPTED = 'NEW_CONNECTION_ACCEPTED', 'New Connection Accepted'
	LEGAL_DOCUMENTS_COLLECTED = 'LEGAL_DOCUMENTS_COLLECTED', 'Legal Documents Collected'
	SV_RELEASED = 'SV_RELEASED', 'SV Released'
	COMPLETED = 'COMPLETED', 'Completed'


class UjjwalaInstallationStatus(models.TextChoices):
	PENDING = 'PENDING', 'Pending',
	SUBMITTED = 'SUBMITTED', 'Submitted',
	ACCEPTED = 'ACCEPTED', 'Accepted',
	REUPLOAD = 'REUPLOAD', 'Reupload'


class UjjwalaV2Application(models.Model):
	marital_status = models.CharField(max_length=25, choices=MaritalStatusEnum.choices)
	name = models.CharField(max_length=50)
	address = models.TextField()
	contact_mobile = models.CharField(max_length=10)
	uid_linked_mobile = models.CharField(max_length=10)
	uid_mobile_status = models.CharField(max_length=25, choices=UjjwalaUidMobileStatusEnum.choices)
	referral_code = models.CharField(max_length=16, null=True, blank=True)

	status = FSMField(
		default=UjjwalaV2ApplicationStatus.DOCUMENTS_UPLOADED,
		choices=UjjwalaV2ApplicationStatus.choices
	)

	installation_status = FSMField(
		default=UjjwalaInstallationStatus.PENDING,
		choices=UjjwalaInstallationStatus.choices
	)
	sv = models.CharField(max_length=25, null=True, blank=True)
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
		source=[
			UjjwalaV2ApplicationStatus.DOCUMENTS_UPLOADED,
			UjjwalaV2ApplicationStatus.DOCUMENTS_REUPLOAD
		],
		target=GET_STATE(
			lambda self, **kwargs: \
					UjjwalaV2ApplicationStatus.EKYC_INITIATED \
							if kwargs.get(
						"reupload_documents") == 'NO' else UjjwalaV2ApplicationStatus.DOCUMENTS_REUPLOAD,
			states=[
				UjjwalaV2ApplicationStatus.DOCUMENTS_REUPLOAD,
				UjjwalaV2ApplicationStatus.EKYC_INITIATED
			]
		),
		custom=dict(short_description='E-KYC Initiated', admin=True, form=EkycInitiated),
	)
	def ekyc_initiated(self, *args, **kwargs):
		pass

	@fsm_log_description
	@fsm_log_by
	@transition(
		field=status,
		source=UjjwalaV2ApplicationStatus.EKYC_INITIATED,
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
		target=GET_STATE(
			lambda self, **kwargs: \
					UjjwalaV2ApplicationStatus.NEW_CONNECTION_ACCEPTED \
						if kwargs.get(
						"new_connection_accepted") == 'ACCEPTED' else UjjwalaV2ApplicationStatus.CONNECTION_REJECTED,
			states=[
				UjjwalaV2ApplicationStatus.NEW_CONNECTION_ACCEPTED,
				UjjwalaV2ApplicationStatus.CONNECTION_REJECTED
			]
		),
		custom=dict(
			short_description='Connection Accpeted Or Rejected', admin=True, form=NewConnectionAcceptedOrRejected
		),
	)
	def connection_accepted(self, *args, **kwargs):
		pass

	@fsm_log_description
	@fsm_log_by
	@transition(
		field=status,
		source=UjjwalaV2ApplicationStatus.NEW_CONNECTION_ACCEPTED,
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
		target=UjjwalaV2ApplicationStatus.SV_RELEASED,
		custom=dict(short_description='SV Released', admin=True, form=SvReleased),
	)
	def sv_released(self, *args, **kwargs):
		pass

	@fsm_log_description
	@fsm_log_by
	@transition(
		field=status,
		source=UjjwalaV2ApplicationStatus.SV_RELEASED,
		target=UjjwalaV2ApplicationStatus.COMPLETED,
		custom=dict(short_description='Completed', admin=True),
	)
	def completed(self, *args, **kwargs):
		pass

	def send_reminder_for_installation_upload(self):
		if self.installation_status in (
				UjjwalaInstallationStatus.REUPLOAD,
				UjjwalaInstallationStatus.PENDING
		):
			# self.event_installation_upload_channel_whatsapp()
			return True
		return False

	@fsm_log_description
	@fsm_log_by
	@transition(
		field=installation_status,
		source=[UjjwalaInstallationStatus.PENDING, UjjwalaInstallationStatus.REUPLOAD],
		target=UjjwalaInstallationStatus.SUBMITTED,
		custom=dict(
			short_description='Upload Installation', admin=False
		),
	)
	def upload_installation(self, *args, **kwargs):
		pass

	@fsm_log_description
	@fsm_log_by
	@transition(
		field=installation_status,
		source=UjjwalaInstallationStatus.SUBMITTED,
		target=GET_STATE(
			lambda self, **kwargs: \
					UjjwalaInstallationStatus.ACCEPTED \
							if kwargs.get("verified") else UjjwalaInstallationStatus.REUPLOAD,
			states=[
				UjjwalaInstallationStatus.ACCEPTED,
				UjjwalaInstallationStatus.REUPLOAD
			]
		),
		# custom=dict(
		# 	short_description='Review Installation', admin=True, form=InstallationReviewForm
		# ),
		custom=dict(
			short_description='Review Installation', admin=True
		),
	)
	def accept_installation(self, *args, **kwargs):
		self.documents_reupload_remarks = kwargs.get('remarks')
		self.documents_required_for_reupload = kwargs.get('documents_required_for_reupload')


class FamilyMembers(models.Model):
	parent = models.ForeignKey(UjjwalaV2Application, on_delete=models.CASCADE, related_name='family_members', null=True)
	name = models.CharField(max_length=50)
	relation = models.CharField(max_length=25, choices=FamilyMemberRelationEnum.choices)
	dob = models.DateField()
	uid_front_link = models.URLField()
	uid_back_link = models.URLField()


class UjjwalaApplicationDocuments(models.Model):
	parent = models.ForeignKey(UjjwalaV2Application, on_delete=models.CASCADE, related_name='documents', null=True)
	type = models.CharField(max_length=25, choices=UjjwalaApplicationDocumentsEnum.choices)
	link = models.URLField()
