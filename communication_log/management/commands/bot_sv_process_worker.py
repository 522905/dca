import datetime
import json
import re
import traceback
import json
import requests
from camunda.external_task.external_task import ExternalTask, TaskResult
from camunda.external_task.external_task_worker import ExternalTaskWorker
from django.conf import settings
from django.core.management.base import BaseCommand

from communication_log.error_stats import error_mapping
from communication_log.jobs import dialogflow_whatapp_message
from ujjwala.camunda_functions import download_file_variable_data, calculate_download_sv_wait_timing, \
	start_ujjwala_cld_dedup_in_camunda, fetch_payment_profile_variables, get_activity_instance_count, \
	enrich_omc_rejection_details, remove_sv_record, start_ujjwala_legal_docs_upload_in_camunda
from ujjwala.camunda_worker_tasks import variables_to_update_for_preinspection, get_consumer_id_for_iocl_investigation
from ujjwala.enums import UjjwalaV2ApplicationStatus, RoboSdmsDedeupStatusEnum
from ujjwala.jobs import ensure_db_connection, do_primary_omc_dedupe_check, move_application_for_audit, \
	compress_application_documents
from ujjwala.sv_functions import update_sv_document, update_in_dca, update_sv_document_v2
from ujjwala.ujjwala_functions import send_pos_list_for_ekyc
from utils.qrcode import get_sv_date_and_doc_no

EXTERNAL_TASK_TO_SUBSCRIBE = [
	'Chatbot#SendSubsidyDetails',
]

default_config = {
	"maxTasks": 1,
	"lockDuration": 10 * 60 * 1000,  # 60 Sec
	"asyncResponseTimeout": 20 * 1000,  # 20 Sec
	"retries": 3,
	"retryTimeout": 1000,
	"sleepSeconds": 3,
	"deserializeValues": False,
}

_existing_relation_regex = re.compile(
	'Aadhaar already exists for customer (?P<consumer_name>.*?)\((?P<consumer_id>.*?)\) of (?P<dist_name>.*?)\((?P<dict_code>.*?)-.*'
)


def task_process_sv(task: ExternalTask) -> TaskResult:
	result = {}
	return task.complete(global_variables=result)


def upload_sv_to_dca(task: ExternalTask) -> TaskResult:
	result = {}
	return task.complete(global_variables=result)


def custom_decoder(obj):
	if 'Created On' in obj:
		obj['Created On'] = datetime.datetime.strptime(obj['Created On'], "%d-%b-%Y %I:%M:%S %p")
	return obj


#
# @ensure_db_connection
# def handle_task(task: ExternalTask) -> TaskResult:
# 	try:
# 		topic = task.get_topic_name()
# 		if topic == 'Chatbot#SendSubsidyDetails':
# 			consumer_id = task.get_variable('consumer_id')
# 			distributor_code = task.get_variable('distributor_code')
# 			SDMS_Beneficiary_json = task.get_variable('SDMS_Beneficiary_Details')
# 			consumer_contact = task.get_variable('consumer_contact')
# 			bank_transactions_json = task.get_variable('bank_transactions')
# 			subsidy_details_json = task.get_variable('subsidy_details')
#
# 			if not subsidy_details_json and not consumer_contact:
# 				return task.failure("Missing required fields in the request data.", )
#
# 			subsidy_details = json.loads(subsidy_details_json, object_hook=custom_decoder)[0]
# 			bank_transactions = json.loads(bank_transactions_json, object_hook=custom_decoder)[0]
# 			sdms_beneficiary = json.loads(SDMS_Beneficiary_json, object_hook=custom_decoder)[0]
#
# 			if sdms_beneficiary['Error Code'] is not None and sdms_beneficiary['profile status'] == 'rejected':
# 				error_code = sdms_beneficiary['Error Code']
# 				if error_mapping.get(error_code):
# 					error_message = f"आपकी subsidy बजने में यह  bank सम्बंदिति सामिया आ रही हा। \n {error_mapping.get(error_code)}।"
# 					dialogflow_whatapp_message(error_message, consumer_contact)
# 					return task.complete()
#
# 			print(subsidy_details, bank_transactions)
# 			if subsidy_details['Subsidy Status'] == "start":
# 				bank_no = subsidy_details['Bank Account Number']
# 				susidy_amount = subsidy_details['Subsidy Amount']
# 				Bank_transection = bank_transactions['Bank DOS']
# 				bank_name = bank_transactions['Bank Name']
# 				if subsidy_details['Status'] != 'Settled':
# 					response_message = f"your subsidy amount {susidy_amount} will be  credited to your bank account end with {bank_no}  soon. \n"
# 				else:
# 					response_message = f"your subsidy amount {susidy_amount} has been credited to your \n" \
# 									   f"{bank_name} bank account end with {bank_no} on date {Bank_transection}. \n"
#
# 				dialogflow_whatapp_message(response_message, consumer_contact)
# 				return task.complete()
# 	except Exception as e:
# 		return task.failure(
# 			str(e), traceback.format_exc(),
# 			max_retries=0, retry_timeout=0
# 		)


@ensure_db_connection
def handle_task(task: ExternalTask) -> TaskResult:
	"""
	Handles incoming external tasks based on the topic name.
	"""
	try:
		# Retrieve topic name
		topic = task.get_topic_name()
		if topic == 'Chatbot#SendSubsidyDetails':
			# Retrieve required variables
			sdms_beneficiary_json = task.get_variable('sdms_beneficiary')
			consumer_contact = task.get_variable('consumer_contact')
			bank_transactions_json = task.get_variable('bank_transactions')
			subsidy_details_json = task.get_variable('subsidy_details')

			# Check for missing critical fields
			required_fields = {
				"consumer_contact": consumer_contact,
				"subsidy_details_json": subsidy_details_json,
				"SDMS_Beneficiary_Details": sdms_beneficiary_json,
				"bank_transactions_json": bank_transactions_json
			}
			missing_fields = [key for key, value in required_fields.items() if not value]
			if missing_fields:
				dialogflow_whatapp_message(f"{sdms_beneficiary_json}", consumer_contact,"")
				return task.failure(f"Missing required fields: {', '.join(missing_fields)}", "", max_retries=0, retry_timeout=0 )

			# Parse JSON fields with error handling
			try:
				subsidy_details = json.loads(subsidy_details_json, object_hook=custom_decoder)[0]
				bank_transactions = json.loads(bank_transactions_json, object_hook=custom_decoder)[0]
				sdms_beneficiary = json.loads(sdms_beneficiary_json, object_hook=custom_decoder)[0]
			except json.JSONDecodeError as json_error:
				return task.failure("Invalid JSON format: {}".format(json_error),"", max_retries=0, retry_timeout=0 )

			# Handle rejected beneficiary profile
			if sdms_beneficiary.get('Error Code') and sdms_beneficiary.get('Bank Profile') == 'RJCT':
				error_code = sdms_beneficiary['Error Code']
				error_message = error_mapping.get(error_code)
				if not error_message:
					return task.failure(f"Unknown Error Code: {error_code}","", max_retries=0, retry_timeout=0 )

				translated_message = (
					f"आपकी subsidy बजने में यह bank सम्बंदिति समस्या आ रही है:\n{error_message}।"
				)
				dialogflow_whatapp_message(translated_message, consumer_contact,"")
				return task.complete()


			# Process subsidy details
			subsidy_status = subsidy_details.get('Subsidy Status')
			if subsidy_status == "Start":
				process_subsidy_details(subsidy_details, bank_transactions, consumer_contact)
				return task.complete()

			return task.failure("Unsupported Subsidy Status: {}".format(subsidy_status),""
								,max_retries=0, retry_timeout=0)

	except Exception as e:
		return task.failure(
			str(e), traceback.format_exc(),
			max_retries=0, retry_timeout=0
		)


def process_subsidy_details(subsidy_details: dict, bank_transactions: dict, contact: str):
	"""
	Processes and sends messages related to subsidy details.
	"""
	try:
		# Extract required details
		bank_account_number = subsidy_details.get('Bank Account Number', 'XXXX')
		subsidy_amount = subsidy_details.get('Subsidy Amount', 'N/A')
		subsidy_status = subsidy_details.get('Status', '')
		bank_transaction_date = bank_transactions.get('Bank DOS', '')
		bank_name = bank_transactions.get('Bank Name', 'Unknown Bank')

		# Create response message
		if subsidy_status != 'Settled':
			response_message = (
				f"Your subsidy amount {subsidy_amount} will be credited to your bank account ending with {bank_account_number} soon."
			)
		else:
			response_message = (
				f"Your subsidy amount {subsidy_amount} has been credited to your {bank_name} bank account "
				f"ending with {bank_account_number} on {bank_transaction_date}."
			)

		# Send the message
		dialogflow_whatapp_message(response_message, contact,"")

	except Exception as e:
		# Handle any unexpected issues in message processing
		return TaskResult.failure(
			"Error while processing subsidy details: {}".format(e), traceback.format_exc()
			, retry_timeout=0 ,
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
