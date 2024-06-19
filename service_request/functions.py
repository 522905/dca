import datetime

import requests
from camunda.external_task.external_task import ExternalTask

from service_request.enums import ServiceRequestTypeEnum, ServiceRequestTypeStatusEnum
from service_request.models import ServiceRequest
from ujjwala.camunda_functions import start_process_in_camunda
from ujjwala.models import UjjwalaV2Application


def start_service_request_process_in_camunda(service_request_id, variables):
	sr_obj = ServiceRequest.objects.get(pk=service_request_id)

	# result, msg = start_process_in_camunda(
	# 	"process_dca_change_phone_number",
	# 	{
	# 		"variables": {
	# 			"request_video_url": {"value": data['request_video_url'], "type": "string"},
	# 			"phone_number": {"value": data['phone_number'], "type": "string"},
	# 			"application_id": {"value": obj.id, "type": "long"},
	# 			"name": {"value": obj.name, "type": "string"},
	# 			"status": {"value": obj.status, "type": "string"},
	# 			"old_phone_numbers": {"value": json.dumps(obj.all_contacts), "type": "string"},
	# 			"request_by": {"value": f"{user.first_name} {user.last_name}"},
	# 			"service_request_id": {"value": service_request.id, "type": "long"},
	# 		}
	# 	}
	# )
		# if sr_obj.service_request_type == ServiceRequestTypeEnum.CHANGE_PHONE_NUMBER:
			# result, msg = start_process_in_camunda("process_dca_change_phone_number", {"variables": variables})
	result, msg = start_process_in_camunda("process_dca_service_request", {"variables": variables})
	sr_obj.camunda_process_id = msg
	sr_obj.save()


def update_service_request_in_dca(task: ExternalTask):
	request_type = task.get_variable('request_type')
	service_request_id = task.get_variable('service_request_id')
	application_id = task.get_variable('application_id')
	action = task.get_variable('action')

	sr_obj = ServiceRequest.objects.get(pk=service_request_id)

	if action == 'ACCEPT':
		if request_type == ServiceRequestTypeEnum.CHANGE_PHONE_NUMBER:
			phone_number = task.get_variable('phone_number')
			if task.get_variable('dca_app') == 'ujjwala':
				application = UjjwalaV2Application.objects.get(pk=application_id)
				application.contact_mobile = phone_number
				application.save()
		elif request_type == ServiceRequestTypeEnum.UPDATE_ADDRESS:
			new_address = task.get_variable('new_address')
			if task.get_variable('dca_app') == 'ujjwala':
				application = UjjwalaV2Application.objects.get(pk=application_id)
				application.address_json = new_address
				application.address_verified = True
				application.address_verified_by = sr_obj.reviewed_by
				application.address_verified_on = sr_obj.reviewed_on
				application.address_updated = True
				application.address_updated_on = datetime.datetime.now()
				application.save()

		sr_obj.status = ServiceRequestTypeStatusEnum.COMPLETED
		sr_obj.sdms_ticket_number = task.get_variable('sdms_ticket_number')
		sr_obj.save()

	else:
		sr_obj.status = ServiceRequestTypeStatusEnum.REJECTED
		sr_obj.save()


	# res = requests.post(
	# 	# f"https://dca.arungas.com/ujjwala/ujjwala-bot/{application_id}/update_ujjwala_service_request/",
	# 	f"http://192.168.168.4:60613/ujjwala/ujjwala-bot/{application_id}/update_ujjwala_service_request/",
	# 	json=data
	# )
	# res.raise_for_status()
