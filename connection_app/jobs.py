from ujjwala.camunda_functions import start_process_in_camunda_v2
import logging , track
from django.conf import settings
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

def start_sales_order_portability_process(sales_order_portability_id):
	from connection_app.models import SalesOrderPortability
	from teams.models import SDMSUser

	sop_obj = SalesOrderPortability.objects.get(pk=sales_order_portability_id)
	sdms_user: SDMSUser = sop_obj.user.userprofile.objects.filter(sdmsuser__distributor=sop_obj.distributor).first()

	variables = {
		"variables":
			{
				"sales_order_id": {"value": sop_obj.sales_order_number, "type": "String"},
				"delivery_boy_id": {"value": sdms_user.delivery_boy_login, "type": "String"},
			}
		}

	res, pid = start_process_in_camunda_v2('Process_domestic_app', variables=variables)
	if res == 200:
		sop_obj.camunda_process_id = pid
		sop_obj.save()
	raise Exception(res.text)


def start_read_customer_profile(customer_profile_id):
	from connection_app.models import CustomerProfile

	cp_obj = CustomerProfile.objects.get(pk=customer_profile_id)
	variables = {
		"variables":
			{
				"sdms_task": {"value": "read_customer_profile", "type": "String"},
				"consumer_id": {"value": cp_obj.consumer_id, "type": "String"},
				"customer_profile_id": {"value": cp_obj.id, "type": "Long"},
				"distributor_code": {"value": cp_obj.distributor_code, "type": "String"}
			}
	}

	res, pid = start_process_in_camunda_v2('Process_domestic_app', variables=variables)
	if res == 200:
		cp_obj.camunda_process_instance_id = pid
		cp_obj.save()
	print(res)
