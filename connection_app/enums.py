from django.db import models


class ConnectionApplicationLeadCommunicationMode(models.TextChoices):
	WHATSAPP = 'WHATSAPP', 'WhatsApp',
	SMS = 'SMS', 'SMS'


class SalesOrderPortabilityStatusEnum(models.TextChoices):
	DRAFTED = 'DRAFTED', 'Drafted'
	SCHEDULED = 'SCHEDULED', 'Scheduled'
	COMPLETED = 'COMPLETED', 'Completed'
	ERROR = 'ERROR', 'Error'


class ConnectionApplicationProcessType(models.TextChoices):
	NEW_CONNECTION = 'NEW_CONNECTION', 'New Connection',
	REGULARISATION = 'REGULARISATION', 'Regularisation',
	REACTIVATION = 'REACTIVATION', 'Re-Activation'


class PostInspectionActivityTypeEnum(models.TextChoices):
	KITCHEN_PHOTO_UPDATE = 'KITCHEN_PHOTO_UPDATE', 'Kitchen Photo Update',
	MAIN_GATE_PHOTO_UPDATE = 'MAIN_GATE_PHOTO_UPDATE', 'Main Gate Photo Update',
	ADDRESS_UPDATE = 'ADDRESS_UPDATE', 'Address Update'
	PROFILE_PHOTO_UPDATE = 'PROFILE_PHOTO_UPDATE', 'Profile Photo Update'
	UID_PHOTO_UPDATE = 'UID_PHOTO_UPDATE', 'UID Photo Update'
	SURAKSHA_PIPE_UPDATE = 'SURAKSHA_PIPE_UPDATE', 'Suraksha Pipe Update'


class ConnectionApplicationLeadStatus(models.TextChoices):
	EDIT_APPLICATION = 'EDIT_APPLICATION', 'Edit Application',
	SUBMITTED = 'SUBMITTED', 'Submitted',
	NOT_INTERESTED = 'NOT_INTERESTED', 'Not Interested',
	BACK_OFFICE_START = 'BACK_OFFICE_START', 'Back Office Start',
	BACK_OFFICE_END = 'BACK_OFFICE_END', 'Back Office End',
	FRONT_OFFICE = 'FRONT_OFFICE', 'Front Office',
	COMPLETED = 'COMPLETED', 'Completed'
	REUPLOAD = 'REUPLOAD', 'Reupload'
	KITCHEN_PHOTO_UPLOAD = 'KITCHEN_PHOTO_UPLOAD', 'Kitchen Photo Upload'


class ConnectionApplicationGenderEnum(models.TextChoices):
	MALE = 'MALE', 'Male',
	FEMALE = 'FEMALE', 'Female',


class ConnectionInstallationStatus(models.TextChoices):
	PENDING = 'PENDING', 'Pending',
	SUBMITTED = 'SUBMITTED', 'Submitted',
	ACCEPTED = 'ACCEPTED', 'Accepted',
	REUPLOAD = 'REUPLOAD', 'Reupload'


class ApplicationTypeEnum(models.TextChoices):
	NEW_CONNECTION = 'NEW_CONNECTION', 'New Connection'
	BLUE_BOOK = 'BLUE_BOOK', 'Blue Book'
	ADD_ON_CYLINDER = 'ADD_ON_CYLINDER', 'Add On Cylinder'


class ItemCodeEnum(models.TextChoices):
	FC5 = 'FC5', '5 KGs Cylinder'
	FC14 = 'FC14', '14 KGs Cylinder'


class ConnectionTypeEnum(models.TextChoices):
	SINGLE = 'SINGLE', 'Single'
	DOUBLE = 'DOUBLE', 'Double'


class InspectionTypeEnum(models.TextChoices):
	SELF = 'SELF', 'Self'
	MECHANIC = 'MECHANIC', 'Mechanic'


class PostInspectionStatusEnum(models.TextChoices):
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
	REDO = 'REDO', 'Redo'
	STARTED = 'STARTED', 'Started'


class HouseTypeEnum(models.TextChoices):
	OWNHOUSE = 'OWNHOUSE', 'Own House'
	RENT = 'RENT', 'Rent'
	VEHRA = 'VEHRA', 'Vehra'


class ConnectionApplicationDocumentsEnum(models.TextChoices):
	UID_FRONT = 'UID_FRONT', 'UID - Aadhar Card Front'
	UID_BACK = 'UID_BACK', 'UID - Aadhar Card Back'
	CUSTOMER_PHOTO = 'CUSTOMER_PHOTO', 'Customer Photo'
	BANK_DETAIL = 'BANK_DETAIL', 'Bank Detail'
	OTHER_ID_PROOF = 'OTHER_ID_PROOF', 'Other Id Proof'
	SV = 'SV', 'Subscription Voucher'
	CONNECTION_DETAIL = 'CONNECTION_DETAIL', 'Connection Detail'
	KITCHEN_PHOTO = 'KITCHEN_PHOTO', 'Kitchen Photo'
	MAIN_GATE = 'MAIN_GATE', 'Main Gate'
	SURAKSHA_PIPE_PHOTO = 'SURAKSHA_PIPE_PHOTO', 'Suraksha Pipe Photo'
	BANK_SUBSIDY_CERTIFICATE_PHOTO = 'BANK_SUBSIDY_CERTIFICATE_PHOTO', 'Bank Subsidy Certificate Photo'
	GAS_COPY_PHOTO = 'GAS_COPY_PHOTO', 'Gas Copy Photo'

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


class PaymentProfileApprovalStatusEnum(models.TextChoices):
	PENDING = 'PENDING', 'Pending'
	APPROVED = 'APPROVED', 'Approved'
	REJECTED = 'REJECTED', 'Rejected'


class CustomerTypeEnum(models.TextChoices):
	GENERAL = 'GENERAL', 'General'
	UJJWALA = 'UJJWALA', 'Ujjwala'


class SalesOrderInvoiceEnum(models.TextChoices):
	OPEN = 'OPEN', 'Open'


class SalesOrderStatusEnum(models.TextChoices):
	INVOICING_IN_PROGRESS = 'Invoicing In Progress', 'Invoicing In Progress'
	NOT_UPDATED = 'Not Updated', 'Not Updated'
	OPEN = 'Open', 'Open'
	CANCELLED = 'Cancelled', 'Cancelled'
	INVOICED = 'Invoiced', 'Invoiced'
	COMPLETED = 'Completed', 'Completed'
	RETURNED = 'Returned', 'Returned'
	NOT_FOUND = 'Not Found', 'Not Found'


class ConsumerTypeEnum(models.TextChoices):
	DOUBLE_BOTTLE_CONNECTION = "DOUBLE_BOTTLE_CONNECTION", "Double Bottle Connection"
	SINGLE_BOTTLE_CONNECTION = "SINGLE_BOTTLE_CONNECTION", "Single Bottle Connection"


class SubsidyStatusEnum(models.TextChoices):
	START = "START", "Start"


class SchemeOnboardingStatusEnum(models.TextChoices):
	ONBOARDED_WITH_CTC = 'ONBOARDED_WITH_CTC', "Onboarded With CTC"


class DeliveryTypeEnum(models.TextChoices):
	HOME_DELIVERY = 'HOME_DELIVERY', 'Home Delivery'


class OrderSubTypeEnum(models.TextChoices):
	REFILL_ORDER = 'REFILL_ORDER', "Refill Order"


class LeadStatusEnum(models.TextChoices):
	GENERATED = 'GENERATED', 'Generated'
	DUE_ON = 'DUE_ON', 'Due On'
	FOLLOW_UP = 'FOLLOW_UP', 'Follow Up'
	IN_PROGRESS = 'IN_PROGRESS', 'In Progress'
	COMPLETED = 'COMPLETED', 'Completed'


class TemplateEnum(models.TextChoices):
	SERVICE_AREA = 'SERVICE_AREA', 'Service Area'
	CUSTOMER_REGISTER = 'CUSTOMER_REGISTER', 'Customer Register'
	DELIVERY_REGISTER = 'DELIVERY_REGISTER', 'Delivery Register'
	CANCEL_BOOKINGS = 'CANCEL_BOOKINGS', 'Cancel Bookings'
	BULK_IS_DIRTY = 'BULK_IS_DIRTY', 'Bulk Is Dirty'
	UPDATE_DISTRIBUTOR = 'UPDATE_DISTRIBUTOR', 'Update Distributor'


class ImportDataStatusEnum(models.TextChoices):
	SUBMITTED = 'SUBMITTED', 'Submitted'
	PROCESSING = 'PROCESSING', 'Processing'
	TEMPLATE_ERROR = 'TEMPLATE_ERROR', 'Template Error'
	FAILED = 'FAILED', 'Failed'
	COMPLETED = 'COMPLETED', 'Completed'


class ProofTypeEnum(models.TextChoices):
	PAN_CARD = 'PAN CARD', 'Pan Card'
	AADHAR = 'AADHAR', 'Aadhar'
	DRIVING_LICENSE = 'DRIVING_LICENSE', 'Driving License'
