import requests
from camunda.external_task.external_task import ExternalTask

from service_request.enums import ServiceRequestTypeEnum
from service_request.models import ServiceRequest
from ujjwala.camunda_functions import start_process_in_camunda


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


def update_service_request_in_dca(service_request_id, task: ExternalTask):
	sr_obj = ServiceRequest.objects.get(pk=service_request_id)

	application_id = task.get_variable('application_id')

	if sr_obj.service_request_type == ServiceRequestTypeEnum.CHANGE_PHONE_NUMBER:
		phone_number = task.get_variable('phone_number')
		service_request_id = task.get_variable('service_request_id')
		res = requests.post(
			f"https://dca.arungas.com/ujjwala/ujjwala-bot/{application_id}/update_ujjwala_application_mobile_number/",
			json={
				"phone_number": phone_number,
				"service_request_id": service_request_id,
			}
		)
		res.raise_for_status()
	elif sr_obj.service_request_type == ServiceRequestTypeEnum.UPDATE_ADDRESS:
		pass
