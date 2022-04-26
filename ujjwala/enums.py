from django.db import models


class UjjwalaApplicationDocumentsEnum(models.TextChoices):
	CUSTOMER_PHOTO = 'CUSTOMER_PHOTO', 'Customer Photo'
	BANK_DETAIL = 'BANK_DETAIL', 'Bank Detail'
	OTHER_ID_PROOF = 'OTHER_ID_PROOF', 'Other Id Proof'
	SV = 'SV', 'Subscription Voucher'
	CONNECTION_DETAIL = 'CONNECTION_DETAIL', 'Connection Detail'
	KITCHEN_PHOTO = 'KITCHEN_PHOTO', 'Kitchen Photo'
	CUSTOMER_SIGNATURE = 'CUSTOMER_SIGNATURE', 'Customer Signature'
	DEATH_CERTIFICATE = 'DEATH_CERTIFICATE', 'Death Certificate'
	DIVORCE_DOCUMENT = 'DIVORCE_DOCUMENT', 'Divorce Document'


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


class UjjwalaV2ApplicationStatus(models.TextChoices):
	DOCUMENTS_UPLOADED = 'DOCUMENTS_UPLOADED', 'Documents Uploaded'
	DOCUMENTS_REUPLOAD = 'DOCUMENTS_REUPLOAD', 'Documents Reupload'
	# EKYC_INITIATED = 'EKYC_INITIATED', 'E-KYC Initiated'
	EKYC_REJECTED = 'EKYC_REJECTED', 'E-KYC Rejected'
	EKYC_ACCEPTED = 'EKYC_ACCEPTED', 'E-KYC Accepted'
	LEGAL_DOCUMENTS_UPLOAD = 'LEGAL_DOCUMENTS_UPLOAD', 'Legal Documents Upload'
	CONNECTION_APPROVED = 'CONNECTION_APPROVED', 'Connection Approved'
	CONNECTION_REJECTED = 'CONNECTION_REJECTED', 'Connection Rejected'
	LEGAL_DOCUMENTS_COLLECTED = 'LEGAL_DOCUMENTS_COLLECTED', 'Legal Documents Collected'
	CONNECTION_RELEASED = 'CONNECTION_RELEASED', 'Connection Released'
	POST_INSTALLATION_UPLOAD = 'POST_INSTALLATION_UPLOAD', 'Post Installation Upload'
	COMPLETED = 'COMPLETED', 'Completed'
	EDIT_APPLICATION = 'EDIT_APPLICATION', 'Edit Application'
	APPLICATION_REJECTED = 'APPLICATION_REJECTED', 'Application Rejected'


class UjjwalaPreInspectionStatus(models.TextChoices):
	PENDING = 'PENDING', 'Pending',
	SUBMITTED = 'SUBMITTED', 'Submitted',
	ACCEPTED = 'ACCEPTED', 'Accepted',
	REUPLOAD = 'REUPLOAD', 'Reupload'


class RejectionTypeEnum(models.TextChoices):
	EKYC = 'EKYC', 'Ekyc'
	APPLICATION = 'APPLICATION', 'Application'
	CONNECTION = 'CONNECTION', 'Connection'
