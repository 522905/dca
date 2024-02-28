import json
import traceback

import requests
from camunda.external_task.external_task import ExternalTask, TaskResult
from camunda.external_task.external_task_worker import ExternalTaskWorker
from django.conf import settings
from django.core.management.base import BaseCommand

from ujjwala.camunda_worker_tasks import preinspection_update_in_dca, preinspection_create_legal_docs, \
	preinspection_add_lead_to_vicidial, preinspection_delete_lead_from_vicidial, preinspection_update_family_members, \
	review_address_add_lead_to_vicidial, review_address_delete_lead_from_vicidial, review_address_update_in_dca, \
	preinspection_update_review_address_accepted
from ujjwala.jobs import ensure_db_connection

EXTERNAL_TASK_TO_SUBSCRIBE = [
	"Process_preinspection#update_review_address_accepted",
	'Process_preinspection#update_in_dca',
	'Process_preinspection#create_legal_docs',
	'Process_preinspection#add_lead_in_vicidial',
	'Process_preinspection#delete_lead_from_vicidial',
	'Process_review_address#add_lead_in_vicidial',
	'Process_review_address#delete_lead_from_vicidial',
	'Process_review_address#update_in_dca'
]

default_config = {
	"maxTasks": 10,
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
		print(topic)
		if topic == "Process_preinspection#update_review_address_accepted":
			application_id = task.get_variable('application_id')
			review_address_completed_by = task.get_variable('review_address_completed_by')
			preinspection_update_review_address_accepted(application_id, review_address_completed_by)
			return task.complete()
		elif topic == "Process_preinspection#update_in_dca":
			preinspection_id = task.get_variable('preinspection_id')
			family_members = json.loads(task.get_variable('family_members'))
			preinspection_update_family_members(preinspection_id, family_members)
			action = task.get_variable('action')
			rejected_reasons = json.loads(task.get_variable('rejected_reasons')) if task.get_variable('rejected_reasons') else []
			preinspection_update_in_dca(preinspection_id, action, rejected_reasons)
			return task.complete()
		elif topic == 'Process_preinspection#create_legal_docs':
			preinspection_id = task.get_variable('preinspection_id')
			action = task.get_variable('action')
			if action == 'PREINSPECTION_ACCEPT':
				preinspection_create_legal_docs(preinspection_id)
			return task.complete()
		# elif topic == 'Process_preinspection#delete_lead_from_vicidial':
		# 	preinspection_id = task.get_variable('preinspection_id')
		# 	contact_mobile = task.get_variable('contact_mobile')
		# 	preinspection_delete_lead_from_vicidial(preinspection_id, contact_mobile)
		# 	return task.complete()
		elif topic in ['Process_review_address#add_lead_in_vicidial', 'Process_preinspection#add_lead_in_vicidial']:
			contact_mobile = task.get_variable('contact_mobile')
			if not contact_mobile:
				contact_mobile = task.get_variable('mobile')
			name = task.get_variable('name')
			application_id = task.get_variable('application_id')
			process_instance_id = task.get_process_instance_id()
			list_id = 1201
			res = review_address_add_lead_to_vicidial(list_id, contact_mobile, name, application_id, process_instance_id)

			if not "success" in res.lower():
				raise Exception("res")

			return task.complete(global_variables={
				'camunda_address_updated': {"type": "Boolean", "value": False}
			})
		elif topic in ['Process_review_address#delete_lead_from_vicidial', 'Process_preinspection#delete_lead_from_vicidial']:
			list_id = 1201
			contact_mobile = task.get_variable('contact_mobile')
			if not contact_mobile:
				contact_mobile = task.get_variable('mobile')
			review_address_delete_lead_from_vicidial(list_id, contact_mobile)
			return task.complete()
		elif topic == 'Process_review_address#update_in_dca':
			application_id = task.get_variable('application_id')
			address_json = json.loads(task.get_variable('address_json'))
			agent = task.get_variable('agent')
			review_address_update_in_dca(application_id, address_json, agent)
			return task.complete()
	except Exception as e:
		print(e)
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
