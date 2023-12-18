from django.db import models


class ServiceRequestTypeEnum(models.TextChoices):
	CHANGE_PHONE_NUMBER = 'CHANGE_PHONE_NUMBER', 'Change Phone Number'
	UID_UPLOAD_FOR_EKYC = 'UID_UPLOAD_FOR_EKYC', 'UID Upload For EKyc'


class ServiceRequestTypeStatusEnum(models.TextChoices):
	PENDING = 'PENDING', 'Pending'
	SUCCESS = 'SUCCESS', 'Success'
