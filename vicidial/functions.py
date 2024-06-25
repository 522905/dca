import requests

# VICI_URL = 'http://vici.arunas.com'
from django.contrib.sites.models import Site
from django.urls import reverse

from communication_log.functions import send_template_link_sms
from reference_data.functions import create_tiny_html_template_url_for_sms
from ujjwala.ujjwala_functions import get_signed_share_data
from utils.global_functions import sign_data_base64

VICI_URL = 'http://192.168.168.3'


def update_lead_in_out1005_campaign(mobile):
	query = "{}/vicidial/non_agent_api.php?source=localhost&user=6666&pass=C00lerMaster101&function=update_lead"
	"&phone_number={}&search_method=PHONE_NUMBER&list_id=602&search_location=LIST&insert_if_not_found=Y"
	"&campaign_id=OUTG1005&phone_code=1&status=MSDCAL&reset_lead=Y".format(VICI_URL, mobile)
	res = requests.post(query)
	return res


def update_lead_in_ujjwala_welcome(mobile):
	res = requests.post(
		"{}/vicidial/non_agent_api.php?source=ujjwala&user=6666&pass=C00lerMaster101"
		"&function=add_lead&phone_number={}&list_id=1007".format(VICI_URL, mobile)
	)
	return res


def update_lead_in_ujjwala_enquiry_list(mobile):
	res = requests.post(
		"{}vicidial/non_agent_api.php?source=ujjwala&user=6666&pass=C00lerMaster101"
		"&function=add_lead&phone_number={}&list_id=77771".format(VICI_URL, mobile)
	)
	return res


def add_lead_to_vicidial(contact_mobile, name, id):
	res = requests.post(
		"{}/vicidial/non_agent_api.php?source=ujjwala&user=6666&pass=C00lerMaster101&function=add_lead&phone_number={}"
		"&phone_code=1&list_id=1001&first_name={}&last_name={}".format(VICI_URL, contact_mobile, name, id)
	)
	return res


def add_lead_to_vicidial_list(list_id, contact_mobile, name, object_id):
	res = requests.post(
		"{url}/vicidial/non_agent_api.php?source=ujjwala&user=6666&pass=C00lerMaster101"
		"&function=add_lead&phone_number={contact_mobile}&phone_code=1&list_id={list_id}"
		"&first_name={first_name}&last_name={last_name}".format(
			url=VICI_URL, list_id=list_id, contact_mobile=contact_mobile, first_name=name, last_name=object_id)
	)
	return res


def delete_lead_from_vicidial_list(list_id, contact_mobile):
	res = requests.post(
		"{}/vicidial/non_agent_api.php?source=ujjwala&user=6666&pass=C00lerMaster101"
		"&function=update_lead&search_location=LIST&search_method=PHONE_NUMBER&delete_lead=Y"
		"&phone_number={}&list_id={}".format(VICI_URL, contact_mobile, list_id)
	)

	return res


def send_ujjwala_application_sms_link(contact_mobile, user_id, host=""):
	data = get_signed_share_data(contact_mobile, user_id)
	url = reverse('ujjwala:ujjwala_application_link', kwargs={'data': data})
	url = url[1:]

	host = host if host else Site.objects.get_current().domain
	req = requests.get(
		"https://tinyurl.com/api-create.php", params={'url': f"{host}/{url}"},
	)
	req.raise_for_status()

	data = sign_data_base64({
		'template': 'ujjwala_share_link',
		'variables': {
			'link': req.text
		}
	})
	url = create_tiny_html_template_url_for_sms(data, host)

	return send_template_link_sms(contact_mobile, "Ujjwala Application Form", url)


def send_non_ujjwala_applicant_status_sms_link(contact_mobile, user_id, host=""):
	data = get_signed_share_data(contact_mobile, user_id)
	url = reverse('ujjwala:ujjwala_application_link', kwargs={'data': data})
	url = url[1:]

	host = host if host else Site.objects.get_current().domain
	req = requests.get(
		"https://tinyurl.com/api-create.php", params={'url': f"{host}/{url}"},
	)
	req.raise_for_status()

	data = sign_data_base64({
		'template': 'non_ujjwala_applicant_share_link',
		'variables': {
			'link': req.text
		}
	})
	url = create_tiny_html_template_url_for_sms(data, host)

	return send_template_link_sms(contact_mobile, "Ujjwala Application Form", url)


def send_new_connection_application_sms_link(contact_mobile, host=""):
	# data = get_signed_share_data(contact_mobile, user_id)
	# url = reverse('ujjwala:ujjwala_application_link', kwargs={'data': data})
	# url = url[1:]

	host = host if host else Site.objects.get_current().domain
	req = requests.get(
		"https://tinyurl.com/api-create.php", params={'url': f"{host}/connection_app/connection-application/start/"},
	)
	req.raise_for_status()

	return send_template_link_sms(contact_mobile, "New Connection Form", req.text)


def send_ujjwala_application_status_sms_link(contact_mobile, application_id, host=""):
	"""
		http://192.168.168.4:60613/ujjwala/portal/ujjwala-customer-profile-public/255/
		@param application_id:
		@param contact_mobile:
		@param host:
		@return:
	"""
	url = reverse('ujjwala:ujjwala_customer_profile_public', kwargs={'pk': application_id})
	url = url[1:]

	host = host if host else Site.objects.get_current().domain
	req = requests.get(
		"https://tinyurl.com/api-create.php", params={'url': f"{host}/{url}"},
	)
	req.raise_for_status()

	return send_template_link_sms(contact_mobile, "Ujjwala Application Status", req.text)