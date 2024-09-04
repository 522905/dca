import datetime

import requests

from connection_app.camunda_functions import get_customer_profile, get_sdms_service_area
from domestic_app.settings import CAMUNDA_BASE_URL
from reference_data.models import Distributor


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
			cp_obj.save()
		print(row)
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

