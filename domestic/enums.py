from django.db import models


class DomesticConnectionApplicationLeadCommunicationMode(models.TextChoices):
	WHATSAPP = 'WHATSAPP', 'WhatsApp',
	SMS = 'SMS', 'SMS'


class DomesticConnectionApplicationProcessType(models.TextChoices):
	NEW_CONNECTION = 'NEW_CONNECTION', 'New Connection',
	REGULARISATION = 'REGULARISATION', 'Regularisation',
	REACTIVATION = 'REACTIVATION', 'Re-Activation'


class DomesticConnectionApplicationLeadStatus(models.TextChoices):
	EDIT_APPLICATION = 'EDIT_APPLICATION', 'Edit Application',
	SUBMITTED = 'SUBMITTED', 'Submitted',
	NOT_INTERESTED = 'NOT_INTERESTED', 'Not Interested',
	BACK_OFFICE_START = 'BACK_OFFICE_START', 'Back Office Start',
	BACK_OFFICE_END = 'BACK_OFFICE_END', 'Back Office End',
	FRONT_OFFICE = 'FRONT_OFFICE', 'Front Office',
	COMPLETED = 'COMPLETED', 'Completed'
	REUPLOAD = 'REUPLOAD', 'Reupload'
	KITCHEN_PHOTO_UPLOAD = 'KITCHEN_PHOTO_UPLOAD', 'Kitchen Photo Upload'


class DomesticConnectionInstallationStatus(models.TextChoices):
	PENDING = 'PENDING', 'Pending',
	SUBMITTED = 'SUBMITTED', 'Submitted',
	ACCEPTED = 'ACCEPTED', 'Accepted',
	REUPLOAD = 'REUPLOAD', 'Reupload'


class DomesticConnectionApplicationTypeEnum(models.TextChoices):
	NEW_CONNECTION = 'NEW_CONNECTION', 'New Connection'
	BLUE_BOOK = 'BLUE_BOOK', 'Blue Book'


class DomesticConnectionItemCodeEnum(models.TextChoices):
	FC5 = 'FC5', '5 KGs Cylinder'
	FC14 = 'FC14', '14 KGs Cylinder'


class DomesticConnectionTypeEnum(models.TextChoices):
	SINGLE = 'SINGLE', 'Single'
	DOUBLE = 'DOUBLE', 'Double'


class DomesticConnectionApplicationDocumentsEnum(models.TextChoices):
	UID_FRONT = 'UID_FRONT', 'UID - Aadhar Card Front'
	UID_BACK = 'UID_BACK', 'UID - Aadhar Card Back'
	CUSTOMER_PHOTO = 'CUSTOMER_PHOTO', 'Customer Photo'
	BANK_DETAIL = 'BANK_DETAIL', 'Bank Detail'
	OTHER_ID_PROOF = 'OTHER_ID_PROOF', 'Other Id Proof'
	SV = 'SV', 'Subscription Voucher'
	CONNECTION_DETAIL = 'CONNECTION_DETAIL', 'Connection Detail'
	KITCHEN_PHOTO = 'KITCHEN_PHOTO', 'Kitchen Photo'

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


class DomesticApplicationRejectionTypeEnum(models.TextChoices):
	UNDER_AGE = 'UNDER_AGE', 'Under Age'
	INSUFFICIENT_DATA = 'INSUFFICIENT_DATA', 'Insufficient Data'
	RELATION_WITH_OTHER_DISTRIBUTOR = 'RELATION_WITH_OTHER_DISTRIBUTOR', 'Relation With Other Distributor'
	EXISTING_UJJWALA_APPLICATION = 'EXISTING_UJJWALA_APPLICATION', 'Existing Ujjwala Application'
	EKYC = 'EKYC', 'Ekyc'
	OMC = 'OMC', 'Omc'
	SDMS_DEDUPE = 'SDMS_DEDUPE', 'Sdms Dedupe'
	APPLICATION = 'APPLICATION', 'Application'
	CONNECTION = 'CONNECTION', 'Connection'