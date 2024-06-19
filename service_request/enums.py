from django.db import models


class ServiceRequestTypeEnum(models.TextChoices):
	CHANGE_PHONE_NUMBER = 'CHANGE_PHONE_NUMBER', 'Change Phone Number'
	UID_UPLOAD_FOR_EKYC = 'UID_UPLOAD_FOR_EKYC', 'UID Upload For EKyc'
	UPDATE_ADDRESS = 'UPDATE_ADDRESS', 'Update Address'
	UPDATE_BANK_DETAILS = 'UPDATE_BANK_DETAILS', 'Update Bank Details'
	CHANGE_CYLINDER_TYPE = 'CHANGE_CYLINDER_TYPE', 'Change Cylinder Type'


class ServiceRequestTypeStatusEnum(models.TextChoices):
	PENDING = 'PENDING', 'Pending'
	COMPLETED = 'COMPLETED', 'COMPLETED'
	REJECTED = 'REJECTED', 'Rejected'
