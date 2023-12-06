import datetime
import json
import traceback

import requests
from camunda.external_task.external_task import ExternalTask, TaskResult
from camunda.external_task.external_task_worker import ExternalTaskWorker
from django.conf import settings
from django.core.management.base import BaseCommand

from ujjwala.camunda_functions import download_file_variable_data, calculate_download_sv_wait_timing, \
	start_ujjwala_cld_dedup_in_camunda
from ujjwala.sv_functions import update_sv_document, update_in_dca

EXTERNAL_TASK_TO_SUBSCRIBE = [
	'calculate_wait_time',
	'update_in_dca',
	'customer_status_update',
	'CLDP_DEDUP_evaluate_and_update_dedup_results'
	# 'process_sv',
	# 'upload_sv_to_dca',
]

default_config = {
	"maxTasks": 1,
	"lockDuration": 10 * 60 * 1000,  # 60 Sec
	"asyncResponseTimeout": 20 * 1000,  # 20 Sec
	"retries": 3,
	"retryTimeout": 1000,
	"sleepSeconds": 3
}


def task_process_sv(task: ExternalTask) -> TaskResult:
	result = {}
	return task.complete(global_variables=result)


def upload_sv_to_dca(task: ExternalTask) -> TaskResult:
	result = {}
	return task.complete(global_variables=result)


def handle_task(task: ExternalTask) -> TaskResult:
	try:
		topic = task.get_topic_name()
		if topic == "ujjwala_sv_generation#calculate_wait_time":
			download_sv_retry_count = task.get_variable('download_sv_retry_count') or 0
			task_start_time = task.get_variable('task_start_time') or datetime.datetime.now()

			download_sv_retry_count = download_sv_retry_count + 1
			sv_new_wait_timing = calculate_download_sv_wait_timing(download_sv_retry_count, task_start_time)
			result = {
				"task_start_time": {"value": task_start_time.strftime('%Y-%m-%d %H:%M:%S'), "type": "string"},
				"sv_generation_check_date": {"value": sv_new_wait_timing.strftime('%Y-%m-%dT%H:%M:%S+0530'), "type": "string"},
				"download_sv_retry_count": {"value": download_sv_retry_count, "type": "string"}
			}
			return task.complete(global_variables=result)
		elif topic == "ujjwala_sv_generation#process_sv":
			connection_disbursement_id = task.get_variable('connection_disbursement_id')
			booking_id = task.get_variable('booking_id')
			sv_file_content = download_file_variable_data(task.get_process_instance_id(), 'sv_file')
			sv_file_link = update_sv_document(connection_disbursement_id, booking_id, sv_file_content)
			result = {
				"sv_file_link": {"value": sv_file_link, "type": "string"},
			}
			return task.complete(global_variables=result)
		elif topic == "ujjwala_sv_generation#upload_sv_to_dca":
			connection_disbursement_id = task.get_variable('connection_disbursement_id')
			consumer_id = task.get_variable('consumer_id')
			booking_id = task.get_variable('booking_id')
			sv_file_link = task.get_variable('sv_file_link')
			update_in_dca(connection_disbursement_id, booking_id, sv_file_link, consumer_id)
			return task.complete()
		elif topic == 'update_in_dca':
			dca_id = task.get_variable('dca_id')
			consumer_id = task.get_variable('consumer_id')
			uid_check_result = task.get_variable('uid_check_result')
			req = requests.post(
				'https://dca.arungas.com/ujjwala/ujjwala-bot-sdms-relationship/update_new_relationship/',
				json={
					'id': dca_id,
					'consumer_id': consumer_id,
					'uid_check_result': json.loads(uid_check_result)
				}
			)
			req.raise_for_status()
			return task.complete()
		elif topic == 'customer_status_update':
			consumer_id = task.get_variable('consumer_id')
			application_id = task.get_variable('application_id')
			message = task.get_variable('message')
			status = task.get_variable('status')
			req = requests.post(
				f'https://dca.arungas.com/ujjwala/ujjwala-bot/{application_id}/update_legal_doc_status/',
				json={
					'message': message,
					'status': status,
				}
			)
			req.raise_for_status()
			res = start_ujjwala_cld_dedup_in_camunda(consumer_id, application_id)
			return task.complete()
		elif topic == 'CLDP_DEDUP_evaluate_and_update_dedup_results':
			application_id = task.get_variable('id')
			nic_status = task.get_variable('nic_status')
			omc_status = task.get_variable('omc_status')
			ekyc_flag = task.get_variable('ekyc_flag')
			contact_number = task.get_variable('contact_number')
			product = task.get_variable('product')
			legal_docs_uploaded = task.get_variable('legal_docs_uploaded')

			cleared = ("Approved" in nic_status or "Clear" in nic_status) and "Clear" in omc_status
			reject = 'reject' in nic_status.lower() or 'reject' in omc_status.lower()

			if not reject and not cleared:
				dedup_retry_date = datetime.datetime.now() + datetime.timedelta(seconds=150)
				return task.bpmn_error('DEDUP_NOT_CLEAR', f'NIC: {nic_status}, OMC: {omc_status}', variables={
					'dedup_retry_date': {"value": dedup_retry_date.strftime('%Y-%m-%dT%H:%M:%S+0530'), "type": "string"},
				})

			req = requests.post(
				f'https://dca.arungas.com/ujjwala/ujjwala-bot/{application_id}/update_omc_and_nic_status/',
				json={
					'nic_status': nic_status,
					'omc_status': omc_status,
					'ekyc_flag': ekyc_flag,
					'product': product,
					'contact_number': contact_number,
					'legal_docs_uploaded': legal_docs_uploaded,
				}
			)
			req.raise_for_status()
			return task.complete()
	except Exception as e:
		return task.failure(
			"Unhandled Exception", traceback.format_exc(),
			max_retries=0, retry_timeout=0
		)


class Command(BaseCommand):
	def add_arguments(self, parser):
		# Positional arguments
		parser.add_argument('worker_id', type=str)

	def handle(self, *args, **options):
		base_url = settings.CAMUNDA_BASE_URL
		worker_id = options['worker_id']

		locked_task_list = requests.get(f"{base_url}/external-task", params={
			"workerId": worker_id
		}).json()

		print(locked_task_list)

		for locked_task in locked_task_list:
			requests.post(f"{base_url}/external-task/{locked_task['id']}/unlock")

		subscription_list = list(EXTERNAL_TASK_TO_SUBSCRIBE)
		ExternalTaskWorker(base_url=base_url, worker_id=worker_id, config=default_config). \
			subscribe(subscription_list, handle_task)
