import csv
import datetime


from connection_app.enums import TemplateEnum, ImportDataStatusEnum, DistributorStatusEnum
from connection_app.vicidial.jobs import make_api_request, VICIDIAL_NON_AGENT_API, VICIDIAL_CAMPAIGN_API
from ujjwala.camunda_functions import start_process_in_camunda_v2
import logging
import track
from django.conf import settings
from domestic_app.settings import START_CALL_URL, CAMUNDA_BASE_URL

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


def import_sales_order(csv_file_rows):
	from connection_app.camunda_functions import start_process_fetch_sales_order_details_from_sdms_for_import

	for idx, row in enumerate(csv_file_rows):
		sales_order_number = row['sales_order_number']
		order_status = 'Completed'
		distributor_code = row['distributor_code'].replace(";", "")
		start_process_fetch_sales_order_details_from_sdms_for_import(sales_order_number, distributor_code,order_status)
	return True


def import_bulk_is_dirty(csv_file_rows):
	from connection_app.models import CustomerProfile

	for idx, row in enumerate(csv_file_rows):
		consumer_id = row['consumer_id'].replace(";", "")
		cp_obj = CustomerProfile.objects.filter(consumer_id=consumer_id).first()
		if cp_obj:
			cp_obj.is_dirty = True
			cp_obj.save()
			start_read_customer_profile(cp_obj.pk)
	return True


def import_update_distributor(csv_file_rows):
	from connection_app.models import CustomerProfile, Distributor

	for idx, row in enumerate(csv_file_rows):
		try:
			consumer_id = row['consumer_id'].replace(";", "")
			cp_obj = CustomerProfile.objects.get(consumer_id=consumer_id)
			distributor_code = row['distributor_code'].replace(";", "")
			distributor_obj = Distributor.objects.get(code=distributor_code)

			if cp_obj.distributor_id != distributor_obj.id:
				cp_obj.distributor = distributor_obj
				cp_obj.distributor_code = distributor_obj.code
				cp_obj.distributor_name = distributor_obj.name
				cp_obj.distributor_status = DistributorStatusEnum.MANUALLY_UPDATED
				cp_obj.save()

			cp_obj.is_dirty = True
			start_read_customer_profile(cp_obj.pk)
		except Exception as e:
			continue
	return True


def import_update_bulk_out(csv_file_rows):
	from connection_app.models import CustomerProfile

	for idx, row in enumerate(csv_file_rows):
		consumer_id = row['consumer_id'].replace(";", "")
		cp_obj: CustomerProfile = CustomerProfile.objects.get(consumer_id=consumer_id)
		cp_obj.relationship_status = 'BULK_OUT'
		cp_obj.relationship_sub_status = 'BULK_OUT'
		cp_obj.distributor_code = None
		cp_obj.distributor_name = row['distributor_name']
		cp_obj.save()
	return True


def import_service_area(csv_file_rows):
	import requests

	PROCESS_DEFINITION_KEY = "Process_service_area_update_in_sdms"

	for idx, r in enumerate(csv_file_rows):
		print(r)
		if not r['consumer_id']:
			continue
		variables = {
			"variables":
				{
					"consumer_id": {"value": r['consumer_id'].replace(";", ""), "type": "String"},
					"service_area": {"value": r['service_area'], "type": "String"},
					"distributor_id": {"value": r['distributor_id'].replace(";", ""), "type": "String"}
				}
		}

		url = "{}/process-definition/key/{}/start".format(CAMUNDA_BASE_URL, PROCESS_DEFINITION_KEY)
		requests.post(url, json=variables)


def schedule_upload_data(template, id_obj):
	from connection_app.functions import schedule_booking_cancellation_csv

	id_obj.status = ImportDataStatusEnum.PROCESSING
	id_obj.save()

	try:
		with open(id_obj.file_path, 'r', encoding='ISO-8859-1') as f:
			reader = csv.DictReader(f)
			data_rows = []
			for row in reader:
				try:
					data_rows.append(row)
				except Exception as e:
					print(e)
					continue

		function = globals().get("import_{}".format(id_obj.import_data_template.template.lower().replace(" ", "_")))

		if function and callable(function):
			function(data_rows)  # Pass arguments dynamically
			id_obj.status = ImportDataStatusEnum.COMPLETED
			id_obj.save()
		else:
			raise Exception("{} Function not found".format("import_{}".format(id_obj.import_data_template.template.lower().replace(" ", "_"))))

	except Exception as e:
		id_obj.error_log = str(e)
		id_obj.status = ImportDataStatusEnum.FAILED
		id_obj.save()

def update_camp_url(self, agent_user):
	campaign_payload = {
		"user": self.user,
		"pass": self.password,
		"campaign_id": agent_user,
		'call_url': START_CALL_URL,
		'upcampaign': True,
	}
	result = make_api_request(VICIDIAL_CAMPAIGN_API, campaign_payload)
	if result["status"] == "error":
		print("Error in creating campaign", result)
		return result
	return {"status": "success", "message": "Campaign updated successfully."}

def update_phone(self, agent_user, phone_number, request=None):
	if not phone_number and not agent_user:
		return {"status": "error", "message": "Phone number and agent user are required."}

	phone_load = {
		"user": self.user,
		"pass": self.password,
		"function": "update_phone",
		"source": "external_update_phone",
		"extension": agent_user,
		"dialplan_number": phone_number,
		"server_ip": "192.168.168.3",
	}
	result = make_api_request(VICIDIAL_NON_AGENT_API, phone_load)
	if result["status"] == "error":
		return result

	result2 = self.update_camp_url(agent_user)

	if result2["status"] == "error":
		return result2

	return {"status": "success", "message": "Phone and call url updated successfully.", "pass": request.user.id}


def parse_datetime(date_str, time_str):
	"""Helper to parse datetime from CSV"""
	if not date_str:
		return None
	try:
		return datetime.datetime.strptime(f"{date_str} {time_str}", "%Y-%m-%d %H:%M:%S")
	except Exception:
		return None


def compare_and_update_delivery_register(distributor_code: str, delivery_register_date: str, file_path: str):
	"""
	Compare delivery register CSV with SalesOrder records, create missing ones,
	and trigger Camunda processes where details need to be updated.
	"""
	from connection_app.models import SalesOrder, Distributor
	from connection_app.camunda_functions import get_customer_profile

	results = []

	try:
		with open(file_path, mode="r", newline="", encoding="utf-8") as csvfile:
			reader = csv.DictReader(csvfile)

			# Pre-fetch distributor
			distributor = Distributor.objects.get(code__contains=distributor_code.lstrip("0"))

			for row in reader:
				sales_order_number = row.get("Book No")
				if not sales_order_number:
					continue  # skip invalid rows

				so: SalesOrder = SalesOrder.objects.filter(sales_order=sales_order_number).first()

				read_details = False

				# Parse order & delivery datetimes safely
				order_date = parse_datetime(row.get("Book Date"), row.get("Book Time"))
				delivery_date = parse_datetime(row.get("Delivery Date"), row.get("Delivery Time"))

				# Consumer details
				relationship_id = (row.get("Consumer Id") or "").replace(".", "")

				if so is None:
					# Create CustomerProfile if missing
					cp_obj = get_customer_profile(
						relationship_id,
						row["Customer Name"],
						row.get("Address", ""),
						distributor.code
					)

					# Create new SalesOrder with all mapped fields
					so = SalesOrder.objects.create(
						parent=cp_obj,
						sales_order=row["Book No"],
						relationship_id=relationship_id,
						order_status="Completed",
						order_date=order_date,
						invoice_number=row.get("Cashmemo Number"),
						consumer_name=row.get("Customer Name"),
						consumer_address=row.get("Address"),
						mobile_number=row.get("Customer Mobile Number"),
						consumer_type=row.get("Category"),
						order_type="Sales Order",
						order_sub_type=row.get("Installation Booking"),
						delivery_date=delivery_date,
						channel=row.get("Mode of Booking"),
						order_total=float(row.get("Total") or 0.0),
						digital_payment=True if row.get('Delivery Mode') == 'Digital Payments' else False,
						delivery_confirm_full_name=row.get("Delivered By"),
						delivery_boy_full_name=row.get("Delivery Boy"),
						distributor_name=distributor.name,
						service_area=None,
						otp=row.get("Mode of Delivery")
					)
					read_details = True
				else:
					# Update if installation order OR missing delivery details
					if row.get("Installation Booking") == "Installation Order":
						read_details = True
					elif so.order_status == "Completed":
						if any(
								getattr(so, field) is None
								for field in ("delivery_date", "digital_payment",
											  "delivery_confirmed_by", "delivery_confirmation_type")
						):
							read_details = True
					else:
						read_details = True

				# Trigger Camunda if needed
				if read_details:
					variables = {
						"variables": {
							"sales_order_id": {"value": so.id, "type": "Long"},
							"sales_order_number": {"value": sales_order_number, "type": "String"},
							"order_status": {"value": so.order_status, "type": "String"},
							"distributor_code": {"value": distributor_code, "type": "String"},
						}
					}

					res, pid = start_process_in_camunda_v2(
						"process_fetch_sales_order_details_from_sdms", variables=variables
					)

					results.append(
						{
							"sales_order_id": so.id,
							"sales_order_number": sales_order_number,
							"status": res,
							"process_id": pid,
							"order_status": so.order_status,
							"distributor_code": distributor_code,
						}
					)

			return results

	except FileNotFoundError:
		print(f"❌ File not found: {file_path}")
	except Distributor.DoesNotExist:
		print(f"❌ Distributor not found for code: {distributor_code}")
	except Exception as e:
		print(f"❌ Error processing file {file_path}: {e}")