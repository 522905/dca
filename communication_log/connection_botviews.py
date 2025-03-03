import logging
import track
from django.conf import settings
from django.contrib.sites import requests
from django.db.models import Q

from connection_app.jobs import dialogflow_chat_assignment
from connection_app.models import CustomerProfile, SalesOrder
from domestic_app.settings import CAMUNDA_BASE_URL
from teams.models import SDMSUser
from ujjwala.camunda_functions import start_process_in_camunda_v2

logger = logging.getLogger(__name__)


def dialogflow_chat_assignment(session_id):
	body_text = {
		"user_phone_number": f"91{session_id}",
		"agent_email": "guriarora8140@gmail.com",
		"wc_id": " ",
	}

	track.client.post(
		api_key=settings.INTERAKT_API_KEY,
		path="/v1/public/message/",
		body=body_text
	).json()

	logger.info(f'Assign the chat to gurpreet : for user  {session_id}')


def My_clinder_status(unique_id, phone_number):
	from ujjwala.models import FamilyMembers
	# Validate the input
	if not unique_id or len(unique_id) not in [10, 12]:
		return "कृपया एक मान्य मोबाइल या उपभोक्ता नंबर दर्ज करें।"

	if len(unique_id) == 10:
		# Try to find the customer profile based on mobile number or consumer number
		application = CustomerProfile.objects.filter(mobile_number=unique_id).first() or \
					  CustomerProfile.objects.filter(consumer_no=unique_id).first()

	if len(unique_id) == 12:
		family_member = FamilyMembers.objects.filter(uid_no=unique_id).first()
		if not family_member:
			try:
				dialogflow_chat_assignment(phone_number)
				return "हम आपके कनेक्शन का विवरण ढूंढने में असमर्थ हैं, इसलिए हम आपको व्हाट्सएप पर हमारे ग्राहक सेवा से जोड़ रहे हैं"
			except Exception as e:
				logger.error(f"the issue in chat assignment {str(e)}")
				return "आपकी ऑर्डर जानकारी उपलब्ध नहीं है, कृपया अपनी ऑर्डर स्थिति की जांच करें। +91 161 520 1005"

		# TODO
		application = CustomerProfile.objects.filter(mobile_number=family_member.parent.sdms_mobile_number).first()

	if not application:
		return "हमें इस मोबाइल और उपभोक्ता नंबर के साथ कोई एप्लिकेशन नहीं मिला, कृपया अपना आधार कार्ड नंबर साझा करें।"

	# Check if the consumer number exists in the found application
	if not application.consumer_no:
		return "उपभोक्ता संख्या मान्य नहीं है, कृपया सही विवरण प्रदान करें।"

	# Find the related sales order
	saleorder = SalesOrder.objects.filter(relationship_id=application.consumer_id).order_by("-id").first()

	if not saleorder:
		return "आपकी कोई ऑर्डर जानकारी नहीं मिली, कृपया अपनी ऑर्डर स्थिति की जांच करें।"

	# Print debug information for development purposes
	print(saleorder.delivery_boy_full_name, saleorder.delivery_boy_login, saleorder.id, "the sale order details")

	# Ensure that saleorder has the necessary details
	if saleorder.order_status not in ["COMPLETED"]:
		try:
			# Retrieve delivery boy details using the delivery boy's login
			delivery_boy_details = SDMSUser.objects.get(delivery_boy_login=saleorder.delivery_boy_login)
			if delivery_boy_details and delivery_boy_details.parent:
				return f"आपके क्षेत्र के सिलेंडर डिलीवरी बॉय का नंबर {delivery_boy_details.parent.phone_number} है, " \
					   f"आपके सिलेंडर पहुंचने के समय के बारे में जानने के लिए कृपया उससे संपर्क करें।"
			else:
				return "डिलीवरी बॉय की जानकारी उपलब्ध नहीं है, कृपया बाद में पुनः प्रयास करें।"
		except SDMSUser.DoesNotExist:
			return "डिलीवरी बॉय की लॉगिन जानकारी मान्य नहीं है, कृपया बाद में पुनः प्रयास करें।"
		except SDMSUser.MultipleObjectsReturned:
			return "डिलीवरी बॉय की लॉगिन जानकारी के लिए कई रिकॉर्ड्स पाए गए, कृपया सहायता केंद्र से संपर्क करें।"
		except Exception as e:
			# Log any unexpected exception for debugging
			print(f"Unexpected error: {e}")
			return "सिस्टम में कुछ गड़बड़ी हो गई है, कृपया बाद में पुनः प्रयास करें।"

	return "आपकी ऑर्डर जानकारी उपलब्ध नहीं है, कृपया अपनी ऑर्डर स्थिति की जांच करें। +91 161 520 1005"


def start_process_fetch_subsidy_status_of_customer_from_sdms(consumer_id,distributor_code,phone_number):
 if not consumer_id and not distributor_code:
  raise Exception("Customer Id and distribution code Not Found for subsidy status")

 variables = {
  "variables": {
   "consumer_id": {"value": consumer_id, "type": "String"},
   "consumer_contact": {"value": phone_number, "type": "String"},
   "distributor_code": {"value": distributor_code, "type": "String"},
  }
 }
 res, pid = start_process_in_camunda_v2('Process_FetchAndSendSubsidyDetailsToCustomer', variables=variables)
 if res == 200:
  print(res)
  return pid


def cylinder_subsidy_status(phone_number,number=None):
	consumer_id = None
	if not phone_number:
		return "कृपया एक मान्य मोबाइल नंबर दर्ज करें।"

	if number and len(number) > 4:
		consumer_id = number[:2] + "000000" + number[2:]

	cust_obj = CustomerProfile.objects.filter(Q(mobile_number=phone_number) |
											  Q(consumer_no=number) |
											  Q(consumer_id=consumer_id)).first()

	if not cust_obj:
		return "हमें इस मोबाइल नंबर से कोई ग्राहक नहीं मिला। कृपया consumer नंबर share करिए"

	try:
		res_pid = start_process_fetch_subsidy_status_of_customer_from_sdms(cust_obj.consumer_id, cust_obj.distributor_code,
																 phone_number)
		if res_pid:
			return "आपकी subsidy की जानकारी पता की जा रही है। आपको जल्द ही सुचिता कर दिया जाये गए|"
	except Exception as e:
		print(f'the  unexpected error: {e}')
		return "सिस्टम में कुछ गड़बड़ी हो गई है, कृपया बाद में पुनः प्रयास करें।"
