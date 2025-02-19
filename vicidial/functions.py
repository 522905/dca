import requests

# VICI_URL = 'http://vici.arunas.com'
from django.contrib.sites.models import Site
from django.urls import reverse

from communication_log.functions import send_template_link_sms
from reference_data.functions import create_tiny_html_template_url_for_sms
from ujjwala.ujjwala_functions import get_signed_share_data
from utils.global_functions import sign_data_base64, generate_tiny_url

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
	# req = requests.get(
	# 	"https://tinyurl.com/api-create.php", params={'url': f"{host}/connection_app/connection-application/start/"},
	# )
	# req.raise_for_status()

	short_url = generate_tiny_url(f"{host}/connection_app/connection-application/start/")

	return send_template_link_sms(contact_mobile, "New Connection Form", short_url)


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
	# req = requests.get(
	# 	"https://tinyurl.com/api-create.php", params={'url': f"{host}/{url}"},
	# )
	# req.raise_for_status()

	short_url = generate_tiny_url(f"{host}/{url}")

	return send_template_link_sms(contact_mobile, "Ujjwala Application Status", short_url)


def get_ujjwala_application_link(contact_mobile, host, user_id):
	from ujjwala.models import UjjwalaV2Application

	host = host if host else Site.objects.get_current().domain

	application = UjjwalaV2Application.objects.filter(contact_mobile=contact_mobile).first()
	if application:
		url = reverse('ujjwala:ujjwala_customer_profile_public', kwargs={'pk': application.id})
		url = url[1:]

		ujjwala_url = generate_tiny_url(f"{host}/{url}")
	else:
		data = get_signed_share_data(contact_mobile, user_id)
		url = reverse('ujjwala:ujjwala_application_link', kwargs={'data': data})
		url = url[1:]

		host = host if host else Site.objects.get_current().domain
		req = requests.get(
			"https://tinyurl.com/api-create.php", params={'url': f"{host}/{url}"},
		)
		req.raise_for_status()
		ujjwala_url = req.text
	return ujjwala_url


def send_response_template_phone_code_1_sms_link(contact_mobile, user_id, host=""):
	# data = get_signed_share_data(contact_mobile, user_id)
	# # url = reverse('vicidial:response_view_for_phone_code_1', kwargs={'data': data})
	# url = reverse('response_view_for_phone_code_1', kwargs={'data': data})
	# url = url[1:]

	host = host if host else Site.objects.get_current().domain
	# req = requests.get(
	# 	"https://tinyurl.com/api-create.php", params={'url': f"{host}/{url}"},
	# )
	# req.raise_for_status()

	data = sign_data_base64({
		'template': 'response_view_for_phone_code_1',
		'variables': {
			'contact_mobile': contact_mobile,
			'user_id': user_id,
			'ujjwala_url': get_ujjwala_application_link(contact_mobile, host, user_id)
		}
	})
	url = create_tiny_html_template_url_for_sms(data, host)

	return send_template_link_sms(contact_mobile, "Arun Gas Domestic Services", url)


from connection_app.enums import SalesOrderInvoiceEnum, SalesOrderStatusEnum
from connection_app.models import CustomerProfile, SalesOrder
from teams.models import SDMSUser, UserProfile
from typing import Optional
from django.core.exceptions import ObjectDoesNotExist
from django.shortcuts import get_object_or_404
import logging

logger = logging.getLogger(__name__)


def transfer_in_out1005_to_delivery_boy(mobile: str) -> Optional[str]:
	"""
	Get delivery boy phone number for a customer's latest invoiced order.

	Args:
		mobile (str): Customer mobile number

	Returns:
		Optional[str]: Delivery boy phone number if found, None otherwise

	Raises:
		ValueError: If mobile number format is invalid
	"""
	# Input validation
	if not mobile or not isinstance(mobile, str):
		logger.error(f"Invalid mobile number format: {mobile}")
		return None

	try:
		# Get customer profile
		customer_profile = get_object_or_404(
			CustomerProfile,
			mobile_number=mobile
		)

		# Get latest invoiced sale order
		sale_order = SalesOrder.objects.filter(
			relationship_id=customer_profile.consumer_id,
			order_status=SalesOrderStatusEnum.INVOICED
		).order_by('-order_date').first()

		if not sale_order:
			logger.info(f"No invoiced orders found for customer: {mobile}")
			return None

		if not sale_order.delivery_boy_login:
			logger.warning(f"No delivery boy assigned to order: {sale_order.id}")
			return None

		# Get delivery boy details
		delivery_boy = get_object_or_404(
			UserProfile,
			sdmsuser__delivery_boy_login__icontains=sale_order.delivery_boy_login
		)

		return delivery_boy.phone_number

	except ObjectDoesNotExist as e:
		logger.error(f"Object not found: {str(e)}")
		return None
	except Exception as e:
		logger.exception(f"Unexpected error while processing mobile {mobile}: {str(e)}")
		return None


def fetch_numbers_delivery_boys(mobile: str) -> Optional[str]:
	"""
	Get delivery boy phone number for a customer's latest invoiced order.

	Args:
		mobile (str): Customer mobile number

	Returns:
		Optional[str]: Delivery boy phone number if found, None otherwise.

	Raises:
		ValueError: If mobile number format is invalid.
	"""
	# Input validation for mobile number
	if not mobile or not isinstance(mobile, str):
		logger.error(f"Invalid mobile number format (not a string): {mobile}")
		return None

	try:
		# Get the customer profile (latest by updated_on)
		customer_profile = CustomerProfile.objects.filter(mobile_number=mobile).order_by("-updated_on").first()

		if not customer_profile:
			logger.warning(f"No customer profile found for mobile number: {mobile}")
			return None  # Assuming this is the fallback message if no customer profile is found

		# Log found customer profile details
		logger.info(f"Found customer profile for mobile {mobile}: {customer_profile.id}")

		# Get delivery boy details based on sdms_service_area (related to customer profile)
		delivery_boy_details = UserProfile.objects.filter(sdms_service_areas=customer_profile.sdms_service_area).first()

		if not delivery_boy_details:
			logger.warning(
				f"No delivery boy found for customer profile with SDMSServiceArea: {customer_profile.sdms_service_area}")
			return None  # Assuming fallback message if no delivery boy is found

		# Log the found delivery boy details
		logger.info(
			f"Found delivery boy for customer {mobile}: {delivery_boy_details.id}, phone: {delivery_boy_details.phone_number}")

		return delivery_boy_details.phone_number

	except ObjectDoesNotExist as e:
		# Handle case where an object doesn't exist in the database
		logger.error(f"Object not found for mobile {mobile}: {str(e)}")
		return None
	except Exception as e:
		# Catch any other unexpected errors and log them
		logger.exception(f"Unexpected error while processing mobile {mobile}: {str(e)}")
		return None