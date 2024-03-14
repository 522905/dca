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
from django_currentuser.middleware import get_current_user
from django_fsm import transition, FSMField, GET_STATE
from django_fsm_log.decorators import fsm_log_description, fsm_log_by
from minio import Minio
from communication_log.jobs import move_sv_doc_file_tus_to_minio, move_files_to_minio_processing
from communication_log.models import CommunicationLog
from connection_app.enums import ApplicationTypeEnum, ItemCodeEnum, ConnectionTypeEnum, \
	ConnectionApplicationProcessType, ConnectionApplicationLeadStatus, ConnectionApplicationDocumentsEnum, \
	ConnectionApplicationLeadCommunicationMode, ConnectionInstallationStatus, \
	PaymentProfileApprovalStatusEnum
from connection_app.forms import ConnectionVerificationResult, BackOfficeForm, SubmitLead, \
	FrontOfficeCompleted, BackOfficeReactivation, BackOfficeRegularisation, \
	BackOfficeNewConnection, DocumentsReupload, InstallationReviewForm
from domestic_app.utils import get_minio_public_url

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
	address = models.TextField()
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

	@fsm_log_description
	@fsm_log_by
	@transition(
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
			self.event_installation_upload_channel_whatsapp()
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
		self.event_submit_channel_whatsapp()
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
							"contentTemplateId": "1107161183026272363"
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
		pass

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
	type = models.CharField(max_length=25, choices=ConnectionApplicationDocumentsEnum.choices)
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
