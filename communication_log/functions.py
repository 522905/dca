import string
from datetime import datetime, timedelta

import requests

from communication_log.models import CommunicationLog
from domestic_app.settings import INFOBIP_NOTIFY_URL, INFOBIP_URL
from otp.serializer import __get_ref_no__, id_generator


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


def send_template_link_sms(contact_mobile, topic, link):
	"""
		01615201005_ivr_call_message_v2
	"""
	from otp.models import Otp

	template_id = '1107171903678756881'
	message = f"""Jai Hind
As Per Your Request For {topic}
Click Link Below:-
{link} -Arun Gas"""

	ref_no = None

	while True:
		ref_no = __get_ref_no__()
		try:
			Otp.objects.get(reference_number=ref_no)
		except Otp.DoesNotExist:
			break

	otp = id_generator(4, chars=string.digits)
	valid_till = datetime.now() + timedelta(minutes=5)
	closed = False

	otp_obj = Otp.objects.create(
		reference_number=ref_no,
		mobile=contact_mobile,
		otp=otp,
		valid_till=valid_till,
		closed=closed,
		extra={
			"contact_mobile": contact_mobile
		}
	)

	status_code, result = send_sms(contact_mobile, message, template_id)

	if status_code == 200:
		if result.get('messages', ''):
			CommunicationLog.objects.create(
				channel_subscriber=contact_mobile,
				event="ujjwala_application_sms_contact_otp", channel="sms",
				message_id=result.get('messages', '')[0]['messageId']
			)
			return ref_no
