import datetime

import requests

from connection_app.camunda_functions import get_customer_profile, get_sdms_service_area

from domestic_app.settings import CAMUNDA_BASE_URL
from reference_data.models import Distributor
from ujjwala.camunda_functions import start_process_in_camunda_v2, is_process_exist_in_camunda


def can_do_post_inspection(user):
	return user.has_perm('connection_app.can_do_post_inspection')


def can_use_admin_tools(user):
	return user.has_perm('connection_app.can_use_admin_tools')


def get_delivery_boy_login(customer_profile_id):
	from connection_app.models import CustomerProfile
	from teams.models import SDMSServiceArea, UserProfile

	cp_obj = CustomerProfile.objects.get(id=customer_profile_id)
	userprofile_obj: UserProfile = cp_obj.sdms_service_area.userprofile_set.first()

	return userprofile_obj.sdmsuser_set.filter(distributor=cp_obj.distributor).first().delivery_boy_login


def upload_customer_register_csv(csv_file_rows):
	for idx, row in enumerate(csv_file_rows):
		try:
			print(idx + 1)
			relationship_id = row['Consumer ID'].replace(".", "")
			distributor: Distributor = Distributor.objects.get(code__contains=row['Distributor Code'])
			cp_obj = get_customer_profile(
				relationship_id, row['Consumer Name'], row['Address'], distributor.code
			)
			if not cp_obj.verified or cp_obj.distributor != distributor:
				cp_obj.relationship_status = row['Consumer Status']
				cp_obj.relationship_sub_status = row['Consumer Sub Status']
				cp_obj.distributor = distributor
				cp_obj.distributor_code = row['Distributor Code']
				cp_obj.distributor_name = distributor.name
				cp_obj.service_area = row['Area Name']
				cp_obj.sdms_service_area = get_sdms_service_area(row['Area Name'], distributor.code)
				cp_obj.verified = True
				cp_obj.verified_on = datetime.datetime.now()
				cp_obj.verification_source = 'manual_csv'
				if row['Phone Number'] and row['Phone Number'] != cp_obj.mobile_number:
					cp_obj.mobile_number = row['Phone Number']
				cp_obj.tube_change_date = datetime.datetime.strptime(row['Tube Change Date'], "%d-%m-%Y") if row['Tube Change Date'] else None
				cp_obj.tube_change_due_date = datetime.datetime.strptime(row['Tube Change Due Date'], "%d-%m-%Y") if row['Tube Change Due Date'] else None
				cp_obj.mandatory_inspection_due_date = datetime.datetime.strptime(row['Mandatory Inspection Date'], "%d-%m-%Y") if row['Mandatory Inspection Date'] else None
				if cp_obj.address != row['Address']:
					cp_obj.address = row['Address']
				cp_obj.last_refill_date = row['Last Refill Date']
				cp_obj.save()
			print(row)
		except Exception as e:
			print(e)
			continue
	return True


def upload_service_area_csv(csv_file_rows):
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
					"distributor_id": {"value": r['distributor_id'], "type": "String"}
				}
		}

		url = "{}/process-definition/key/{}/start".format(CAMUNDA_BASE_URL, PROCESS_DEFINITION_KEY)
		requests.post(url, json=variables)


def upload_delivery_register_csv(csv_file_rows):
	pass


def schedule_booking_cancellation_csv(csv_file_rows):
	for idx, row in enumerate(csv_file_rows):
		try:
			exist = is_process_exist_in_camunda('Process_book_sales_order', 'sales_order', row['sale_order'])
			if not exist:
				variables = {
					"variables": {
						"sale_order": {"value": row['sale_order'], "type": "String"},
						"distributor_code": {"value": row['distributor_code'], "type": "String"},
						"sdms_task": {"value": "cancel_booked_sales_order", "type": "String"},
					}
				}
				res, pid = start_process_in_camunda_v2('Process_book_sales_order', variables=variables)
				print(pid)
		except Exception as e:
			continue
	return True


def bulk_is_dirty_update(csv_file_rows):
	from connection_app.models import CustomerProfile
	from connection_app.jobs import start_read_customer_profile

	for idx, row in enumerate(csv_file_rows):
		try:
			consumer_id = row['consumer_id'].replace(";", "")
			cp_obj = CustomerProfile.objects.get(consumer_id=consumer_id)
			cp_obj.is_dirty = True
			cp_obj.save()
			start_read_customer_profile(cp_obj.pk)
		except Exception as e:
			continue
	return True


def update_distributor(csv_file_rows):
	from connection_app.models import CustomerProfile
	from connection_app.jobs import start_read_customer_profile

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
				cp_obj.save()

			cp_obj.is_dirty = True
			start_read_customer_profile(cp_obj.pk)
		except Exception as e:
			continue
	return True


def update_bulk_out(csv_file_rows):
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
