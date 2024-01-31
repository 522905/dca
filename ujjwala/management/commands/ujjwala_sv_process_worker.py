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

from ujjwala.camunda_functions import download_file_variable_data, calculate_download_sv_wait_timing, \
	start_ujjwala_cld_dedup_in_camunda, fetch_payment_profile_variables, get_activity_instance_count, \
	enrich_omc_rejection_details
from ujjwala.enums import UjjwalaV2ApplicationStatus
from ujjwala.jobs import ensure_db_connection
from ujjwala.sv_functions import update_sv_document, update_in_dca, update_sv_document_v2
from ujjwala.ujjwala_functions import send_pos_list_for_ekyc
from utils.qrcode import get_sv_date_and_doc_no

EXTERNAL_TASK_TO_SUBSCRIBE = [
	'ujjwala_sv_generation#calculate_wait_time',
	'process_ekyc#update_in_dca',
	'ujjwala_legal_docs_update#customer_status_update',
	'CLDP_DEDUP_evaluate_and_update_dedup_results',
	'ujjwala_legal_docs_update#fetch_payment_profile_variables',
	'process_ekyc#process_existing_relationship',
	'dca_change_phone_number#update_changed_number_in_dca',
	'ujjwala_sv_generation#process_sv',
	'ujjwala_sv_generation#upload_sv_to_dca',
	'process_get_ekyc_status_from_sdms#update_consumer_ekyc_status_in_dca',
	'process_ekyc#enrich_omc_rejection',
	'ujjwala_legal_docs_update#enrich_omc_rejection',
	'iocl_investigation#extract_data_for_iocl_investigation',
]

default_config = {
	"maxTasks": 1,
	"lockDuration": 10 * 60 * 1000,  # 60 Sec
	"asyncResponseTimeout": 20 * 1000,  # 20 Sec
	"retries": 3,
	"retryTimeout": 1000,
	"sleepSeconds": 3
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


@ensure_db_connection
def handle_task(task: ExternalTask) -> TaskResult:
	try:
		topic = task.get_topic_name()
		if topic == "ujjwala_sv_generation#calculate_wait_time":
			# try:
			if 'Error' in (task.get_variable('status', '') or ''):
				return task.bpmn_error("download_sv_from_queue_timeout_error", "Error Processing Print Request")

			download_sv_retry_count = int(task.get_variable('download_sv_retry_count') or 0)
			task_start_time = task.get_variable('task_start_time') or datetime.datetime.now()
			if type(task_start_time) != str:
				task_start_time = task_start_time.strftime("%Y-%m-%d %H:%M:%S")

			if download_sv_retry_count > 0:
				print("Second Attempt")

			time_elapsed = datetime.datetime.now() - datetime.datetime.strptime(task_start_time, "%Y-%m-%d %H:%M:%S")
			if download_sv_retry_count > 1 and time_elapsed.seconds > 600:
				return task.bpmn_error("download_sv_from_queue_timeout_error", "More Than 10 Minutes Expired")

			download_sv_retry_count = download_sv_retry_count + 1
			sv_new_wait_timing = calculate_download_sv_wait_timing(download_sv_retry_count, task_start_time)
			result = {
				"task_start_time": {"value": task_start_time, "type": "string"},
				"sv_generation_check_date": {"value": sv_new_wait_timing.strftime('%Y-%m-%dT%H:%M:%S+0530'), "type": "string"},
				"download_sv_retry_count": {"value": download_sv_retry_count, "type": "string"}
			}
			return task.complete(global_variables=result)
			# except Exception as e:
			# 	return task.bpmn_error("download_sv_from_queue_timeout_error", e.__str__())
		elif topic == "ujjwala_sv_generation#process_sv":
			from ujjwala.models import UjjwalaV2Application

			# connection_disbursement_id = task.get_variable('connection_disbursement_id')
			application_id = task.get_variable('application_id')
			application = UjjwalaV2Application.objects.get(pk=application_id)
			connection_disbursement_id = application.connection_disbursement.id
			consumer_id = task.get_variable('consumer_id')

			booking_id = task.get_variable('booking_id')
			sv_file_content = download_file_variable_data(task.get_process_instance_id(), 'sv_file')
			sv_file_link = update_sv_document_v2(connection_disbursement_id, booking_id, consumer_id, sv_file_content)
			sv_date, sv_doc_no = get_sv_date_and_doc_no(sv_file_content)
			result = {
				"sv_file_link": {"value": sv_file_link, "type": "string"},
				"sv_date": {"value": sv_date, "type": "string"},
				"sv_document_number": {"value": sv_doc_no, "type": "string"},
				"connection_disbursement_id": {"value": connection_disbursement_id, "type": "string"},
			}
			return task.complete(global_variables=result)
		elif topic == "ujjwala_sv_generation#upload_sv_to_dca":
			from ujjwala.models import UjjwalaV2Application

			application_id = task.get_variable('application_id')
			application = UjjwalaV2Application.objects.get(pk=int(application_id))
			connection_disbursement_id = application.connection_disbursement.id

			# connection_disbursement_id = task.get_variable('connection_disbursement_id')
			consumer_id = task.get_variable('consumer_id')
			booking_id = task.get_variable('booking_id')
			sv_file_link = task.get_variable('sv_file_link')
			sv_date = task.get_variable('sv_date')
			document_number = task.get_variable('sv_document_number')
			update_in_dca(connection_disbursement_id, booking_id, sv_file_link, consumer_id, sv_date, document_number)
			return task.complete()
		elif topic == 'process_ekyc#update_in_dca':
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
			if req.status_code != 200:
				from ujjwala.models import UjjwalaV2Application
				obj = UjjwalaV2Application.objects.get(pk=dca_id)
				if not obj.status == UjjwalaV2ApplicationStatus.DOCUMENTS_UPLOADED:
					return task.complete()
				else:
					req.raise_for_status()
			return task.complete()
		elif topic == 'ujjwala_legal_docs_update#customer_status_update':
			from ujjwala.models import UjjwalaV2Application

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
			application = UjjwalaV2Application.objects.get(pk=application_id)
			send_pos_list_for_ekyc(application.contact_mobile)
			return task.complete()
		elif topic == 'CLDP_DEDUP_evaluate_and_update_dedup_results':
			activity_count = get_activity_instance_count('Activity_0i4o1xm', task.get_process_instance_id())
			start_relationship_activity_count = get_activity_instance_count('Activity_09zvctd',
			                                                                task.get_process_instance_id())

			if (activity_count - (start_relationship_activity_count * 200)) > 20:
				return task.bpmn_error('ERROR_delayed_clearing', "Looped Process More Than 20 Times")

			application_id = task.get_variable('id')
			nic_status = task.get_variable('nic_status')
			omc_status = task.get_variable('omc_status')
			ekyc_flag = task.get_variable('ekyc_flag')
			contact_number = task.get_variable('contact_number')
			product = task.get_variable('product')
			legal_docs_uploaded = task.get_variable('legal_docs_uploaded')

			cleared = ("Approved" in nic_status or "Clear" in nic_status) and "Clear" in omc_status
			reject = 'reject' in nic_status.lower() or 'reject' in omc_status.lower()
			approval = "Approval" in nic_status

			if not reject and approval:
				if "fo" in nic_status.lower():
					return task.bpmn_error(
						'Error_NIC_Error_FO_Approval', f'NIC: {nic_status}, OMC: {omc_status}',
						variables={
							'nic_status': {"value": nic_status, "type": "string"},
							'omc_status': {"value": omc_status, "type": "string"},
						}
					)

				if "DNSA" in nic_status and "Dist" in nic_status:
					return task.bpmn_error(
						'Error_Auto_Approve_Dedup', f'NIC: {nic_status}, OMC: {omc_status}',
						variables={
							'nic_status': {"value": nic_status, "type": "string"},
							'omc_status': {"value": omc_status, "type": "string"},
						}
					)

				return task.bpmn_error(
					'Error_NIC_Error_Dist_Approval', f'NIC: {nic_status}, OMC: {omc_status}',
					variables={
						'nic_status': {"value": nic_status, "type": "string"},
						'omc_status': {"value": omc_status, "type": "string"},
					}
				)
				#
				# return task.bpmn_error(
				# 	'Error_NIC_Error_User_Approval', f'NIC: {nic_status}, OMC: {omc_status}',
				# 	variables={
	            #        'nic_status': {"value": nic_status, "type": "string"},
	            #        'omc_status': {"value": omc_status, "type": "string"},
	            #     }
				# )

			if not reject and not cleared:
				dedup_retry_date = datetime.datetime.now() + datetime.timedelta(seconds=150)
				return task.bpmn_error('DEDUP_NOT_CLEAR', f'NIC: {nic_status}, OMC: {omc_status}', variables={
					'dedup_retry_date': {"value": dedup_retry_date.strftime('%Y-%m-%dT%H:%M:%S+0530'), "type": "string"},
					'nic_status': {"value": nic_status, "type": "string"},
					'omc_status': {"value": omc_status, "type": "string"},
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
		elif topic == 'ujjwala_legal_docs_update#fetch_payment_profile_variables':
			application_id = int(task.get_variable('application_id'))
			force_main_branch = True if task.get_variable('bank_account', '') else False
			payment_vars = fetch_payment_profile_variables(application_id, force_main_branch=force_main_branch)['result']

			if not payment_vars['status']:
				raise Exception(payment_vars['reason'])
			if payment_vars['ifscode'] == task.get_variable('ifscode', ''):
				raise Exception("No New IFSC To Try")

			result = {
				"bank_account": {"value": payment_vars['bank_account'], "type": "string"},
				"ifscode": {"value": payment_vars['ifscode'], "type": "string"},
				"first_name": {"value": payment_vars['first_name'], "type": "string"},
			}
			return task.complete(global_variables=result)
		elif topic == 'dca_change_phone_number#update_changed_number_in_dca':
			application_id = task.get_variable('application_id')
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
			return task.complete()
		elif topic == 'process_ekyc#process_existing_relationship':
			incident_dict = _existing_relation_regex.search(task.get_variable('bpmnError')).groupdict()
			if not incident_dict:
				return task.failure(
					"Regex Not Matching", traceback.format_exc(),
					max_retries=0, retry_timeout=0
				)

			variables_dict = {
                key: {"value": value, "type": "String"}
                for key, value in incident_dict.items()
            }

			if incident_dict['dict_code'] == '0000305948':
				return task.complete(global_variables=variables_dict)

			return task.bpmn_error("non_arun_indane_customer_error", task.get_variable('bpmnError'), variables=variables_dict)
		elif topic == 'process_ekyc#enrich_omc_rejection':
			application_id = task.get_variable('dca_id')
			dist_name = task.get_variable('dist_name')
			data = {'distributor_name': dist_name}
			res = enrich_omc_rejection_details(application_id, data)
			print(f"{application_id}, {res}")
			return task.complete()
		elif topic == 'ujjwala_legal_docs_update#enrich_omc_rejection':
			application_id = task.get_variable('application_id')
			dist_name = task.get_variable('dist_name')
			data = {'distributor_name': dist_name}
			res = enrich_omc_rejection_details(application_id, data)
			print(f"{application_id}, {res}")
			return task.complete()
		elif topic == 'process_get_ekyc_status_from_sdms#update_consumer_ekyc_status_in_dca':
			from ujjwala.models import UjjwalaV2Application, EkycLogs, FamilyMembers, Ekyc
			from ujjwala.enums import FamilyMemberRelationEnum

			dca_id = task.get_variable('dca_id')
			ekyc_flag = task.get_variable('ekyc_flag')
			ekyc_date = task.get_variable('ekyc_date')
			request_by_id = task.get_variable('requested_by_id')
			first_name = task.get_variable('first_name')
			last_name = task.get_variable('last_name')
			phone_number = task.get_variable('contact_number')
			relationship_type = task.get_variable('relationship_type')
			relationship_id = task.get_variable('relationship_id')
			omc_status = task.get_variable("omc_status")

			valid_ekyc_detail = None
			result_variables = {
				"sv_priority": {"value": 0, "type": "long"},
				"is_dedup_required": {"value": True if "pending" in omc_status else False, "type": "Boolean"}
			}

			biometric_authentication = False

			application = UjjwalaV2Application.objects.get(pk=dca_id)

			if ekyc_flag:
				ekyc_details = task.get_variable('ekyc_details')
				ekyc_details_list = json.loads(ekyc_details, object_hook=custom_decoder)
				print("Process Instance Id: {}".format(task.get_process_instance_id()))
				if ekyc_details_list:
					ekyc_details_biometric_list = []

					# First Find Biometric
					for ekyc_detail in ekyc_details_list:
						if 'Biometric' in ekyc_detail['Authentication Type']:
							ekyc_details_biometric_list.append(ekyc_detail)
					ekyc_details_biometric_list = sorted(ekyc_details_biometric_list, key=lambda x: x['Created On'],
					                                     reverse=True)
					if not ekyc_details_biometric_list:
						ekyc_details_valid_list = []
						for ekyc_detail in ekyc_details_list:
							if ekyc_detail['eKYC Sub Type'] == "Fresh KYC" and ekyc_detail['Channel'] == 'Mobility':
								ekyc_details_valid_list.append(ekyc_detail)
						ekyc_details_valid_list = sorted(ekyc_details_valid_list, key=lambda x: x['Created On'],
						                                 reverse=True)
						if ekyc_details_valid_list:
							valid_ekyc_detail = ekyc_details_valid_list[0]
							valid_ekyc_detail['Authentication Type'] = 'Biometric'
							biometric_authentication = False
					else:
						valid_ekyc_detail = ekyc_details_biometric_list[0]
						biometric_authentication = True

					if valid_ekyc_detail:
						parsed_date = datetime.datetime.strptime(ekyc_date,
						                                         "%d-%b-%Y %I:%M:%S %p") if ekyc_date else None
						application.ekyc_cleared = True
						application.ekyc_date = parsed_date
						application.ekyc_channel = valid_ekyc_detail['Authentication Type']
						application.save()
						self_family_member: FamilyMembers = application.family_members.filter(
							relation=FamilyMemberRelationEnum.SELF).first()

						if self_family_member.uid_check_result:
							self_family_member.uid_check_result['old_contact_name'] = \
							self_family_member.uid_check_result['contact_name']
							self_family_member.uid_check_result['contact_name'] = f"{last_name}, {first_name}"
							self_family_member.uid_check_result['old_phone_number'] = \
							self_family_member.uid_check_result['phone_number']
							self_family_member.uid_check_result['phone_number'] = phone_number
							self_family_member.uid_check_result['relationship_id'] = relationship_id
							self_family_member.save()

					EkycLogs.objects.create(
						parent_id=application.id, requested_by_id=int(request_by_id), ekyc_date=parsed_date
					)

					# application = UjjwalaV2Application.objects.get(pk=int(dca_id))
					if not Ekyc.objects.filter(parent=application).exists():
						Ekyc.objects.create(
							parent=application, ekyc_num=valid_ekyc_detail['eKYC Num'],
							ekyc_created_on=valid_ekyc_detail['Created On'],
							ekyc_type=valid_ekyc_detail['eKYC Type'],
							ekyc_subtype=valid_ekyc_detail['eKYC Sub Type'],
							channel=valid_ekyc_detail['Channel'],
							authentication_type=valid_ekyc_detail['Authentication Type'],
							status=valid_ekyc_detail['eKYC Status'],
							ekyc_details_data=ekyc_details_list
						)

					if relationship_type == 'LPG' and relationship_id:
						if application.consumer_id != relationship_id:
							application.consumer_id = relationship_id
							application.save()
				else:
					start_time = task.get_variable('start_time')
					if start_time:
						application.ekyc_last_attempt_log = f"Last attempt start time: {start_time} and could not find any E-KYC details. Did you click the button before doing E-KYC?"
						application.save()
			result_variables["biometric_authentication"] = {"value": biometric_authentication, "type": "Boolean"}
			return task.complete(global_variables=result_variables)
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
