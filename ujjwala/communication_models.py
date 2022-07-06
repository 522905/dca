import io

import requests
import track
from django.conf import settings
from django.contrib.contenttypes.models import ContentType
from django.template import loader

from communication_log.models import CommunicationLog
from connection_app.models import minio_client
from ujjwala.enums import UjjwalaApplicationDocumentsEnum


class UjjwalaWhatsappCommunication(object):
	def event_submit_channel_whatsapp(self):
		body_text = {
			"countryCode": "+91",
			"phoneNumber": self.contact_mobile,
			"type": "Template",
			"traits": {
				"name": self.name,
			},
			# "callbackData": "some_callback_data",
			"template": {
				# "name": "ujjwala_application_submitted_",
				"name": "ujjwala_application_submitted_300522",
				"languageCode": "hi",
				"headerValues": [
					# "Alert",  #
				],
				"bodyValues": [
					self.name,
					self.id,
					"90"
				],
				"buttonValues": {
					"0": [
						"connection-app/connection-application/{}/".format(self.id)
					]
				}
			}
		}

		ujjwala_v2_application_content_type = ContentType.objects.get(
			app_label='ujjwala', model='ujjwalav2application'
		)
		data = track.client.post(
			api_key=settings.INTERAKT_API_KEY,
			path="/v1/public/message/",
			body=body_text
		).json()

		if data.get('result', ''):
			CommunicationLog.objects.create(
				content_type=ujjwala_v2_application_content_type,
				object_id=self.pk,
				channel_subscriber=self.contact_mobile,
				event="submit", channel="whatsapp",
				message_id=data.get('id')
			)

		res = requests.post(
			"http://vici.arungas.com/vicidial/non_agent_api.php?source=ujjwala&user=6666&pass=C00lerMaster"
			"&function=add_lead&phone_number={}&list_id=1006&first_name={}&last_name={}".format(
				self.contact_mobile, self.name, self.pk
			)
		)

	def event_ioc_dedupe_reject_channel_whatsapp(self):
		from ujjwala.models import FamilyMembers

		family_member_with_connection: FamilyMembers = None
		for family_member in self.family_members.all():
			distributor_name = family_member.uid_check_result.get('distributor_name', '')
			if not distributor_name or (
				distributor_name and 'arun indane' in distributor_name.lower()
			):
				continue
			family_member_with_connection = family_member
			break

		if not family_member_with_connection:
			return

		body_text = {
			"countryCode": "+91",
			"phoneNumber": self.contact_mobile,
			"type": "Template",
			"traits": {
				"name": self.name,
			},
			# "callbackData": "some_callback_data",
			"template": {
				"name": "sdms_omc_dedupe_rejection_jz",
				"languageCode": "hi",
				"headerValues": [
					# "Alert",  #
				],
				"bodyValues": [
					self.name,
					self.id,
					family_member_with_connection.name,
					family_member_with_connection.uid_check_result.get('distributor_name', ''),
					family_member_with_connection.uid_check_result.get('consumer_id')
				],
			}
		}
		ujjwala_v2_application_content_type = ContentType.objects.get(
			app_label='ujjwala', model='ujjwalav2application'
		)
		data = track.client.post(
			api_key=settings.INTERAKT_API_KEY,
			path="/v1/public/message/",
			body=body_text
		).json()

		if data.get('result', ''):
			CommunicationLog.objects.create(
				content_type=ujjwala_v2_application_content_type,
				object_id=self.pk,
				event="ioc_dedupe_reject", channel="whatsapp",
				channel_subscriber=self.contact_mobile,
				message_id=data.get('id')
			)

	# Invite For Ekyc After SDMS Dedupe
	def event_invite_for_ekyc_channel_whatsapp(self):
		body_text = {
			"countryCode": "+91",
			"phoneNumber": self.contact_mobile,
			"type": "Template",
			"traits": {
				"name": self.name,
			},
			# "callbackData": "some_callback_data",
			"template": {
				# "name": "sdms_kyc_dedupe_approved_without_location_dw",
				"name": "sdms_omc_dedupe_approved_300522",
				"languageCode": "hi",
				"headerValues": [
					# "Alert",  #
				],
				"bodyValues": [
					self.id
				],
			}
		}

		ujjwala_v2_application_content_type = ContentType.objects.get(
			app_label='ujjwala', model='ujjwalav2application'
		)
		data = track.client.post(
			api_key=settings.INTERAKT_API_KEY,
			path="/v1/public/message/",
			body=body_text
		).json()

		if data.get('result', ''):
			CommunicationLog.objects.create(
				content_type=ujjwala_v2_application_content_type,
				object_id=self.pk,
				channel_subscriber=self.contact_mobile,
				event="ujjwala_invite_for_ekyc", channel="whatsapp",
				message_id=data.get('id')
			)

		res = requests.post(
			"http://vici.arungas.com/vicidial/non_agent_api.php?source=ujjwala&user=6666&pass=C00lerMaster"
			"&function=add_lead&phone_number={}&list_id=1007&first_name={}&last_name={}".format(
				self.contact_mobile, self.name, self.pk
			)
		)

	def event_legal_documents_upload_channel_whatsapp(self):
		from ujjwala.models import ConnectionDisbursement

		connection_disbursement = ConnectionDisbursement.objects.get(parent_id=self.pk)

		physical_legal_doc_link = self.pre_inspection_accepted.documents.filter(
			type=UjjwalaApplicationDocumentsEnum.PHYSICAL_LEGAL_DOCUMENT
		).first().link

		body_text = {
			"countryCode": "+91",
			"phoneNumber": self.contact_mobile,
			"type": "Template",
			"traits": {
				"name": self.name,
			},
			# "callbackData": "some_callback_data",
			"template": {
				"name": "ujjwala_legal_documents_upload__10062022",
				"languageCode": "hi",
				"headerValues": [
					physical_legal_doc_link,  #
				],
				"bodyValues": [
					self.name
				],
				"buttonValues": {
					"0": [
						"ujjwala/portal/legal_documents_upload/{}/".format(
							connection_disbursement.pk
						)
					]
				}
			}
		}

		ujjwala_v2_application_content_type = ContentType.objects.get(
			app_label='ujjwala', model='ujjwalav2application'
		)
		data = track.client.post(
			api_key=settings.INTERAKT_API_KEY,
			path="/v1/public/message/",
			body=body_text
		).json()

		if data.get('result', ''):
			CommunicationLog.objects.create(
				content_type=ujjwala_v2_application_content_type,
				object_id=self.pk,
				channel_subscriber=self.contact_mobile,
				event="physcial_legal_document", channel="whatsapp",
				message_id=data.get('id')
			)

		res = requests.post(
			"http://vici.arungas.com/vicidial/non_agent_api.php?source=ujjwala&user=6666&pass=C00lerMaster"
			"&function=add_lead&phone_number={}&list_id=1009&first_name={}&last_name={}".format(
				self.contact_mobile, self.name, self.pk
			)
		)
		# res = requests.post(
		# 	"http://vici.hawabadlo.in/vicidial/non_agent_api.php?source=ujjwala&user=6666&pass=C00lerMaster"
		# 	"&function=add_lead&phone_number={}&list_id=1006&first_name={}&last_name={}".format(
		# 		self.contact_mobile, self.name, self.pk
		# 	)
		# )


	def event_legal_documents_reupload_channel_whatsapp(self):
		body_text = {
			"countryCode": "+91",
			"phoneNumber": self.contact_mobile,
			"type": "Template",
			"traits": {
				"name": self.name,
			},
			# "callbackData": "some_callback_data",
			"template": {
				"name": "ujjwala_legal_documents_reupload",
				"languageCode": "hi",
				"headerValues": [
					# "Alert",  #
				],
				"bodyValues": [
					self.name
				],
				"buttonValues": {
					"0": [
						"ujjwala/ujjwala-application/legal_documents_upload/{}/".format(
							self.id
						)
					]
				}
			}
		}

		ujjwala_v2_application_content_type = ContentType.objects.get(
			app_label='ujjwala', model='ujjwalav2application'
		)
		data = track.client.post(
			api_key=settings.INTERAKT_API_KEY,
			path="/v1/public/message/",
			body=body_text
		).json()

		if data.get('result', ''):
			CommunicationLog.objects.create(
				content_type=ujjwala_v2_application_content_type,
				object_id=self.pk,
				channel_subscriber=self.contact_mobile,
				event="legal_documents_upload", channel="whatsapp",
				message_id=data.get('id')
			)

	def event_whatsapp_nic_error_update_address(self):
		body_text = {
			"countryCode": "+91",
			"phoneNumber": self.contact_mobile,
			"type": "Template",
			"traits": {
				"name": self.name,
			},
			# "callbackData": "some_callback_data",
			"template": {
				# "name": "ujjwala_application_submitted_",
				"name": "nic_error_update_address",
				"languageCode": "hi",
				"headerValues": [
					# "Alert",  #
				],
				"bodyValues": [
					self.name,
				],
				"buttonValues": {
					"0": [
						"ujjwala/portal/nic_error_update_address/{}/".format(self.id)
					]
				}
			}
		}

		ujjwala_v2_application_content_type = ContentType.objects.get(
			app_label='ujjwala', model='ujjwalav2application'
		)
		data = track.client.post(
			api_key=settings.INTERAKT_API_KEY,
			path="/v1/public/message/",
			body=body_text
		).json()

		if data.get('result', ''):
			CommunicationLog.objects.create(
				content_type=ujjwala_v2_application_content_type,
				object_id=self.pk,
				channel_subscriber=self.contact_mobile,
				event="nic_error_update_address", channel="whatsapp",
				message_id=data.get('id')
			)

		# res = requests.post(
		# 	"http://vici.arungas.com/vicidial/non_agent_api.php?source=ujjwala&user=6666&pass=C00lerMaster"
		# 	"&function=add_lead&phone_number={}&list_id=1006&first_name={}&last_name={}".format(
		# 		self.contact_mobile, self.name, self.pk
		# 	)
		# )
		return data.get('result', '')

	def event_whatsapp_pre_inspection_type_self(self, pre_inspection_id):
		body_text = {
			"countryCode": "+91",
			"phoneNumber": self.contact_mobile,
			"type": "Template",
			"traits": {
				"name": self.name,
			},
			# "callbackData": "some_callback_data",
			"template": {
				# "name": "ujjwala_application_submitted_",
				"name": "pre_inspection_type_self",
				"languageCode": "hi",
				"headerValues": [
					# "Alert",  #
				],
				"bodyValues": [
					self.name,
					"https://dca-local.arungas.com/portal/pre-inspection/{}/".format(str(pre_inspection_id))
				],
				"buttonValues": {
					"0": [
						"ujjwala/portal/whatsapp_pre_inspection_type_self/{}/".format(pre_inspection_id)
					]
				}
			}
		}

		ujjwala_v2_application_content_type = ContentType.objects.get(
			app_label='ujjwala', model='ujjwalav2application'
		)
		data = track.client.post(
			api_key=settings.INTERAKT_API_KEY,
			path="/v1/public/message/",
			body=body_text
		).json()

		if data.get('result', ''):
			CommunicationLog.objects.create(
				content_type=ujjwala_v2_application_content_type,
				object_id=self.pk,
				channel_subscriber=self.contact_mobile,
				event="pre_inspection_type_self", channel="whatsapp",
				message_id=data.get('id')
			)

		# res = requests.post(
		# 	"http://vici.arungas.com/vicidial/non_agent_api.php?source=ujjwala&user=6666&pass=C00lerMaster"
		# 	"&function=add_lead&phone_number={}&list_id=1006&first_name={}&last_name={}".format(
		# 		self.contact_mobile, self.name, self.pk
		# 	)
		# )
		return data.get('result', '')
