import traceback

import requests
from camunda.external_task.external_task import ExternalTask, TaskResult
from camunda.external_task.external_task_worker import ExternalTaskWorker
from django.conf import settings
from django.core.management.base import BaseCommand

from ujjwala.camunda_functions import download_file_variable_data, calculate_download_sv_wait_timing
from ujjwala.sv_functions import update_sv_document, update_in_dca

EXTERNAL_TASK_TO_SUBSCRIBE = [
	'calculate_wait_time',
	'process_sv',
	'upload_sv_to_dca',
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
		if topic == "calculate_wait_time":
			download_sv_retry_count = task.get_variable('download_sv_retry_count')
			download_sv_retry_count = download_sv_retry_count + 1 if download_sv_retry_count else 1
			sv_wait_timing = calculate_download_sv_wait_timing(download_sv_retry_count)
			result = {
				"sv_generation_wait_timer": {"value": sv_wait_timing, "type": "duration"},
			}
			return task.complete(global_variables=result)
		elif topic == "process_sv":
			connection_disbursement_id = task.get_variable('connection_disbursement_id')
			booking_id = task.get_variable('booking_id')
			sv_file_content = download_file_variable_data(task.get_process_instance_id(), 'sv_file')
			sv_file_link = update_sv_document(connection_disbursement_id, booking_id, sv_file_content)
			result = {
				"sv_file_link": {"value": sv_file_link, "type": "string"},
			}
			return task.complete(global_variables=result)
		elif topic == "upload_sv_to_dca":
			connection_disbursement_id = task.get_variable('connection_disbursement_id')
			booking_id = task.get_variable('booking_id')
			sv_file_link = task.get_variable('sv_file_link')
			update_in_dca(connection_disbursement_id, booking_id, sv_file_link)
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
