import requests
import track
from django.contrib.contenttypes.models import ContentType

from communication_log.models import CommunicationLog
from domestic_app import settings
from domestic_app.settings import INFOBIP_URL, INFOBIP_NOTIFY_URL


def send_whatsapp_message(phone_number, template_name, body_values, language_code="hi"):
	body_text = {
		"countryCode": "+91",
		"phoneNumber": phone_number,
		"type": "Template",
		"traits": {"name": phone_number},
		"template": {
			"name": template_name,
			"languageCode": language_code,
			"headerValues": [
				# "Alert",  #
			],
			"bodyValues": body_values
		}
	}

	data = track.client.post(
		api_key=settings.INTERAKT_API_KEY,
		path="/v1/public/message/",
		body=body_text
	).json()

	return data.get('result'), data


def send_sms(mobile, message, template_id):
	x = requests.post(INFOBIP_URL, json={
		"messages": [
			{
				"from": "ARUNGS",
				"destinations": [
					{
						"to": "+91{}".format(mobile)
					}
				],

				"text": message,
				"flash": False,

				"regional": {
					"indiaDlt": {
						"principalEntityId": "1101546710000030317",
						"contentTemplateId": template_id
					}
				},
				"notifyUrl": INFOBIP_NOTIFY_URL,
				"notifyContentType": "application/json",
				# "callbackData": "DLR callback data",
				# "validityPeriod": 720
			}
		]
	}, headers={
		'Authorization': 'App 140a3abf6dd9134f5defb703a54dfcf0-e3df520b-f144-4282-a174-aa3765c7b438'
	})
	return x.status_code == 200, x.json()


