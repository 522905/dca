from django.db import models


class UjjwalaApplicationDocumentsEnum(models.TextChoices):
	CUSTOMER_PHOTO = 'CUSTOMER_PHOTO', 'Customer Photo'
	BANK_DETAIL = 'BANK_DETAIL', 'Bank Detail'
	OTHER_ID_PROOF = 'OTHER_ID_PROOF', 'Other Id Proof'
	SV = 'SV', 'Subscription Voucher'
	CONNECTION_DETAIL = 'CONNECTION_DETAIL', 'Connection Detail'
	KITCHEN_PHOTO = 'KITCHEN_PHOTO', 'Kitchen Photo'
	CUSTOMER_IN_KITCHEN = 'CUSTOMER_IN_KITCHEN', 'Customer In Kitchen'
	MAIN_GATE = 'MAIN_GATE', 'Main Gate'
	WITNESS_PHOTO = 'WITNESS_PHOTO', 'Witness Photo'
	MECHANIC_PHOTO = 'MECHANIC_PHOTO', 'Mechanic Photo'
	CUSTOMER_SIGNATURE = 'CUSTOMER_SIGNATURE', 'Customer Signature'
	WITNESS_SIGNATURE = 'WITNESS_SIGNATURE', 'Witness Signature'
	DEATH_CERTIFICATE = 'DEATH_CERTIFICATE', 'Death Certificate'
	DIVORCE_DOCUMENT = 'DIVORCE_DOCUMENT', 'Divorce Document'
	SAFETY_AUDIO = 'SAFETY_AUDIO', 'Safety Audio'

	@classmethod
	def get_skipped_additional_choices(cls):

		ret = []

		for e in cls:
			if not e in ('SV', 'CONNECTION_DETAIL', 'KITCHEN_PHOTO'):
				ret.append((e.value, e.label))
		return ret

	@classmethod
	def get_only_additional_choices(cls):
		ret = []

		for e in cls:
			if e in ('SV', 'CONNECTION_DETAIL', 'KITCHEN_PHOTO'):
				ret.append((e.value, e.label))
		return ret


class UserDocumentsEnum(models.TextChoices):
	PROFILE_PHOTO = 'PROFILE_PHOTO', 'Profile Photo'
	SIGNATURE = 'SIGNATURE', 'Signature'


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


class ResidentialStatusEnum(models.TextChoices):
	LIVING_ALONE = 'LIVING_ALONE', 'Living Alone'
	LIVING_WITH_FAMILY = 'LIVING_WITH_FAMILY', 'Living With Family'


class RoboSdmsDedeupStatusEnum(models.TextChoices):
	NOT_PROCESSED = 'NOT_PROCESSED', 'Not Processed'
	PROCESSED_AND_UNIQUE = 'PROCESSED_AND_UNIQUE', 'Processed and Unique'
	PROCESSED_AND_DUPLICATE = 'PROCESSED_AND_DUPLICATE', 'Processed and Duplicate'
	PROCESS_MANUAL = 'PROCESS_MANUAL', 'Process Manual'


class UjjwalaV2ApplicationStatus(models.TextChoices):
	DOCUMENTS_UPLOADED = 'DOCUMENTS_UPLOADED', 'Documents Uploaded'
	DOCUMENTS_REUPLOAD = 'DOCUMENTS_REUPLOAD', 'Documents Reupload'
	EKYC_REJECTED = 'EKYC_REJECTED', 'E-KYC Rejected'
	EKYC_ACCEPTED = 'EKYC_ACCEPTED', 'E-KYC Accepted'
	LEGAL_DOCUMENTS_UPLOAD = 'LEGAL_DOCUMENTS_UPLOAD', 'Legal Documents Upload'
	MANUAL_LEGAL_DOCUMENTS_UPLOAD = 'MANUAL_LEGAL_DOCUMENTS_UPLOAD', 'Manual Legal Documents Upload'
	# CONNECTION_APPROVED = 'CONNECTION_APPROVED', 'Connection Approved'
	# CONNECTION_REJECTED = 'CONNECTION_REJECTED', 'Connection Rejected'
	LEGAL_DOCUMENTS_COLLECTED = 'LEGAL_DOCUMENTS_COLLECTED', 'Legal Documents Collected'
	EDIT_APPLICATION = 'EDIT_APPLICATION', 'Edit Application'
	APPLICATION_REJECTED = 'APPLICATION_REJECTED', 'Application Rejected'
	OMC_CLEARED = 'OMC_CLEARED', 'OMC Cleared'
	OMC_REJECTED = 'OMC_REJECTED', 'OMC Rejected'
	NIC_ERROR = 'NIC_ERROR', 'NIC Error'
	NIC_CLEARED = 'NIC_CLEARED', 'NIC Cleared'
	INSUFFICIENT_ADDRESS = 'INSUFFICIENT_ADDRESS', 'Insufficient Address'
	DO_MANUAL_OPERATION = 'DO_MANUAL_OPERATION', 'Do Manual Operation'
	PRE_INSPECTION_SUBMITTED = 'PRE_INSPECTION_SUBMITTED', 'Pre Inspection Submitted'
	PRE_INSPECTION_REUPLOAD = 'PRE_INSPECTION_REUPLOAD', 'Pre Inspection Reupload'
	PRE_INSPECTION_ACCEPTED = 'PRE_INSPECTION_ACCEPTED', 'Pre Inspection Accepted'
	CONNECTION_RELEASED = 'CONNECTION_RELEASED', 'Connection Released'
	POST_INSTALLATION_UPLOAD = 'POST_INSTALLATION_UPLOAD', 'Post Installation Upload'
	COMPLETED = 'COMPLETED', 'Completed'


class RejectionTypeEnum(models.TextChoices):
	EKYC = 'EKYC', 'Ekyc'
	APPLICATION = 'APPLICATION', 'Application'
	CONNECTION = 'CONNECTION', 'Connection'


class ManualOperationCodeEnum(models.TextChoices):
	UID_MISMATCH_SDMS = 'UID_MISMATCH_SDMS', 'UID mismatch SDMS'
	NO_PRIMARY_RECORD = 'NO_PRIMARY_RECORD', 'No Primary Record'
	NO_UID_FOUND = 'NO_UID_FOUND', 'No UID Found'
	UID_RELATION_MISMATCH = 'UID_RELATION_MISMATCH', 'UID relation mismatch'
	ROBO_GOT_ERROR_ALERT = 'ROBO_GOT_ERROR_ALERT', 'Robo Got Error Alert'


class OtpStatusEnum(models.TextChoices):
	SENT = 'SENT', 'Sent'
	RESENT = 'RESENT', 'Resent'
	SUBMITTED = 'SUBMITTED', 'Submitted'
	ACCEPTED = 'ACCEPTED', 'Accepted'
	REJECTED = 'REJECTED', 'Rejected'


class PreInspectionStatusEnum(models.TextChoices):
	ALLOCATED = 'ALLOCATED', 'Allocated'
	OTP_VERIFIED = 'OTP_VERIFIED', 'Otp Verified'
	KITCHEN_PHOTO = 'KITCHEN_PHOTO', 'Kitchen Photo'
	SAFETY_AUDIO = 'SAFETY_AUDIO', 'Safety Audio'
	PREVIEW_INSPECTION = 'PREVIEW_INSPECTION', 'Preview Inspection'
	SUBMITTED = 'SUBMITTED', 'Submitted'
	ACCEPTED = 'ACCEPTED', 'Accepted'
	REUPLOAD = 'REUPLOAD', 'Reupload'
	REJECTED = 'REJECTED', 'Rejected'
