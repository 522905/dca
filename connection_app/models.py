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
	ConnectionApplicationLeadCommunicationMode
from connection_app.forms import ConnectionVerificationResult, BackOfficeForm, FrontOfficeForm, SubmitLead, \
	FrontOfficeSVForm
from domestic_app.utils import get_minio_public_url

minio_client = Minio(
    settings.MINIO_ENDPOINT,
    access_key=settings.MINIO_CREDENTIAL.get("access_key"),
    secret_key=settings.MINIO_CREDENTIAL.get("secret_key"),
	secure=False
)


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
	status = FSMField(default=ConnectionApplicationLeadStatus.DRAFT, choices=ConnectionApplicationLeadStatus.choices)
	applicant_remarks = models.TextField(null=True, blank=True)
	required_by = models.DateField(null=True, blank=True)
	consumer_id = models.CharField(max_length=25, null=True, blank=True)
	process_type = models.CharField(
		max_length=25, choices=ConnectionApplicationProcessType.choices, null=True, blank=True
	)
	communication_mode = models.CharField(
		max_length=25, choices=ConnectionApplicationLeadCommunicationMode.choices, null=True, blank=True
	)

	def lead_details_in_html(self):
		template = loader.get_template("connection_app/application_details_template.html")
		html = template.render({'obj': self})
		return mark_safe(html)

	lead_details_in_html.short_description = 'Lead Details'

	@fsm_log_description
	@fsm_log_by
	@transition(
		field=status,
		source=ConnectionApplicationLeadStatus.DRAFT,
		target=ConnectionApplicationLeadStatus.SUBMITTED,
		custom=dict(
			short_description='Submit Application', admin=True
		),
		# conditions=[can_close]
	)
	def submit(self, *args, **kwargs):
		self.event_submit_channel_whatsapp()


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
				"name": "domestic_application_submitted",
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

					# "notifyUrl": "https://www.example.com/sms/advanced",
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
			ConnectionApplicationLeadStatus.BACK_OFFICE \
			if kwargs.get("required") else ConnectionApplicationLeadStatus.NOT_INTERESTED,
			states=[
				ConnectionApplicationLeadStatus.BACK_OFFICE,
				ConnectionApplicationLeadStatus.NOT_INTERESTED
			]
		),
		custom=dict(short_description='Application Confirmation', admin=True, form=ConnectionVerificationResult),
	)
	def confirm_application(self, *args, **kwargs):
		if kwargs.get("required"):
			self.required_by = kwargs.get("required_by")
			self.applicant_remarks = kwargs.get("applicant_remarks")


	@fsm_log_description
	@fsm_log_by
	@transition(
		field=status,
		source=ConnectionApplicationLeadStatus.BACK_OFFICE,
		# target=ConnectionApplicationLeadStatus.FRONT_OFFICE,
		target=GET_STATE(
			lambda self, **kwargs: \
			ConnectionApplicationLeadStatus.FRONT_OFFICE \
			if kwargs.get("process_type") == ConnectionApplicationProcessType.REACTIVATION \
					else ConnectionApplicationLeadStatus.FRONT_OFFICE_SV,
			states=[
				ConnectionApplicationLeadStatus.FRONT_OFFICE_SV,
				ConnectionApplicationLeadStatus.FRONT_OFFICE
			]
		),
		custom=dict(short_description='Back Office Processing', admin=True, form=BackOfficeForm),
	)
	def front_office_process(self, *args, **kwargs):
		self.consumer_id = kwargs.get("consumer_id")
		self.process_type = kwargs.get("process_type")


	@fsm_log_description
	@fsm_log_by
	@transition(
		field=status,
		source=ConnectionApplicationLeadStatus.FRONT_OFFICE,
		target=GET_STATE(
			lambda self, **kwargs: \
			ConnectionApplicationLeadStatus.COMPLETED \
			if kwargs.get("verified") else ConnectionApplicationLeadStatus.BACK_OFFICE,
			states=[
				ConnectionApplicationLeadStatus.COMPLETED,
				ConnectionApplicationLeadStatus.BACK_OFFICE
			]
		),
		custom=dict(short_description='Front Office Processing', admin=True, form=FrontOfficeForm),
	)
	def application_completed(self, *args, **kwargs):
		if kwargs.get("verified"):
			self.remarks = kwargs.get("remarks")

			# Loading html template & converting to pdf document
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
				sv_doc_pdf_bytes, sv_doc_pdf_bytes.getbuffer().nbytes
			)

			self.documents.create(
				type=ConnectionApplicationDocumentsEnum.SV,
				link=get_minio_public_url(settings.MINIO_BUCKET_NAME, sv_doc_file_name)
			)


	@fsm_log_by
	@transition(
		field=status,
		source=ConnectionApplicationLeadStatus.FRONT_OFFICE_SV,
		target=GET_STATE(
			lambda self, **kwargs: \
			ConnectionApplicationLeadStatus.COMPLETED \
			if kwargs.get("verified") else ConnectionApplicationLeadStatus.BACK_OFFICE,
			states=[
				ConnectionApplicationLeadStatus.COMPLETED,
				ConnectionApplicationLeadStatus.BACK_OFFICE
			]
		),
		custom=dict(short_description='Front Office Processing With SV', admin=True, form=FrontOfficeSVForm),
	)
	def application_completed_sv(self, *args, **kwargs):
		if kwargs.get("verified"):
			self.remarks = kwargs.get("remarks")


class ConnectionApplicationDocuments(models.Model):
	parent = models.ForeignKey(ConnectionApplication, on_delete=models.CASCADE, related_name='documents', null=True)
	type = models.CharField(max_length=25, choices=ConnectionApplicationDocumentsEnum.choices)
	link = models.URLField()
