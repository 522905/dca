from django.db import models


class ConnectionApplicationLeadCommunicationMode(models.TextChoices):
	WHATSAPP = 'WHATSAPP', 'WhatsApp',
	SMS = 'SMS', 'SMS'


class ConnectionApplicationProcessType(models.TextChoices):
	NEW_CONNECTION = 'NEW_CONNECTION', 'New Connection',
	REGULARISATION = 'REGULARISATION', 'Regularisation',
	REACTIVATION = 'REACTIVATION', 'Re-Activation'


class ConnectionApplicationLeadStatus(models.TextChoices):
	EDIT_APPLICATION = 'EDIT_APPLICATION', 'Edit Application',
	SUBMITTED = 'SUBMITTED', 'Submitted',
	NOT_INTERESTED = 'NOT_INTERESTED', 'Not Interested',
	BACK_OFFICE_START = 'BACK_OFFICE_START', 'Back Office Start',
	BACK_OFFICE_END = 'BACK_OFFICE_END', 'Back Office End',
	FRONT_OFFICE = 'FRONT_OFFICE', 'Front Office',
	COMPLETED = 'COMPLETED', 'Completed'
	REUPLOAD = 'REUPLOAD', 'Reupload'


class ConnectionInstallationStatus(models.TextChoices):
	PENDING = 'PENDING', 'Pending',
	SUBMITTED = 'SUBMITTED', 'Submitted',
	ACCEPTED = 'ACCEPTED', 'Accepted',
	REUPLOAD = 'REUPLOAD', 'Reupload'


class ApplicationTypeEnum(models.TextChoices):
	NEW_CONNECTION = 'NEW_CONNECTION', 'New Connection'
	BLUE_BOOK = 'BLUE_BOOK', 'Blue Book'


class ItemCodeEnum(models.TextChoices):
	FC5 = 'FC5', '5 KGs Cylinder'
	FC14 = 'FC14', '14 KGs Cylinder'


class ConnectionTypeEnum(models.TextChoices):
	SINGLE = 'SINGLE', 'Single'
	DOUBLE = 'DOUBLE', 'Double'


class ConnectionApplicationDocumentsEnum(models.TextChoices):
	UID_FRONT = 'UID_FRONT', 'UID - Aadhar Card Front'
	UID_BACK = 'UID_BACK', 'UID - Aadhar Card Back'
	CUSTOMER_PHOTO = 'CUSTOMER_PHOTO', 'Customer Photo'
	BANK_DETAIL = 'BANK_DETAIL', 'Bank Detail'
	OTHER_ID_PROOF = 'OTHER_ID_PROOF', 'Other Id Proof'
	SV = 'SV', 'Subscription Voucher'
	CONNECTION_DETAIL = 'CONNECTION_DETAIL', 'Connection Detail'
	KITCHEN_PHOTO = 'KITCHEN_PHOTO', 'Kitchen Photo'


