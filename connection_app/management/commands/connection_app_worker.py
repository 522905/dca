import json
import traceback

import requests
from camunda.external_task.external_task import ExternalTask, TaskResult
from camunda.external_task.external_task_worker import ExternalTaskWorker
from django.core.management import BaseCommand

from connection_app.camunda_functions import process_update_sales_order_in_dca, \
	update_sales_order_details_in_dca, process_update_sales_order_completed_today, update_customer_profile_in_dca, \
	update_booked_order_details_in_dca, update_service_area_in_customer_profile, update_returned_booked_order, \
	clean_sales_order_tasks, update_service_request_in_dca, update_distributor_status
from domestic_app import settings
from ujjwala.jobs import ensure_db_connection


EXTERNAL_TASK_TO_SUBSCRIBE = [
	'process_update_sales_order_in_dca#update',
	'process_fetch_sales_order_details_from_sdms#update_in_dca',
	'process_read_customer_profile_from_sdms#update_in_dca',
	'process_book_sales_order#update_booked_order_details_in_dca',
	'service_area_update#verify_update_service_area_in_sdms',
	'process_book_sales_order#update_returned_booked_order',
	'process_fetch_sales_order_details_from_sdms#cleanup_sales_order_tasks',
	'process_dca_service_request#update_service_request_in_dca',
	'process_dca_service_request#update_service_request_status_in_dca'
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
			sdms_task = task.get_variable('sdms_task')

			if sdms_task == 'fetch_sales_order':
				distributor_code = task.get_variable('distributor_code')
				sales_order_list = json.loads(task.get_variable('sales_order_list'))
				process_update_sales_order_in_dca(sales_order_list, distributor_code)
				return task.complete()
		elif topic == 'process_fetch_sales_order_details_from_sdms#update_in_dca':
			sales_order_details = json.loads(task.get_variable('sales_order_details'))
			sales_order_id = task.get_variable('sales_order_id')
			existing_order_status = task.get_variable('order_status')
			distributor_code = task.get_variable('distributor_code')
			importing = task.get_variable('importing')
			updated = update_sales_order_details_in_dca(sales_order_id, sales_order_details, existing_order_status,
			                                            importing, distributor_code)
			if not updated:
				return task.bpmn_error("sales order read error", "Could not read sales order details from SDMS")
			return task.complete()
		elif topic == 'process_read_customer_profile_from_sdms#update_in_dca':
			relationship_details = json.loads(task.get_variable('relationship_details'))
			customer_profile_id = task.get_variable('customer_profile_id')
			if relationship_details.get('distributor_status'):
				update_distributor_status(relationship_details.get('distributor_status'), customer_profile_id)
			else:
				update_customer_profile_in_dca(relationship_details, customer_profile_id)
			return task.complete()
		elif topic == 'process_book_sales_order#update_booked_order_details_in_dca':
			consumer_id = task.get_variable('consumer_id')
			sales_order_details = json.loads(task.get_variable('sales_order_details'))
			update_booked_order_details_in_dca(sales_order_details, consumer_id, task.get_process_instance_id())
			return task.complete()
		elif topic == 'service_area_update#verify_update_service_area_in_sdms':
			consumer_id = task.get_variable('consumer_id')
			service_area = task.get_variable('service_area')
			update_service_area_in_customer_profile(consumer_id, service_area)
			return task.complete()
		elif topic == 'process_book_sales_order#update_returned_booked_order':
			sales_order_id = task.get_variable('sales_order_id')
			status = task.get_variable('status')
			result_variables = update_returned_booked_order(sales_order_id, status)
			return task.complete(global_variables=result_variables)
		elif topic == 'process_fetch_sales_order_details_from_sdms#cleanup_sales_order_tasks':
			sales_order_id = task.get_variable('sales_order_id')
			importing = task.get_variable('importing')
			if not importing:
				clean_sales_order_tasks(sales_order_id, task.get_process_instance_id())
			return task.complete()
		elif topic == 'process_dca_service_request#update_service_request_status_in_dca':
			update_service_request_in_dca(task)
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
