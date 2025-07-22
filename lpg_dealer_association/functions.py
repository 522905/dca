from django.contrib.sites.models import Site

from communication_log.functions import send_sms
from communication_log.models import CommunicationLog
from utils.global_functions import sign_data_base64



def send_template_link_sms(contact_mobile, topic):
	"""
		01615201005_ivr_call_message_v2
	"""
	from otp.models import Otp

	url = "https://ludhianalpg.com/contactus.html"

	template_id = '1107175309566728561'
	message = f"""Jai Hind
Welcome to Ludhiana LPG Dealers Welfare Association.
for more info Click Link Below {url} -Arun Gas"""

	status_code, result = send_sms(contact_mobile, message, template_id)

	if status_code == 200:
		if result.get('messages', ''):
			CommunicationLog.objects.create(
				channel_subscriber=contact_mobile,
				event="lpg_dealer_welfare_welcome_message", channel="sms",
				message_id=result.get('messages', '')[0]['messageId']
			)
	return True


def send_response_template_phone_code_1_sms(contact_mobile):
	return send_template_link_sms(contact_mobile, "LPG Dealer Welfare Welcome SMS")
