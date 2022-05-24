import track
from django.conf import settings
from django.contrib.contenttypes.models import ContentType

from communication_log.models import CommunicationLog


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
				"name": "ujjwala_application_submitted_",
				# "name": "domestic_application_sub_8v",
				# "languageCode": "en_GB",
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

		if data['result']:
			CommunicationLog.objects.create(
				content_type=ujjwala_v2_application_content_type,
				object_id=self.pk,
				event="submit", channel="whatsapp",
				message_id=data.get('id')
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

		if data['result']:
			CommunicationLog.objects.create(
				content_type=ujjwala_v2_application_content_type,
				object_id=self.pk,
				event="ioc_dedupe_reject", channel="whatsapp",
				message_id=data.get('id')
			)


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
				"name": "sdms_kyc_dedupe_approved_without_location_dw",
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

		if data['result']:
			CommunicationLog.objects.create(
				content_type=ujjwala_v2_application_content_type,
				object_id=self.pk,
				event="ujjwala_invite_for_ekyc", channel="whatsapp",
				message_id=data.get('id')
			)
