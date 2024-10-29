import datetime
import io

import django_rq
import requests
import track
from django.conf import settings
from django.contrib.auth.models import User
from django.contrib.contenttypes.models import ContentType
from django.db import models
from django.template import loader
from django.utils.safestring import mark_safe
from django_fsm import transition, FSMField, GET_STATE
from django_fsm_log.decorators import fsm_log_description, fsm_log_by
from minio import Minio
from taggit.managers import TaggableManager

from communication_log.functions import send_template_link_sms
from communication_log.jobs import move_sv_doc_file_tus_to_minio, move_files_to_minio_processing
from communication_log.models import CommunicationLog
from connection_app.camunda_functions import start_process_fetch_sales_order_details_from_sdms
from connection_app.enums import ApplicationTypeEnum, ItemCodeEnum, ConnectionTypeEnum, \
	ConnectionApplicationProcessType, ConnectionApplicationLeadStatus, ConnectionApplicationDocumentsEnum, \
	ConnectionApplicationLeadCommunicationMode, ConnectionInstallationStatus, \
	PaymentProfileApprovalStatusEnum, CustomerTypeEnum, SalesOrderStatusEnum, InspectionTypeEnum, \
	PostInspectionStatusEnum, PostInspectionActivityTypeEnum, LeadStatusEnum, SalesOrderPortabilityStatusEnum, \
	TemplateEnum, ImportDataStatusEnum
from connection_app.forms import ConnectionVerificationResult, BackOfficeForm, FrontOfficeCompleted, \
	BackOfficeReactivation, BackOfficeRegularisation, \
	BackOfficeNewConnection, DocumentsReupload, InstallationReviewForm
from domestic_app.utils import get_minio_public_url
from reference_data.models import ServiceType, Distributor
from teams.models import SDMSServiceArea
from ujjwala.camunda_functions import is_process_exist_in_camunda
from utils.global_functions import generate_tiny_url

minio_client = Minio(
	settings.MINIO_API_ENDPOINT,
	access_key=settings.MINIO_CREDENTIAL.get("access_key"),
	secret_key=settings.MINIO_CREDENTIAL.get("secret_key"),
	secure=False
)


def get_form_to_load(self):
	if self.process_type == ConnectionApplicationProcessType.NEW_CONNECTION:
		return BackOfficeNewConnection
	elif self.process_type == ConnectionApplicationProcessType.REGULARISATION:
		return BackOfficeRegularisation
	else:
		return BackOfficeReactivation


class ConnectionApplication(models.Model):
	created_on = models.DateTimeField(auto_now_add=True)
	updated_on = models.DateTimeField(auto_now=True)
	name = models.CharField(max_length=255, null=True)
	mobile = models.CharField(max_length=10)
	address = models.TextField(null=True, blank=True)
	address_json = models.JSONField(null=True, blank=True)
	application_type = models.CharField(max_length=25, choices=ApplicationTypeEnum.choices)
	item_code = models.CharField(max_length=25, choices=ItemCodeEnum.choices)
	connection_type = models.CharField(max_length=25, choices=ConnectionTypeEnum.choices, null=True)
	referral_code = models.CharField(max_length=16, null=True, blank=True)

	documents_reupload_remarks = models.TextField(null=True, blank=True)
	documents_required_for_reupload = models.TextField(null=True, blank=True)

	status = FSMField(
		default=ConnectionApplicationLeadStatus.SUBMITTED,
		choices=ConnectionApplicationLeadStatus.choices
	)
	installation_status = FSMField(
		default=ConnectionInstallationStatus.PENDING,
		choices=ConnectionInstallationStatus.choices
	)
	applicant_remarks = models.TextField(null=True, blank=True)
	required_by = models.DateField(null=True, blank=True)
	consumer_id = models.CharField(max_length=25, null=True, blank=True)
	process_type = models.CharField(
		max_length=25, choices=ConnectionApplicationProcessType.choices, null=True, blank=True
	)
	communication_mode = models.CharField(
		max_length=25, choices=ConnectionApplicationLeadCommunicationMode.choices, null=True, blank=True
	)
	last_execution_state = models.CharField(max_length=50, null=True, blank=True)
	filled_by = models.ForeignKey(User, on_delete=models.PROTECT, null=True, blank=True)
	customer_profile = models.ForeignKey("connection_app.CustomerProfile", on_delete=models.CASCADE, null=True)
	customer_remarks = models.TextField(null=True, blank=True)
	# def status(request):
	# 	status = Status.objects.all()

	# 	return render(request, 'connection_app/status.html', {'status': status})

	def lead_details_in_html(self):
		template = loader.get_template("connection_app/application_details_template.html")
		html = template.render({'obj': self})
		return mark_safe(html)

	lead_details_in_html.short_description = 'Lead Details'

	def attachment_details_in_html(self):
		template = loader.get_template("connection_app/application_attachment_details_template.html")
		html = template.render({'obj': self})
		return mark_safe(html)

	lead_details_in_html.short_description = 'Lead Details'


	@ fsm_log_description
	@ fsm_log_by
	@ transition(
		field=status,
		source=[
			ConnectionApplicationLeadStatus.SUBMITTED,
			ConnectionApplicationLeadStatus.BACK_OFFICE_START,
			ConnectionApplicationLeadStatus.BACK_OFFICE_END,
		],
		target=ConnectionApplicationLeadStatus.EDIT_APPLICATION,
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
		source='*',
		target=ConnectionApplicationLeadStatus.REUPLOAD,
		custom=dict(
			short_description='Resend To Customer', admin=True, form=DocumentsReupload
		),
	)
	def send_for_reupload_to_customer(self, *args, **kwargs):
		self.last_execution_state = self.status
		self.documents_reupload_remarks = kwargs.get('remarks')
		self.documents_required_for_reupload = kwargs.get('documents_required_for_reupload')
		self.event_reupload_channel_whatsapp()

	def send_reminder_for_installation_upload(self):
		if self.installation_status in (
				ConnectionInstallationStatus.REUPLOAD,
				ConnectionInstallationStatus.PENDING
		):
			# self.event_installation_upload_channel_whatsapp()
			self.event_installation_upload_channel_sms()
			return True
		return False

	@fsm_log_description
	@fsm_log_by
	@transition(
		field=installation_status,
		source=[ConnectionInstallationStatus.PENDING, ConnectionInstallationStatus.REUPLOAD],
		target=ConnectionInstallationStatus.SUBMITTED,
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
		source=ConnectionInstallationStatus.SUBMITTED,
		target=GET_STATE(
			lambda self, **kwargs: \
				ConnectionInstallationStatus.ACCEPTED \
				if kwargs.get("verified") else ConnectionInstallationStatus.REUPLOAD,
			states=[
				ConnectionInstallationStatus.ACCEPTED,
				ConnectionInstallationStatus.REUPLOAD
			]
		),
		custom=dict(
			short_description='Review Pre-Inspection', admin=True, form=InstallationReviewForm
		),
	)
	def accept_installation(self, *args, **kwargs):

		self.documents_reupload_remarks = kwargs.get('remarks')
		self.documents_required_for_reupload = kwargs.get('documents_required_for_reupload')


	@fsm_log_description
	@fsm_log_by
	@transition(
		field=status,
		source=ConnectionApplicationLeadStatus.EDIT_APPLICATION,
		target=GET_STATE(
			lambda self, **kwargs: self.last_execution_state,
		),
		custom=dict(
			short_description='Update Edits To Application', admin=True
		),
	)
	def restore_edit(self, *args, **kwargs):
		pass

	def submit(self, *args, **kwargs):
		"""
		Called when application is uploaded via api to change state to submitted
		"""
		django_rq.enqueue(
			move_files_to_minio_processing,
			args=(self.id,),
		)
		# Disabled Whatsapp Message To Switch To SMS
		# self.event_submit_channel_whatsapp()

		# Currently we have to use SMS Communication
		self.event_submit_channel_sms()
		self.send_reminder_for_installation_upload()

	def event_submit_channel_whatsapp(self):
		body_text = {
			"countryCode": "+91",
			"phoneNumber": self.mobile,
			"type": "Template",
			"traits": {
				"name": self.name,
			},
			# "callbackData": "some_callback_data",
			"template": {
				"name": "domestic_application_sub_8v",
				"languageCode": "en_GB",	
				"headerValues": [
					# "Alert",  #
				],
				"bodyValues": [
					self.name,
					self.id,
					'{} {} {}'.format(
						self.get_application_type_display(),
						self.get_item_code_display(),
						self.get_connection_type_display()
					),
					"2"
				],
				"buttonValues": {
					"0": [
						"connection-app/connection-application/{}/".format(self.id)
					]
				}
			}
		}
		connection_application_content_type = ContentType.objects.get_for_model(ConnectionApplication)
		data = track.client.post(
			api_key=settings.INTERAKT_API_KEY,
			path="/v1/public/message/",
			body=body_text
		).json()

		if data['result']:
			CommunicationLog.objects.create(
				content_type=connection_application_content_type,
				object_id=self.pk,
				event="submit", channel="whatsapp",
				channel_subscriber=self.mobile,
				message_id=data.get('id')
			)
		else:
			self.event_submit_channel_sms()

	def event_submit_channel_sms(self):
		context = {
			"name": self.name,
			"id": self.id,
			"application_details": '{} {} {}'.format(
				self.get_application_type_display(),
				self.get_item_code_display(),
				self.get_connection_type_display()
			),
			"working_days": "2"
		}

		message = settings.SUBMIT_SMS_TEMPLATE.format(**context)

		x = requests.post("https://4r198.api.infobip.com/sms/2/text/advanced", json={
			"messages": [
				{
					"from": "ARUNGS",
					"destinations": [
						{
							"to": "+91{}".format(self.mobile)
						}
					],

					"text": message,
					"flash": False,

					"regional": {
						"indiaDlt": {
							"principalEntityId": "1101546710000030317",
							# "contentTemplateId": "1107161183026272363"
							"contentTemplateId": "1107164508265878553"
						}
					},
					"notifyUrl": "https://dca.arungas.com/commlog/infobip/webhook/",
					"notifyContentType": "application/json",
					# "callbackData": "DLR callback data",
					# "validityPeriod": 720
				}
			]
		}, headers={
			'Authorization': 'App 140a3abf6dd9134f5defb703a54dfcf0-e3df520b-f144-4282-a174-aa3765c7b438'
		})
		if x.status_code == 200:
			messages = x.json()['messages']
			message_id = messages[0].get('messageId')
			connection_application_content_type = ContentType.objects.get_for_model(ConnectionApplication)
			CommunicationLog.objects.create(
				content_type=connection_application_content_type,
				object_id=self.pk,
				event="submit", channel="sms",
				channel_subscriber=self.mobile,
				message_id=message_id
			)

	def event_completed_channel_whatsapp(self):
		sv_doc = self.documents.filter(type=ConnectionApplicationDocumentsEnum.SV).first()

		body_text = {
			"countryCode": "+91",
			"phoneNumber": self.mobile,
			"type": "Template",
			"traits": {
				"name": self.name,
			},
			# "callbackData": "some_callback_data",
			"template": {
				"name": "domestic_application_completed",
				"languageCode": "en_GB",
				"headerValues": [
					sv_doc.link
				],
				"bodyValues": [
					self.name,
					self.id,
					'{} {} {}'.format(
						self.get_application_type_display(),
						self.get_item_code_display(),
						self.get_connection_type_display()
					),
				],
			}
		}

		connection_application_content_type = ContentType.objects.get_for_model(ConnectionApplication)
		data = track.client.post(
			api_key=settings.INTERAKT_API_KEY,
			path="/v1/public/message/",
			body=body_text
		).json()

		if data.get('result'):
			CommunicationLog.objects.create(
				content_type=connection_application_content_type,
				object_id=self.pk,
				event="completed", channel="whatsapp",
				channel_subscriber=self.mobile,
				message_id=data.get('id')
			)

	@fsm_log_description
	@fsm_log_by
	@transition(
		field=status,
		source=ConnectionApplicationLeadStatus.SUBMITTED,
		target=GET_STATE(
			lambda self, **kwargs: \
					ConnectionApplicationLeadStatus.BACK_OFFICE_START \
					if kwargs.get("required") == 'Y' else ConnectionApplicationLeadStatus.NOT_INTERESTED,
			states=[
				ConnectionApplicationLeadStatus.BACK_OFFICE_START,
				ConnectionApplicationLeadStatus.NOT_INTERESTED
			]
		),
		custom=dict(
			short_description='Application Confirmation',
			admin=True,
			form=ConnectionVerificationResult
		),
	)
	def confirm_application(self, *args, **kwargs):
		if kwargs.get("required"):
			self.required_by = kwargs.get("required_by")
			self.applicant_remarks = kwargs.get("applicant_remarks")

	@fsm_log_description
	@fsm_log_by
	@transition(
		field=status,
		source=ConnectionApplicationLeadStatus.BACK_OFFICE_START,
		target=ConnectionApplicationLeadStatus.BACK_OFFICE_END,
		custom=dict(short_description='Back Office Processing Start', admin=True, form=BackOfficeForm),
	)
	def back_office_process_start(self, *args, **kwargs):
		self.consumer_id = kwargs.get("consumer_id")
		self.process_type = kwargs.get("process_type")

	@fsm_log_by
	@transition(
		field=status,
		source=ConnectionApplicationLeadStatus.BACK_OFFICE_END,
		target=ConnectionApplicationLeadStatus.FRONT_OFFICE,
		custom=dict(
			short_description='Back Office Processing End',
			admin=True,
			form_func=get_form_to_load
		),
	)
	def application_processed(self, *args, **kwargs):
		if self.process_type == ConnectionApplicationProcessType.NEW_CONNECTION:
			self.remarks = kwargs.get("remarks")
			self.consumer_id = kwargs.get("consumer_id")

			new_sv_doc_url = move_sv_doc_file_tus_to_minio(
				kwargs.get('sv_doc_url'), self.id, kwargs.get("consumer_id")
			)
			#
			# self.documents.create(
			# 	type=ConnectionApplicationDocumentsEnum.SV,
			# 	link=kwargs.get('sv_doc_url')
			# )
			self.documents.create(
				type=ConnectionApplicationDocumentsEnum.SV,
				link=new_sv_doc_url
			)
		elif self.process_type == ConnectionApplicationProcessType.REGULARISATION:
			self.remarks = kwargs.get("remarks")

			new_sv_doc_url = move_sv_doc_file_tus_to_minio(
				kwargs.get('sv_doc_url'), self.id, kwargs.get("consumer_id")
			)
			#
			# self.documents.create(
			# 	type=ConnectionApplicationDocumentsEnum.SV,
			# 	link=kwargs.get('sv_doc_url')
			# )
			self.documents.create(
				type=ConnectionApplicationDocumentsEnum.SV,
				link=new_sv_doc_url
			)
		else:
			sv_doc_html_template = loader.get_template("connection_app/sv-doc.html")
			sv_doc_html = sv_doc_html_template.render({'obj': self})

			sv_doc_pdf = requests.post(
				settings.HTML_TO_PDF_SERVER_URL,
				json={
					"content": sv_doc_html,
					"options": {"pageSize": "A4", "imageDpi": 150, "imageQuality": 80}
				}
			)

			# Converting PDF file to Bytes IO Stream and Uploading To minio
			sv_doc_pdf_bytes = io.BytesIO(sv_doc_pdf.content)
			sv_doc_file_name = "cnapp_{}_sv_{}.pdf".format(self.id, self.consumer_id)
			# sv_doc_file_name = "{}_sv.pdf".format(self.consumer_id)
			minio_client.put_object(
				settings.MINIO_BUCKET_NAME,
				sv_doc_file_name,
				sv_doc_pdf_bytes, sv_doc_pdf_bytes.getbuffer().nbytes,
				content_type="application/pdf"
			)

			self.documents.create(
				type=ConnectionApplicationDocumentsEnum.SV,
				link=get_minio_public_url(settings.MINIO_BUCKET_NAME, sv_doc_file_name)
			)


	@fsm_log_description
	@fsm_log_by
	@transition(
		field=status,
		source=ConnectionApplicationLeadStatus.FRONT_OFFICE,
		target=GET_STATE(
			lambda self, **kwargs: \
					ConnectionApplicationLeadStatus.COMPLETED \
							if kwargs.get("verified") else ConnectionApplicationLeadStatus.BACK_OFFICE_END,
			states=[
				ConnectionApplicationLeadStatus.BACK_OFFICE_END,
				ConnectionApplicationLeadStatus.COMPLETED
			]),
		custom=dict(
			short_description='Verified OTP & Application', admin=True, form=FrontOfficeCompleted
		),
	)
	def front_office_completed(self, *args, **kwargs):
		if kwargs.get("verified"):
			self.remarks = kwargs.get("remarks")

	def event_installation_upload_channel_whatsapp(self):
		body_text = {
			"countryCode": "+91",
			"phoneNumber": self.mobile,
			"type": "Template",
			"traits": {
				"name": self.name,
			},
			# "callbackData": "some_callback_data",
			"template": {
				"name": "kitchen_photo_upload_sp",
				"languageCode": "en_GB",
				"headerValues": [
					# "Alert",  #
				],
				"bodyValues": [
					self.name,
				],
				"buttonValues": {
					"0": [
						"connection-app/connection-application/{}/installation".format(self.id)
					]
				}
			}
		}

		connection_application_content_type = ContentType.objects.get_for_model(ConnectionApplication)
		data = track.client.post(
			api_key=settings.INTERAKT_API_KEY,
			path="/v1/public/message/",
			body=body_text
		).json()

		if data['result']:
			CommunicationLog.objects.create(
					content_type=connection_application_content_type,
				object_id=self.pk,
				event="submit", channel="whatsapp",
				message_id=data.get('id')
			)
		else:
			pass
			#self.event_submit_channel_sms()

	def event_installation_upload_channel_sms(self):
		send_template_link_sms(
			self.mobile,
			"Installation",
			generate_tiny_url(
				"https://dca.arungas.com/connection-app/connection-application/{}/installation".format(self.id))
		)

	def event_reupload_channel_whatsapp(self):
		body_text = {
			"countryCode": "+91",
			"phoneNumber": self.mobile,
			"type": "Template",
			"traits": {
				"name": self.name,
			},
			# "callbackData": "some_callback_data",
			"template": {
				"name": "domestic_application_reupload",
				"languageCode": "en_GB",	
				"headerValues": [
					# "Alert",  #
				],
				"bodyValues": [
					self.name,
				],
				"buttonValues": {
					"0": [
						"connection-app/connection-application/{}/".format(self.id)
					]
				}
			}
		}

		connection_application_content_type = ContentType.objects.get_for_model(ConnectionApplication)
		data = track.client.post(
			api_key=settings.INTERAKT_API_KEY,
			path="/v1/public/message/",
			body=body_text
		).json()

		if data['result']:
			CommunicationLog.objects.create(
				content_type=connection_application_content_type,
				object_id=self.pk,
				event="submit", channel="whatsapp",
				message_id=data.get('id')
			)
		else:
			self.event_submit_channel_sms()
			self.event_submit_channel_sms()

	def event_reupload_channel_sms(self):
		pass


class ConnectionApplicationDocuments(models.Model):
	parent = models.ForeignKey(ConnectionApplication, on_delete=models.CASCADE, related_name='documents', null=True)
	type = models.CharField(max_length=52, choices=ConnectionApplicationDocumentsEnum.choices)
	link = models.URLField()
	valid_size = models.BooleanField(default=False, null=True, blank=True)


class PaymentProfile(models.Model):
	"""
		{
			"": "",
			"Case Num": "1-38288458",
			"Closed Date": "",
			"Created Date": "14-Nov-2023 12:45:51 AM",
			"Name As Per Bank": "Laddi",
			"Name As On Relationship": "Laddi Devi",
			"Name As Per Bank Response": "",
			"Name Match": "N",
			"Distributor Code": "0000305948",
			"Distributor Name": "ARUN INDANE PROP LUDHIANA ENT.",
			"Comments": "",
			"Relationship Id": "7200000026714114",
			"Payment Profile Id": "1-8NKUKSUI",
			"Account Id": "1-8NKUKSTQ",
			"Status": "Open",
			"Contact Id": "1-8NKUKST1",
			"Type": "Bank Verification Approval",
			"PFMS Payment Method": "ACTC"
		}
	"""
	case_num = models.CharField(max_length=128)
	closed_data = models.DateTimeField(null=True, blank=True)
	created_date = models.DateTimeField(null=True, blank=True)
	name_as_per_bank = models.CharField(max_length=256)
	name_as_on_relationship = models.CharField(max_length=256)
	name_as_per_bank_response = models.CharField(max_length=256)
	name_match = models.BooleanField(default=False)
	distributor_code = models.CharField(max_length=256)
	distributor_name = models.CharField(max_length=256)
	comments = models.CharField(max_length=256, null=True, blank=True)
	relationship_id = models.CharField(max_length=128)
	payment_profile_id = models.CharField(max_length=128)
	account_id = models.CharField(max_length=128)
	status = models.CharField(max_length=128)
	contact_id = models.CharField(max_length=128)
	profile_type = models.CharField(max_length=256)
	pfms_payment_method = models.CharField(max_length=128)
	approval_status = models.CharField(max_length=128, choices=PaymentProfileApprovalStatusEnum.choices,
                        default=PaymentProfileApprovalStatusEnum.PENDING)
	action = models.CharField(max_length=1, null=True)


class CustomerProfile(models.Model):
	created_on = models.DateTimeField(auto_now_add=True)
	updated_on = models.DateTimeField(auto_now=True)
	name = models.CharField(max_length=256)
	consumer_id = models.CharField(max_length=128)
	customer_type = models.CharField(max_length=128, choices=CustomerTypeEnum.choices, default=CustomerTypeEnum.GENERAL,
                               null=True)
	address = models.TextField(null=True)
	relationship_type = models.CharField(max_length=128, null=True)
	consumer_no = models.CharField(max_length=128, null=True)
	dob = models.DateField(null=True)
	kyc_level = models.CharField(max_length=128, null=True)
	contact_status = models.CharField(max_length=128, null=True)
	ucm_id = models.CharField(max_length=128, null=True)
	relationship_channel = models.CharField(max_length=128, null=True)
	relationship_start_date = models.DateField(null=True)
	ekyc_flag = models.BooleanField(null=True)
	ekyc_date = models.DateTimeField(null=True)
	auth_type = models.CharField(max_length=128, null=True)
	customer_segment = models.CharField(max_length=128, null=True)
	kyc_approval_date = models.DateTimeField(null=True)
	fleet_marketing = models.BooleanField(null=True)
	kyc_approval_flag = models.BooleanField(null=True)
	otp_verification = models.CharField(max_length=128, null=True)
	first_name = models.CharField(max_length=128, null=True)
	last_name = models.CharField(max_length=128, null=True)
	gender = models.CharField(max_length=128, null=True)
	account_name = models.CharField(max_length=128, null=True)
	primary_account_address = models.TextField(null=True)
	dealer_code = models.CharField(max_length=128, null=True)
	distributor = models.ForeignKey(Distributor, on_delete=models.PROTECT, null=True, blank=True)
	distributor_code = models.CharField(max_length=128, null=True)
	distributor_name = models.CharField(max_length=128, null=True)
	mobile_number = models.CharField(max_length=128, null=True)
	mobile_number_2 = models.CharField(max_length=128, null=True)
	email_addresss = models.CharField(max_length=256, null=True)
	employee_code = models.CharField(max_length=128, null=True)
	vip_flag = models.BooleanField(null=True)
	vip_description = models.CharField(max_length=128, null=True)
	old_vip_description = models.CharField(max_length=128, null=True)
	cancel_reason = models.CharField(max_length=128, null=True)
	cancel_remarks = models.TextField(null=True)
	delivery_type = models.CharField(max_length=128, null=True)
	sdms_service_area = models.ForeignKey(SDMSServiceArea, on_delete=models.PROTECT, blank=True, null=True)
	service_area = models.CharField(max_length=128, null=True)
	relationship_status = models.CharField(max_length=128, null=True)
	relationship_sub_status = models.CharField(max_length=128, null=True)
	waitlist_status = models.CharField(max_length=128, null=True)
	kyc_date = models.DateTimeField(null=True)
	kyc_status = models.CharField(max_length=128, null=True)
	application_id = models.CharField(max_length=128, null=True)
	subsidy_status = models.CharField(max_length=128, null=True)
	nic_status = models.CharField(max_length=128, null=True)
	omc_status = models.CharField(max_length=128, null=True)
	revalidated = models.BooleanField(null=True)
	ftl_reseller_flag = models.BooleanField(null=True)
	tcs_flag = models.BooleanField(null=True)
	pan_number = models.CharField(max_length=128, null=True)
	multiple_connection_blocking_reason = models.TextField(null=True)
	release_date = models.DateTimeField(null=True)
	intimation_release_date = models.DateTimeField(null=True)
	mandatory_inspection_due_date = models.DateField(null=True)
	last_inspection_date = models.DateField(null=True)
	mi_refusal_flag = models.BooleanField(null=True)
	mi_refusal_date = models.DateTimeField(null=True)
	tube_change_date = models.DateField(null=True)
	tube_change_due_date = models.DateField(null=True)
	suspend_deact_date = models.DateTimeField(null=True)
	suspend_reason = models.CharField(max_length=256, null=True)
	tight_joint_replacement_flag = models.BooleanField(null=True)
	tight_joint_replacement_date = models.DateTimeField(null=True)
	approval_rejection_comments = models.TextField(null=True)
	group_member_status = models.CharField(max_length=128, null=True)
	consumer_category = models.CharField(max_length=128, null=True)
	scheme = models.CharField(max_length=256, null=True)
	scheme_type = models.CharField(max_length=256, null=True)
	scheme_sub_type = models.CharField(max_length=256, null=True)
	ujjwala_category = models.CharField(max_length=256, null=True)
	priority = models.BooleanField(null=True)
	consumer_type = models.CharField(max_length=256, null=True)
	products = models.CharField(max_length=256, null=True)
	no_of_flats = models.IntegerField(null=True)
	parent_consumer_id = models.CharField(max_length=128, null=True)
	scheme_opted = models.CharField(max_length=128, null=True)
	asset_count = models.IntegerField(null=True)
	migrant = models.BooleanField(null=True)
	scheme_onbaording_status = models.CharField(max_length=128, null=True)
	contact_identities = models.JSONField(null=True)
	phones = models.JSONField(null=True)
	ekyc_details = models.JSONField(null=True)
	camunda_process_instance_id = models.TextField(max_length=128, null=True, blank=True)
	latitude = models.CharField(max_length=128, null=True, blank=True)
	longitude = models.CharField(max_length=128, null=True, blank=True)
	do_not_auto_generate = models.BooleanField(default=False)
	verified = models.BooleanField(null=True, blank=True)
	verified_on = models.DateTimeField(null=True, blank=True)
	verification_source = models.CharField(max_length=128, null=True, blank=True)
	is_dirty = models.BooleanField(null=True, blank=True)
	last_refill_date = models.DateTimeField(null=True, blank=True)
	last_synced_date = models.DateTimeField(null=True, blank=True)

	def get_do_not_auto_generate_sales_order(self):
		if self.customer_profile_settings:
			return self.customer_profile_settings.do_not_auto_generate_sales_order
		return False

	def days_since_last_sales_order(self):
		last_order = self.salesorder_set.filter(
			order_status__in=[SalesOrderStatusEnum.COMPLETED, SalesOrderStatusEnum.INVOICED,
			                  SalesOrderStatusEnum.INVOICING_IN_PROGRESS]).order_by('-order_date').first()
		if last_order:
			delta = datetime.datetime.now().date() - last_order.order_date.date()
			return delta.days
		return None

	def document_self(self):
		sd = self.documents.filter(type=ConnectionApplicationDocumentsEnum.CUSTOMER_PHOTO).first()
		if not sd:
			if self.ujjwalav2application_set.exists():
				return self.ujjwalav2application_set.first().document_self()
		return sd.link if sd else ''

	def get_refill_sales_order_count(self):
		if self.ujjwalav2application_set.exists():
			ujjwala_obj = self.ujjwalav2application_set.first()
			if ujjwala_obj.override_change_cylinder_type:
				return ujjwala_obj.sdms_refills
		return self.salesorder_set.filter(order_sub_type='Refill Order').exclude(
			order_status=SalesOrderStatusEnum.CANCELLED).count()

	def get_phone_numbers_from_sales_order(self):
		return self.salesorder_set.exclude(mobile_number__isnull=True).exclude(mobile_number='').values(
			'mobile_number').distinct()

	def get_last_sales_order(self):
		return self.salesorder_set.order_by('-order_date').first()


class CustomerProfileSettings(models.Model):
	parent = models.OneToOneField(
		CustomerProfile,
		on_delete=models.CASCADE,
		related_name='customer_profile_settings',
		null=True
	)
	do_not_auto_generate_sales_order = models.BooleanField(default=False)


class CustomerProfileDocuments(models.Model):
	parent = models.ForeignKey(CustomerProfile, on_delete=models.CASCADE, related_name='documents', null=True)
	type = models.CharField(max_length=48, choices=ConnectionApplicationDocumentsEnum.choices)
	link = models.URLField()
	valid_size = models.BooleanField(default=False, null=True, blank=True)


class PostInspectionActivity(models.Model):
	activity_type = models.CharField(max_length=25, choices=PostInspectionActivityTypeEnum.choices)
	created_on = models.DateTimeField(auto_now_add=True, null=True)
	completed = models.BooleanField(default=False)
	completed_on = models.DateTimeField(auto_now=True, null=True)
	completed_by = models.ForeignKey(User, on_delete=models.PROTECT, null=True, blank=True)
	data = models.JSONField(null=True)


class PostInspection(models.Model):
	parent = models.OneToOneField(
		CustomerProfile, on_delete=models.PROTECT, related_name='post_inspection'
	)
	created_on = models.DateTimeField(auto_now_add=True, null=True)
	updated_on = models.DateTimeField(auto_now=True, null=True)
	latitude = models.CharField(max_length=32, null=True, blank=True)
	longitude = models.CharField(max_length=32, null=True, blank=True)
	address_json = models.JSONField(null=True)
	mobile_number = models.CharField(max_length=12, null=True)
	accuracy = models.CharField(max_length=24, null=True, blank=True)
	mechanic = models.ForeignKey(User, on_delete=models.PROTECT, null=True, blank=True)
	submitted_on = models.DateTimeField(null=True)
	type = models.CharField(max_length=32, choices=InspectionTypeEnum.choices, default=InspectionTypeEnum.MECHANIC)
	status = FSMField(
		default=PostInspectionStatusEnum.CHANGE_ADDRESS,
		choices=PostInspectionStatusEnum.choices
	)
	camunda_process_id = models.CharField(max_length=128, null=True, blank=True)
	camunda_error_message = models.TextField(null=True, blank=True)
	rejected_reasons = models.JSONField(null=True, blank=True)
	tags = TaggableManager()
	activities = models.ManyToManyField(PostInspectionActivity)

	class Meta:
		permissions = (
			("can_do_post_inspection", "Can Do Post Inspection"),
		)

	def mechanic_name(self):
		if self.mechanic:
			return self.mechanic.get_full_name()
		else:
			return self.parent.name

	def document_kitchen_photo(self):
		return self.documents.filter(type=ConnectionApplicationDocumentsEnum.KITCHEN_PHOTO).first().link

	def document_main_gate_photo(self):
		return self.documents.filter(type=ConnectionApplicationDocumentsEnum.MAIN_GATE).first().link

	@fsm_log_description
	@fsm_log_by
	@transition(
		field=status,
		source=[
			PostInspectionStatusEnum.STARTED,
			PostInspectionStatusEnum.REJECTED
		],
		target=PostInspectionStatusEnum.SUBMITTED,
		custom=dict(short_description='Post Inspection Submitted', admin=False),
	)
	def transition_post_inspection_submitted(self, *args, **kwargs):
		if self.status == PostInspectionStatusEnum.REJECTED:
			self.documents.all().delete()
		self.mechanic = kwargs.get('mechanic')
		self.submitted_on = datetime.datetime.now()

	def kitchen_photo_updated(self):
		return self.activities.get(activity_type=PostInspectionActivityTypeEnum.KITCHEN_PHOTO_UPDATE).completed

	def main_gate_photo_updated(self):
		return self.activities.get(activity_type=PostInspectionActivityTypeEnum.MAIN_GATE_PHOTO_UPDATE).completed

	def profile_photo_updated(self):
		return self.activities.get(activity_type=PostInspectionActivityTypeEnum.PROFILE_PHOTO_UPDATE).completed

	def uid_photo_updated(self):
		return self.activities.get(activity_type=PostInspectionActivityTypeEnum.UID_PHOTO_UPDATE).completed

	def address_updated(self):
		return self.activities.get(activity_type=PostInspectionActivityTypeEnum.ADDRESS_UPDATE).completed

	def suraksha_pipe_updated(self):
		return self.activities.get(activity_type=PostInspectionActivityTypeEnum.SURAKSHA_PIPE_UPDATE).completed

	# @fsm_log_description
	# @fsm_log_by
	# @transition(
	# 	field=status,
	# 	source=[
	# 		PostInspectionStatusEnum.REJECTED,
	# 		PostInspectionStatusEnum.REDO,
	# 	],
	# 	target=PostInspectionStatusEnum.CHANGE_ADDRESS,
	# 	custom=dict(short_description='Verify Otp', admin=False),
	# )
	# def transition_post_inspection_otp_verified(self, *args, **kwargs):
	# 	# Deleting existing documents
	# 	if self.status == PostInspectionStatusEnum.REJECTED:
	# 		self.documents.all().delete()
	#
	# @fsm_log_description
	# @fsm_log_by
	# @transition(
	# 	field=status,
	# 	source=[
	# 		PostInspectionStatusEnum.CHANGE_ADDRESS,
	# 	],
	# 	target=PostInspectionStatusEnum.KITCHEN_PHOTO,
	# 	custom=dict(short_description='Change Address', admin=False),
	# )
	# def transition_post_inspection_changed_address(self, *args, **kwargs):
	# 	pass
	#
	# @fsm_log_description
	# @fsm_log_by
	# @transition(
	# 	field=status,
	# 	source=[
	# 		PostInspectionStatusEnum.KITCHEN_PHOTO,
	# 	],
	# 	target=PostInspectionStatusEnum.PREVIEW_INSPECTION,
	# 	custom=dict(short_description='Upload Main Gate Pic & Location', admin=False),
	# )
	# def transition_post_inspection_kitchen_photo_uploaded(self, *args, **kwargs):
	# 	self.documents.filter(
	# 		type=ConnectionApplicationDocumentsEnum.KITCHEN_PHOTO
	# 	).delete()
	#
	# 	self.documents.create(
	# 		type=ConnectionApplicationDocumentsEnum.KITCHEN_PHOTO,
	# 		link=kwargs.get('link')
	# 	)
	#
	# @fsm_log_description
	# @fsm_log_by
	# @transition(
	# 	field=status,
	# 	source=PostInspectionStatusEnum.PREVIEW_INSPECTION,
	# 	target=PostInspectionStatusEnum.SUBMITTED,
	# 	custom=dict(short_description='Submit Pre-Inspection', admin=False),
	# )
	# def transition_post_inspection_submitted(self, *args, **kwargs):
	# 	self.documents.filter(
	# 		type=ConnectionApplicationDocumentsEnum.MAIN_GATE
	# 	).delete()
	#
	# 	self.documents.create(
	# 		type=ConnectionApplicationDocumentsEnum.MAIN_GATE,
	# 		link=kwargs.get('link')
	# 	)
	#
	# 	if self.type == InspectionTypeEnum.SELF:
	# 		self.mechanic = None
	# 	else:
	# 		self.mechanic = get_current_user()
	# 	self.submitted_on = datetime.datetime.now()
	# 	self.save()
	#
	# 	# start_process_in_camunda_v2('Process_preinspection', variables)
	# 	create_camunda_preinspection_review_function = partial(
	# 		start_process_in_camunda_v2,
	# 		process_definition_key='Process_preinspection',
	# 		variables={"variables": {"preinspection_id": {"value": self.id, "type": "String"}}}
	# 	)
	# 	transaction.on_commit(create_camunda_preinspection_review_function)


class PostInspectionDocuments(models.Model):
	parent = models.ForeignKey(PostInspection, on_delete=models.CASCADE, related_name='documents', null=True)
	type = models.CharField(max_length=32, choices=ConnectionApplicationDocumentsEnum.choices)
	compressed = models.BooleanField(default=False)
	file_size = models.CharField(max_length=16, default='0')
	link = models.URLField(null=True, blank=True)
	# Fields To Store Original Tus Link
	original_link = models.URLField(null=True, blank=True)

	def download_links(self):
		html = '''
		<a href="{}" target="blank">View File</a>
		'''.format(self.link)
		return mark_safe(html)


class SalesOrder(models.Model):
	"""
	{
		"": "",
		"Sales Order #": "2-003664888925",
		"Order Date": "26-Mar-2024 09:13:44 PM",
		"Relationship Id": "7200000033203814",
		"Invoice Number": "5-104004535514",
		"Consumer Name": "Arfa Parveen",
		"Consumer Address": "hNo 1815/87 StNo 1 Industrial area a  millerganjVijay nagar   Ludhiana LUDHIANA Punjab 141003",
		"Channel": "MissedCall",
		"Order Type": "Sales Order",
		"Order Sub Type": "Refill Order",
		"Order Status": "Completed",
		"Delivery Date": "27-Mar-2024 07:35:30 AM",
		"Consumed Quota": "28.4",
		"Campaign Name": "",
		"Campaign Code": "",
		"Digital Payment": "Y",
		"Account Name": "",
		"Consumer Type": "Single Bottle Connection",
		"Cancellation Date": "",
		"Paid": "Y",
		"Delivery Confirm Full Name": "ANAND RAY",
		"Mobile Number": "8969102423",
		"Tatkal Order": "",
		"Portability Flag": "N"
	 }
	"""
	parent = models.ForeignKey(CustomerProfile, on_delete=models.CASCADE)
	created_on = models.DateTimeField(auto_now_add=True)
	updated_on = models.DateTimeField(auto_now=True)
	sales_order = models.CharField(max_length=128)
	order_type = models.CharField(max_length=128, null=True)
	order_sub_type = models.CharField(max_length=128, null=True)
	order_status = FSMField(
		default=SalesOrderStatusEnum.NOT_UPDATED,
		choices=SalesOrderStatusEnum.choices
	)
	order_date = models.DateTimeField()
	channel = models.CharField(max_length=128, null=True)
	channel_ref = models.CharField(max_length=128, null=True)
	relationship_id = models.CharField(max_length=128, null=True)
	invoice_number = models.CharField(max_length=128, null=True)
	consumer_name = models.CharField(max_length=128)
	consumer_address = models.CharField(max_length=256, null=True)
	price_list = models.CharField(max_length=256, null=True)
	total_due_amount = models.FloatField(null=True)
	total_payment_amount = models.FloatField(null=True)
	attempted_during_pdt_daytime = models.BooleanField(null=True)
	indenting_po_number = models.CharField(max_length=128, null=True)
	zone_distributor_id = models.CharField(max_length=256, null=True)
	scheme_opted = models.CharField(max_length=128, null=True)
	order_total = models.FloatField(null=True)
	delivery_type = models.CharField(max_length=128, null=True)
	delivery_date = models.DateTimeField(null=True)
	dac_flag = models.BooleanField(null=True)
	portability_flag = models.BooleanField(null=True)
	sub_channel = models.CharField(max_length=128, null=True)
	booked_by = models.CharField(max_length=256, null=True)
	qc_due = models.BooleanField(null=True)
	consumed_quota = models.FloatField(null=True)
	account_name = models.CharField(null=True, max_length=128)
	consumer_type = models.CharField(max_length=256, null=True)
	mobile_number = models.CharField(max_length=128, null=True)
	tatkal_order = models.CharField(max_length=64, null=True)
	scheme_onboarding_status = models.CharField(max_length=128, null=True)
	subsidy_status = models.CharField(max_length=128, null=True)
	smart_card_num = models.CharField(max_length=128, null=True)
	perferred_day = models.CharField(max_length=128, null=True)
	preferred_time_slot = models.CharField(max_length=128, null=True)
	preferred_flag = models.BooleanField(null=True)
	isi_mark_ho_plate = models.BooleanField(null=True)
	burner_type = models.CharField(max_length=128, null=True)
	cancellation_reason = models.CharField(max_length=256, null=True)
	cancellation_date = models.DateTimeField(null=True)
	dac_disable_reason = models.CharField(max_length=128, null=True)
	campaign_code = models.CharField(null=True, max_length=128)
	campaign_name = models.CharField(null=True, max_length=128)
	distributor_name = models.CharField(null=True, max_length=256)
	service_area = models.CharField(null=True, max_length=128)
	delivery_boy_login = models.CharField(null=True, max_length=256)
	delivery_boy_full_name = models.CharField(null=True, max_length=256)
	otp = models.CharField(null=True, max_length=64)
	delivery_confirmation_type = models.CharField(null=True, max_length=256)
	delivery_confirmed_by = models.CharField(null=True, max_length=256)
	delivery_confirm_full_name = models.CharField(null=True, max_length=256)
	error_message = models.TextField(null=True, max_length=256)
	paid_flag = models.BooleanField(null=True)
	digital_payment = models.BooleanField(null=True)
	subsidized = models.BooleanField(null=True)
	subsidized_on_invoice_gen = models.BooleanField(null=True)
	cancel_source = models.CharField(null=True, max_length=128)
	dac_disable_by = models.CharField(null=True, max_length=128)
	ship_to_address = models.TextField(null=True)
	camunda_process_instance_id = models.CharField(max_length=128, null=True)
	cancellation_camunda_pid = models.CharField(max_length=128, null=True)
	extra_data = models.JSONField(null=True)
	auto_generated = models.BooleanField(default=False)
	hide_from_view = models.BooleanField(default=False)
	is_dirty = models.BooleanField(null=True, blank=True)
	last_synced_on = models.DateTimeField(null=True, blank=True)

	class Meta:
		constraints = [
			models.UniqueConstraint(fields=['order_date', 'sales_order'], name='unique sales_order_date_sales_order')
		]

	@fsm_log_description
	@fsm_log_by
	@transition(
		field=order_status,
		source=['*'],
		target=SalesOrderStatusEnum.COMPLETED,
		custom=dict(
			short_description='Sales Order Completed',
			admin=False,
		),
	)
	def transition_sales_order_completed(self, *args, **kwargs):
		pass

	@fsm_log_description
	@fsm_log_by
	@transition(
		field=order_status,
		source=['*'],
		target=SalesOrderStatusEnum.CANCELLED,
		custom=dict(
			short_description='Sales Order Cancelled',
			admin=False,
		),
	)
	def transition_sales_order_cancelled(self, *args, **kwargs):
		pass

	@fsm_log_description
	@fsm_log_by
	@transition(
		field=order_status,
		source=['*'],
		target=SalesOrderStatusEnum.INVOICED,
		custom=dict(
			short_description='Sales Order Invoiced',
			admin=False,
		),
	)
	def transition_sales_order_invoiced(self, *args, **kwargs):
		pass

	@fsm_log_description
	@fsm_log_by
	@transition(
		field=order_status,
		source=['*'],
		target=SalesOrderStatusEnum.NOT_FOUND,
		custom=dict(
			short_description='Sales Order Not Found',
			admin=False,
		),
	)
	def transition_sales_order_not_found(self, *args, **kwargs):
		pass

	@fsm_log_description
	@fsm_log_by
	@transition(
		field=order_status,
		source=['*'],
		target=SalesOrderStatusEnum.RETURNED,
		custom=dict(
			short_description='Sales Order Returned',
			admin=False,
		),
	)
	def transition_sales_order_returned(self, *args, **kwargs):
		exist = is_process_exist_in_camunda(
			'process_fetch_sales_order_details_from_sdms', 'sales_order_id', so.id
		)
		if not exist:
			if self.parent.distributor:
				start_process_fetch_sales_order_details_from_sdms(self.id, self.parent.distributor.code)
			elif "arun gas" in self.distributor_name.lower():
				start_process_fetch_sales_order_details_from_sdms(self.id, "0000110338")
			elif "arun indane" in self.distributor_name.lower():
				start_process_fetch_sales_order_details_from_sdms(self.id, "0000305948")
			else:
				print("Could Not Find Valid Distributor")


class SalesOrderInvoice(models.Model):
	"""
	{
		"": "",
		"Invoice Number": "5-103991627817",
		"Sales Order #": "2-003653125558",
		"Invoice date": "21-Mar-2024 01:24:31 PM",
		"Invoice Status": "Open",
		"Consumer Name": "Sham Lal",
		"Consumer Type": "Double Bottle Connection",
		"Consumer Address": "H.NO.6441/2 ST.NO.8 HARGOBIND NAGAR LDH. PROOF OK /10/2/2010 LUDHIANA Punjab 141008",
		"Subsidy Status": "Start",
		"Scheme Onboarding Status": "Onboarded With CTC",
		"Delivery Type": "Home Delivery",
		"Service Area": "KIDWAI NGR RANJIT NGR AMAR PUR",
		"Delivery Boy": "ARUN YADAV",
		"Paid Flag": "N",
		"Preferred Flag": "N",
		"Preferred Day": "",
		"Preferrred Time Slot": "",
		"Print Flag": "N",
		"Order Sub Type": "Refill Order",
		"Equipment Type": "14.2",
		"Relationship Id": "7500000068250924",
		"Consumer Number": "7568250924",
		"Distributor Local Cash Memo#": "305948243100193364",
		"Digital Payment": "N",
		"Scheme Type": "General",
		"Tatkal Order": "",
		"EPIC Invoice IRN Calc": "N",
		"IRN Number": "",
		"Site Id": ""
	}
	"""
	parent = models.ForeignKey(CustomerProfile, on_delete=models.CASCADE)
	invoice_number = models.CharField(max_length=128, unique=True)
	sales_order = models.CharField(max_length=128)
	invoice_date = models.DateTimeField()
	invoice_status = models.CharField(max_length=128)
	consumer_name = models.CharField(max_length=128)
	consumer_type = models.CharField(max_length=128)
	consumer_address = models.CharField(max_length=256)
	subsidy_status = models.CharField(max_length=128)
	scheme_onboarding_status = models.CharField(max_length=128)
	delivery_type = models.CharField(max_length=128)
	service_area = models.CharField(max_length=128)
	delivery_boy = models.CharField(max_length=128)
	paid_flag = models.BooleanField()
	preferred_flag = models.BooleanField()
	preferred_day = models.CharField(max_length=128, null=True)
	preferred_time_slot = models.CharField(max_length=128, null=True)
	print_flag = models.BooleanField()
	order_sub_type = models.CharField(max_length=128)
	equipment_type = models.CharField(max_length=64)
	relationship_id = models.CharField(max_length=128)
	consumer_number = models.CharField(max_length=128)
	distributor_local_cash_memo = models.CharField(max_length=128)
	digital_payment = models.BooleanField()
	scheme_type = models.CharField(max_length=128)
	tatkal_order = models.CharField(max_length=64, null=True)
	epic_invoice_irn_calc = models.BooleanField()
	irn_number = models.CharField(max_length=128, null=True)
	site_id = models.CharField(max_length=128, null=True)

	class Meta:
		constraints = [
			models.UniqueConstraint(fields=['invoice_date', 'invoice_number'],
		                      name='unique sales_order_invoice_date_invoice_number')
		]


class Lead(models.Model):
	parent = models.ForeignKey(CustomerProfile, on_delete=models.CASCADE, null=True)
	created_on = models.DateTimeField(auto_now_add=True)
	updated_on = models.DateTimeField(auto_now=True)
	name = models.CharField(max_length=128)
	mobile_number = models.CharField(max_length=10)
	remarks = models.CharField(max_length=128, null=True, blank=True)
	generated_by = models.ForeignKey(User, on_delete=models.CASCADE)
	service_type = models.ForeignKey(ServiceType, on_delete=models.CASCADE)
	due_on = models.DateTimeField(null=True)
	follow_up_on = models.DateTimeField(null=True)
	status = models.CharField(max_length=128, choices=LeadStatusEnum.choices, default=LeadStatusEnum.GENERATED)


class BookSalesOrder(models.Model):
	customer_profile = models.ForeignKey(CustomerProfile, on_delete=models.CASCADE)
	camunda_process_id = models.CharField(max_length=128, null=True)
	error_log = models.TextField(null=True, blank=True)


class SalesOrderPortability(models.Model):
	created_on = models.DateTimeField(auto_now_add=True)
	updated_on = models.DateTimeField(auto_now=True)
	sales_order_number = models.CharField(max_length=48)
	user = models.ForeignKey(User, on_delete=models.PROTECT)
	distributor = models.ForeignKey(Distributor, on_delete=models.PROTECT)
	status = models.CharField(max_length=128, choices=SalesOrderPortabilityStatusEnum.choices,
	                          default=SalesOrderPortabilityStatusEnum.DRAFTED)
	camunda_process_id = models.CharField(max_length=128)


class ImportData(models.Model):
	created_on = models.DateTimeField(auto_now_add=True)
	updated_on = models.DateTimeField(auto_now=True)
	template = models.CharField(max_length=128, choices=TemplateEnum.choices)
	file_path = models.TextField()
	status = models.CharField(max_length=128, choices=ImportDataStatusEnum.choices,
	                          default=ImportDataStatusEnum.SUBMITTED)
	error_log = models.TextField(null=True, blank=True)

	class Meta:
		permissions = (
			("can_use_admin_tools", "Can Use Admin Tools"),
		)
