import json
import traceback

import requests
from camunda.external_task.external_task import ExternalTask, TaskResult
from camunda.external_task.external_task_worker import ExternalTaskWorker
from django.conf import settings
from django.core.management.base import BaseCommand

from ujjwala.camunda_functions import get_review_address_activity_user, \
	get_review_other_details_and_preinspection_activity_user
from ujjwala.camunda_worker_tasks import preinspection_update_in_dca, preinspection_create_legal_docs, \
	preinspection_update_family_members, \
	review_address_add_lead_to_vicidial, review_address_delete_lead_from_vicidial, review_address_update_in_dca, \
	preinspection_update_review_address_accepted, review_address_update_in_dca_other_action, \
	preinspection_evaluate_pre_inspection_data, preinspection_update_other_details_action, \
	payment_profile_update_add_lead_to_vicidial, payment_profile_update_delete_lead_and_update_dca, \
	payment_profile_update_sdms_status_in_dca, send_payment_profile_update_whatsapp_message
from ujjwala.jobs import ensure_db_connection

EXTERNAL_TASK_TO_SUBSCRIBE = [
	"Process_preinspection#evaluate_pre_inspection_data",
	"Process_preinspection#update_review_address_accepted",
	'Process_preinspection#update_in_dca',
	'Process_preinspection#create_legal_docs',
	'Process_preinspection#add_lead_in_vicidial',
	'Process_preinspection#delete_lead_from_vicidial',
	'Process_review_address#add_lead_in_vicidial',
	'Process_review_address#delete_lead_from_vicidial',
	# 'Process_review_address#update_in_dca',
	# Payment Profile Update
	'payment_profile_update_batch_in_dca',
	'Process_payment_profile_update_in_sdms#update_in_dca',
	'Process_payment_profile_update#add_lead_and_send_whatsapp',
	'Process_payment_profile_update#delete_lead_and_update_in_dca',
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
		print(topic, " - ", task.get_process_instance_id(),
		      f"https://camunda.dca.arungas.com/camunda/app/cockpit/default/#/process-instance/{task.get_process_instance_id()}")
		if topic == "Process_preinspection#evaluate_pre_inspection_data":
			preinspection_id = task.get_variable('preinspection_id')
			results = preinspection_evaluate_pre_inspection_data(preinspection_id)
			return task.complete(global_variables=results)
		elif topic == "Process_preinspection#update_review_address_accepted":
			application_id = task.get_variable('application_id')
			review_address_completed_by_user = get_review_address_activity_user(task.get_process_instance_id())

			if not review_address_completed_by_user.get('user'):
				review_address_completed_by = task.get_variable('review_address_completed_by')
			else:
				review_address_completed_by = review_address_completed_by_user.get('user')

			preinspection_update_review_address_accepted(application_id, review_address_completed_by)

			other_details_action = task.get_variable('other_details_action')

			if not other_details_action:
				return task.complete(global_variables={
					"other_details_status": {"value": 'NOT_MATCHED', "type": "String"}
				})
			return task.complete()
		elif topic == "Process_preinspection#update_in_dca":
			preinspection_id = task.get_variable('preinspection_id')
			review_address_completed_by = task.get_variable('review_address_completed_by')
			review_variables = get_review_other_details_and_preinspection_activity_user(task.get_process_instance_id())
			# Updating Other Details Review
			# If user did Review Other Details
			# In Case Action is pre-inspection reject in review address
			# This User task bypassed hence no need to update
			other_details_action = task.get_variable('other_details_action')
			if other_details_action:
				family_members = json.loads(task.get_variable('family_members'))
				remarks = task.get_variable('remarks')

				review_other_details_completed_by = review_variables.get('review_other_details_completed_by')
				preinspection_update_family_members(preinspection_id, family_members)
				preinspection_update_other_details_action(review_other_details_completed_by, preinspection_id,
			                                          other_details_action, remarks)

			# Updating PreInspection Review
			action = task.get_variable('action')

			if not review_address_completed_by:
				review_address_completed_by_user = get_review_address_activity_user(task.get_process_instance_id())
				review_variables['review_address_completed_by'] = review_address_completed_by_user.get('user')
			else:
				review_variables['review_address_completed_by'] = review_address_completed_by

			rejected_reasons = json.loads(task.get_variable('rejected_reasons')) if task.get_variable('rejected_reasons') else []
			preinspection_update_in_dca(review_variables, preinspection_id, action, rejected_reasons)
			return task.complete()
		elif topic == 'Process_preinspection#create_legal_docs':
			preinspection_id = task.get_variable('preinspection_id')
			action = task.get_variable('action')

			if action in ['OUT_OF_SERVICE_AREA', 'PREINSPECTION_REJECT']:
				return task.complete()
			else:
				rejected_reasons = task.get_variable('rejected_reasons')

				if rejected_reasons:
					rejected_reasons = json.loads(task.get_variable('rejected_reasons', []))

				if not rejected_reasons:
					preinspection_create_legal_docs(preinspection_id)
				return task.complete()
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
			action = task.get_variable('action')

			if action == 'ADDRESS_ACCEPT':
				review_address_update_in_dca(application_id, address_json, agent)
			elif action == 'ADDRESS_REJECT':
				raise Exception("Fix Transition")
			else:
				review_address_update_in_dca_other_action(application_id, action, agent)

			return task.complete()
		elif topic == 'payment_profile_update_batch_in_dca':
			from connection_app.models import PaymentProfile
			import datetime

			data = json.loads(task.get_variable("data")).get('data')

			skipped_rows = []
			for payment_profile in data:
				if PaymentProfile.objects.filter(case_num=payment_profile.get('Case Num')).exists():
						skipped_rows.append(payment_profile)
				else:
					PaymentProfile.objects.create(
						case_num=payment_profile.get('Case Num'),
						closed_data=datetime.datetime.strptime(payment_profile.get("Closed Date"),
						                                       "%d-%b-%Y %I:%M:%S %p") if payment_profile.get(
							"Closed Date") else None,
						created_date=datetime.datetime.strptime(payment_profile.get("Created Date"),
						                                        "%d-%b-%Y %I:%M:%S %p"),
						name_as_per_bank=payment_profile.get("Name As Per Bank"),
						name_as_on_relationship=payment_profile.get("Name As On Relationship"),
						name_as_per_bank_response=payment_profile.get("Name As Per Bank Response"),
						name_match=True if payment_profile.get("Name Match") == 'Y' else False,
						distributor_code=payment_profile.get("Distributor Code"),
						distributor_name=payment_profile.get("Distributor Name"),
						comments=payment_profile.get("Comments"),
						relationship_id=payment_profile.get("Relationship Id"),
						payment_profile_id=payment_profile.get("Payment Profile Id"),
						account_id=payment_profile.get("Account Id"),
						status=payment_profile.get("Status"),
						contact_id=payment_profile.get("Contact Id"),
						profile_type=payment_profile.get("Type"),
						pfms_payment_method=payment_profile.get("PFMS Payment Method"))

			print(skipped_rows)
			return task.complete()
		elif topic == 'Process_payment_profile_update_in_sdms#update_in_dca':
			case_num = task.get_variable('case_num')
			print(task.get_variable('action'))
			result = payment_profile_update_sdms_status_in_dca(case_num)
			return task.complete(global_variables=result)
		elif topic == 'Process_payment_profile_update#add_lead_and_send_whatsapp':
			contact_mobile = task.get_variable('contact_mobile')
			name = task.get_variable('name')
			application_id = task.get_variable('application_id')
			process_instance_id = task.get_process_instance_id()

			send_payment_profile_update_whatsapp_message(application_id, contact_mobile, process_instance_id)
			list_id = 1202
			res = payment_profile_update_add_lead_to_vicidial(list_id, contact_mobile, name, application_id,
			                                          process_instance_id)

			if not "success" in res.lower():
				raise Exception("res")

			return task.complete()
		elif topic == 'Process_payment_profile_update#delete_lead_and_update_in_dca':
			list_id = 1202
			contact_mobile = task.get_variable('contact_mobile')
			application_id = task.get_variable('application_id')
			variables = payment_profile_update_delete_lead_and_update_dca(list_id, contact_mobile, application_id)
			return task.complete(global_variables=variables)
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
