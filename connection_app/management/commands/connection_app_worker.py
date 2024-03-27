import traceback

import requests
from camunda.external_task.external_task import ExternalTask, TaskResult
from camunda.external_task.external_task_worker import ExternalTaskWorker
from django.core.management import BaseCommand

from connection_app.camunda_functions import process_update_sales_order_in_dca, \
	process_update_sales_order_invoice_in_dca
from domestic_app import settings
from ujjwala.jobs import ensure_db_connection


EXTERNAL_TASK_TO_SUBSCRIBE = [
	'process_update_sales_order_in_dca#update',
]

default_config = {
	"maxTasks": 1,
	"lockDuration": 10 * 60 * 1000,  # 60 Sec
	"asyncResponseTimeout": 20 * 1000,  # 20 Sec
	"retries": 3,
	"retryTimeout": 1000,
	"sleepSeconds": 3
}


@ensure_db_connection
def handle_task(task: ExternalTask) -> TaskResult:
	try:
		topic = task.get_topic_name()

		print(topic, " - ", task.get_process_instance_id(),
			f"https://camunda.dca.arungas.com/camunda/app/cockpit/default/#/process-instance/{task.get_process_instance_id()}"
		)

		if topic == 'process_update_sales_order_in_dca#update':
			sales_order_type = task.get_variable('sales_order_type')

			if sales_order_type == 'sales_order_invoice':
				process_update_sales_order_invoice_in_dca(task)
				return task.complete()
			elif sales_order_type == 'sales_order':
				process_update_sales_order_in_dca(task)
				return task.complete()

	except Exception as e:
		return task.failure(
			str(e), traceback.format_exc(),
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
