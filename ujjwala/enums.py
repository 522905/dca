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
	LEGAL_DOC_ANNEXURE_14_POINTS = 'LEGAL_DOC_ANNEXURE_14_POINTS', 'Legal Doc Annexure 14 Points'
	LEGAL_DOC_FAMILY_OCCUPANCY = 'LEGAL_DOC_FAMILY_OCCUPANCY', 'Legal Doc Family Occupancy'
	LEGAL_DOC_PRE_INSPECTION = 'LEGAL_DOC_PRE_INSPECTION', 'Legal Doc Pre Inspection'
	PHYSICAL_LEGAL_DOCUMENT = 'PHYSICAL_LEGAL_DOCUMENT', 'Physical Legal Document'
	DISBURSEMENT_PHOTO = 'DISBURSEMENT_PHOTO', 'Disbursement Photo'
	SOCIAL_MEDIA_PHOTO = 'SOCIAL_MEDIA_PHOTO', 'Social Media Photo'
	INSTALLATION_KITCHEN_PHOTO = 'INSTALLATION_KITCHEN_PHOTO', 'Installation Kitchen Photo'
	INSTALLATION_STOVE_WITH_STICKER = 'INSTALLATION_STOVE_WITH_STICKER', 'Installation Stove With Sticker'

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
	IOCL_INVESTIGATION_REQUIRED = 'IOCL_INVESTIGATION_REQUIRED', 'Iocl Investigation Required'
	ENRICH_REJECTION_DETAILS = 'ENRICH_REJECTION_DETAILS', 'Enrich Rejection Details'


class UjjwalaV2ApplicationStatus(models.TextChoices):
	DOCUMENTS_UPLOADED = 'DOCUMENTS_UPLOADED', 'Documents Uploaded'
	DOCUMENTS_REUPLOAD = 'DOCUMENTS_REUPLOAD', 'Documents Reupload'
	EKYC_REJECTED = 'EKYC_REJECTED', 'E-KYC Rejected'
	EKYC_ACCEPTED = 'EKYC_ACCEPTED', 'E-KYC Accepted'
	LEGAL_DOCUMENTS_UPLOAD = 'LEGAL_DOCUMENTS_UPLOAD', 'Legal Documents Upload'
	MANUAL_LEGAL_DOCUMENTS_UPLOAD = 'MANUAL_LEGAL_DOCUMENTS_UPLOAD', 'Manual Legal Documents Upload'
	EDIT_APPLICATION = 'EDIT_APPLICATION', 'Edit Application'
	APPLICATION_REJECTED = 'APPLICATION_REJECTED', 'Application Rejected'
	OMC_CLEARED = 'OMC_CLEARED', 'OMC Cleared'
	OMC_REJECTED = 'OMC_REJECTED', 'OMC Rejected'
	NIC_ERROR = 'NIC_ERROR', 'NIC Error'
	NIC_CLEARED = 'NIC_CLEARED', 'NIC Cleared'
	INSUFFICIENT_ADDRESS = 'INSUFFICIENT_ADDRESS', 'Insufficient Address'
	MATERIAL_DELIVERED = 'MATERIAL_DELIVERED', 'Material Delivered'
	INSTALLED = 'INSTALLED', 'Installed'
	DO_MANUAL_OPERATION = 'DO_MANUAL_OPERATION', 'Do Manual Operation'
	AUDIT_APPLICATION = 'AUDIT_APPLICATION', 'Audit Application'
	COMPLETED = 'COMPLETED', 'Completed'
	READY_FOR_DISBURSEMENT = 'READY_FOR_DISBURSEMENT', 'Ready For Disbursement'
	NIC_ERROR_INSUFFICIENT_ADDRESS = 'NIC_ERROR_INSUFFICIENT_ADDRESS', 'Nic Error Insufficient Address'
	NIC_ERROR_UPDATE_ADDRESS = 'NIC_ERROR_UPDATE_ADDRESS', 'Nic Error Update Address'
	NIC_ERROR_ADDRESS_ACCEPTED = 'NIC_ERROR_ADDRESS_ACCEPTED', 'Nic Error Address Accepted'
	NIC_ERROR_APPROVED = 'NIC_ERROR_APPROVED', 'Nic Error Approved'


class RejectionTypeEnum(models.TextChoices):
	UNDER_AGE = 'UNDER_AGE', 'Under Age'
	INSUFFICIENT_DATA = 'INSUFFICIENT_DATA', 'Insufficient Data'
	RELATION_WITH_OTHER_DISTRIBUTOR = 'RELATION_WITH_OTHER_DISTRIBUTOR', 'Relation With Other Distributor'
	EXISTING_UJJWALA_APPLICATION = 'EXISTING_UJJWALA_APPLICATION', 'Existing Ujjwala Application'
	EKYC = 'EKYC', 'Ekyc'
	OMC = 'OMC', 'Omc'
	SDMS_DEDUPE = 'SDMS_DEDUPE', 'Sdms Dedupe'
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
	CHANGE_ADDRESS = 'CHANGE_ADDRESS', 'Change Address'
	KITCHEN_PHOTO = 'KITCHEN_PHOTO', 'Kitchen Photo'
	SAFETY_AUDIO = 'SAFETY_AUDIO', 'Safety Audio'
	PREVIEW_INSPECTION = 'PREVIEW_INSPECTION', 'Preview Inspection'
	SUBMITTED = 'SUBMITTED', 'Submitted'
	ACCEPTED = 'ACCEPTED', 'Accepted'
	REUPLOAD = 'REUPLOAD', 'Reupload'
	REJECTED = 'REJECTED', 'Rejected'


class PreInspectionTypeEnum(models.TextChoices):
	SELF = 'SELF', 'Self'
	MECHANIC = 'MECHANIC', 'Mechanic'


class ConnectionDisbursementStatusEnum(models.TextChoices):
	LEGAL_DOCUMENTS_PENDING = 'LEGAL_DOCUMENTS_PENDING', 'Legal Documents Not Uploaded (Upload Pending)'
	LEGAL_DOCUMENTS_REVIEW = 'LEGAL_DOCUMENTS_REVIEW', 'Legal Documents In Review (Review Pending)'
	LEGAL_DOCUMENTS_ACCEPTED = 'LEGAL_DOCUMENTS_ACCEPTED', 'Legal Documents Accepted'
	OTP_VERIFIED = 'OTP_VERIFIED', 'Otp Verified'
	SV_LABEL_PRINT = 'SV_LABEL_PRINT', 'Social Media Photo Pending'
	SOCIAL_MEDIA_UPDATES = 'SOCIAL_MEDIA_UPDATES', 'Material Delivery (OTP & Photo Pending)'
	# DISBURSEMENT_PHOTO_UPLOAD = 'DISBURSEMENT_PHOTO_UPLOAD', 'Disbursement Photo Upload'
	MATERIAL_DELIVERY_OTP_VERIFIED = 'MATERIAL_DELIVERY_OTP_VERIFIED', 'Material Delivery (OTP Done, Photo Pending)'
	MATERIAL_DELIVERED = 'MATERIAL_DELIVERED', 'Material Delivered'
	INSTALLATION_MAIN_GATE = 'INSTALLATION_MAIN_GATE', 'Installation Main Gate'
	INSTALLATION_UPLOADED = 'INSTALLATION_UPLOADED', 'Installation Uploaded'


class SchemeOnboardingStatusEnum(models.TextChoices):
	ONBOARD_WITH_BTC = 'ONBOARD_WITH_BTC', 'Onboard With BTC'
	ONBOARD_WITH_NCTC = 'ONBOARD_WITH_NCTC', 'Onboard With NCTC'


class NicClearedCustomerRemarksEnum(models.TextChoices):
	NOT_INTERESTED = 'NOT_INTERESTED', 'Not Interested'
	NOT_APPROACHABLE = 'NOT_APPROACHABLE', 'Not Approachable'
	SCHEDULED_DELIVERY = 'SCHEDULED_DELIVERY', 'Scheduled Delivery'
