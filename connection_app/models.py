import io

import requests
import track
from django.conf import settings
from django.contrib.contenttypes.models import ContentType
from django.db import models
from django.template import loader
from django.utils.safestring import mark_safe
from django_fsm import transition, FSMField, GET_STATE
from django_fsm_log.decorators import fsm_log_description, fsm_log_by
from minio import Minio

from communication_log.models import CommunicationLog
from connection_app.enums import ApplicationTypeEnum, ItemCodeEnum, ConnectionTypeEnum, \
	ConnectionApplicationProcessType, ConnectionApplicationLeadStatus, ConnectionApplicationDocumentsEnum, \
	ConnectionApplicationLeadCommunicationMode, ConnectionInstallationStatus
from connection_app.forms import ConnectionVerificationResult, BackOfficeForm, SubmitLead, \
	FrontOfficeCompleted, BackOfficeReactivation, BackOfficeRegularisation, \
	BackOfficeNewConnection, DocumentsReupload, InstallationReviewForm
from domestic_app.utils import get_minio_public_url

minio_client = Minio(
	settings.MINIO_ENDPOINT,
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
	connection_type = models.CharField(max_length=25, choices=ConnectionTypeEnum.choices)
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

	
	# @fsm_log_description
	# @fsm_log_by
	# @transition(
	# 	field=status,
	# 	source='*',
	# 	target=ConnectionApplicationLeadStatus.KITCHEN_PHOTO_UPLOAD,
	# 	custom=dict(
	# 		short_description='Upload Kitchen Photo', admin=True, form=KitchenPhotoUploadForm
	# 	),
	# )
	# def send_for_kitchen_photo_upload(self, *args, **kwargs):
	# 	self.last_execution_state = self.status
	# 	self.documents_reupload_remarks = kwargs.get('remarks')
	# 	self.documents_required_for_reupload = kwargs.get('kitchen_photo')
	# 	self.event_installation_upload_channel_whatsapp()


	# @fsm_log_description
	# @fsm_log_by
	# @transition(
	# 	field=installation_status,
	# 	source=ConnectionApplicationLeadStatus.REUPLOAD,
	# 	target=GET_STATE(
	# 		lambda self, **kwargs: self.last_execution_state,
	# 	),
	# 	custom=dict(
	# 		short_description='Application Uploaded By Customer'
	# 	),
	# )
	# def reuploaded_by_customer(self, *args, **kwargs):
	# 	pass


	# @fsm_log_description
	# @fsm_log_by
	# @transition(
	# 	field=status,
	# 	source=ConnectionApplicationLeadStatus.KITCHEN_PHOTO_UPLOAD,
	# 	target=GET_STATE(
	# 		lambda self, **kwargs: self.last_execution_state,
	# 	),
	# 	custom=dict(
	# 		short_description='Kitchen Photo Uploaded By Customer'
	# 	),
	# )
	# def kitchen_photo_uploaded_by_customer(self, *args, **kwargs):
	# 	pass


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
			short_description='Review Installation', admin=True, form=InstallationReviewForm
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
#		conditions=[lambda app: app.installation_status == ConnectionInstallationStatus.ACCEPTED],
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

			self.documents.create(
				type=ConnectionApplicationDocumentsEnum.SV,
				link=kwargs.get('sv_doc_url')
			)
		elif self.process_type == ConnectionApplicationProcessType.REGULARISATION:
			self.remarks = kwargs.get("remarks")

			self.documents.create(
				type=ConnectionApplicationDocumentsEnum.SV,
				link=kwargs.get('sv_doc_url')
			)
		else:
			sv_doc_html_template = loader.get_template("connection_app/sv-doc.html")
			sv_doc_html = sv_doc_html_template.render({'obj': self})

			sv_doc_pdf = requests.post(
				settings.HTML_TO_PDF_SERVER_URL,
				json={
					"content": sv_doc_html,
					"options": {"pageSize": "A4"}
				}
			)

			# Converting PDF file to Bytes IO Stream and Uploading To minio
			sv_doc_pdf_bytes = io.BytesIO(sv_doc_pdf.content)
			sv_doc_file_name = "{}_sv.pdf".format(self.consumer_id)
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
