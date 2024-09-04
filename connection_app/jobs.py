import csv

from connection_app.enums import TemplateEnum, ImportDataStatusEnum
from ujjwala.camunda_functions import start_process_in_camunda_v2


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


def schedule_upload_data(template, id_obj):
	from connection_app.functions import upload_customer_register_csv, upload_service_area_csv

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

		if template == TemplateEnum.SERVICE_AREA:
			upload_service_area_csv(data_rows)
		elif template == TemplateEnum.CUSTOMER_REGISTER:
			upload_customer_register_csv(data_rows)
		elif template == TemplateEnum.DELIVERY_REGISTER:
			pass

		id_obj.status = ImportDataStatusEnum.COMPLETED
		id_obj.save()
	except Exception as e:
		id_obj.error_log = str(e)
		id_obj.status = ImportDataStatusEnum.FAILED
		id_obj.save()
