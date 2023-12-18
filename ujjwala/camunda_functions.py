import datetime

import arrow
import pandas as pd
import requests

# Camunda Production URL
# CAMUNDA_WEB_ROOT_URL = "https://camunda.dca.arungas.com"
from domestic_app import settings

# CAMUNDA_WEB_ROOT_URL = "http://192.168.171.15:38080"
# Camunda Development URL
#CAMUNDA_WEB_ROOT_URL = "http://192.168.168.4:25252"

from domestic_app.settings import CAMUNDA_BASE_URL
# Camunda Base URL
# CAMUNDA_BASE_URL = f"{settings.CAMUNDA_BASE_URL}/engine-rest"
UJJWALA_SV_GENERATION_PROCESS = 'ujjwala_sv_generation'
PROCESS_CLDP_DEDUP = "Process_CLDP_DEDUP"


def start_ujjwala_sv_process_in_camunda(connection_disbursement_id, disbursement_drive):
	from ujjwala.models import ConnectionDisbursement, DisbursementDrive

	ci_obj = ConnectionDisbursement.objects.get(pk=connection_disbursement_id)

	sv_priority = disbursement_drive.priority - ConnectionDisbursement.objects.filter(
		disbursement_drive_id=disbursement_drive.id).order_by('-walk_in_date').count()
	url = "{}/process-definition/key/{}/start".format(CAMUNDA_BASE_URL, UJJWALA_SV_GENERATION_PROCESS)
	res = requests.post(url, json={
		"variables": {
			"connection_disbursement_id": {"value": ci_obj.id, "type": "string"},
			"consumer_id": {"value": ci_obj.parent.consumer_id, "type": "string"},
			"application_id": {"value": ci_obj.parent_id, "type": "string"},
			"name": {"value": ci_obj.parent.name, "type": "string"},
			"product": {"value": ci_obj.parent.product, "type": "string"},
			"sv_priority": {"value": sv_priority, "type": "integer"},
		}
	})

	if res.status_code == 200:
		return True, res.json()['id']
	return False, res.text


def start_ujjwala_sv_process_in_camunda_v2(connection_disbursement_id, sv_priority=None):
	from ujjwala.models import ConnectionDisbursement

	ci_obj = ConnectionDisbursement.objects.get(pk=connection_disbursement_id)

	if not sv_priority:
		sv_priority = ci_obj.disbursement_drive.priority - ConnectionDisbursement.objects.filter(
			disbursement_drive_id=ci_obj.disbursement_drive.id).order_by('-walk_in_date').count()
	url = "{}/process-definition/key/{}/start".format(CAMUNDA_BASE_URL, UJJWALA_SV_GENERATION_PROCESS)
	res = requests.post(url, json={
		"variables": {
			"connection_disbursement_id": {"value": ci_obj.id, "type": "string"},
			"consumer_id": {"value": ci_obj.parent.consumer_id, "type": "string"},
			"application_id": {"value": ci_obj.parent_id, "type": "string"},
			"name": {"value": ci_obj.parent.name, "type": "string"},
			"product": {"value": ci_obj.parent.product, "type": "string"},
			"sv_priority": {"value": sv_priority, "type": "integer"},
		}
	})

	if res.status_code == 200:
		return True, res.json()['id']
	return False, res.text


def evaluate_and_start_ujjwala_sv_process_in_camunda(connection_disbursement_id, sv_priority=None):
	from ujjwala.models import ConnectionDisbursement, ConnectionDisbursementInvitation

	ci = ConnectionDisbursement.objects.get(pk=connection_disbursement_id)

	res = requests.post(f"{CAMUNDA_BASE_URL}/engine-rest/process-instance", json={
		"variables": [{"operator": "eq", "name": "connection_disbursement_id", "value": f"{ci.pk}"}]})
	if res.json():
		for process_instance in res.json():
			res = requests.delete(f"{CAMUNDA_BASE_URL}/engine-rest/process-instance/{process_instance['id']}")
			print(res.text)

	if ci.invitation.first():
		invitation: ConnectionDisbursementInvitation = ci.invitation.first()
		if invitation.sv_link:
			return True, 'sv_exist'

	return start_ujjwala_sv_process_in_camunda_v2(ci.pk, sv_priority=sv_priority)


def re_push_task_in_camunda_process(connection_disbursement_id):
	from ujjwala.models import ConnectionDisbursement, DisbursementDrive

	cd_obj = ConnectionDisbursement.objects.get(id=connection_disbursement_id)

	print("Connection Disbursement Id: ", cd_obj.id, "Camunda Task Id: ", cd_obj.camunda_process_id)
	if not cd_obj.camunda_process_id:
		result, msg = start_ujjwala_sv_process_in_camunda_v2(connection_disbursement_id)
		return result, msg
	elif cd_obj.invitation.exists():
		if cd_obj.invitation.first().sv_link:
			return True, cd_obj.camunda_process_id
	else:
		url = "{}/process-instance".format(CAMUNDA_BASE_URL)
		res = requests.post(url, json={
			"processInstanceIds": [f"{cd_obj.camunda_process_id}"]
		})
		if not res.json():
			start_ujjwala_sv_process_in_camunda_v2(connection_disbursement_id)


def start_ujjwala_cld_dedup_in_camunda(consumer_id, application_id):
	url = "{}/process-definition/key/{}/start".format(CAMUNDA_BASE_URL, PROCESS_CLDP_DEDUP)
	#
	# data = requests.get("https://dca.arungas.com/ujjwala/ujjwala-bot//get_list_to_fetch_omc_nic_status/&quot;).json()
	#
	# for i in data:
	# record = i['payload']
	# if record['id'] in existing:
	# continue
	res = requests.post(url, json={
		"variables": {
			"consumer_id": {"value": consumer_id, "type": "string"},
			"id": {"value": application_id, "type": "string"},
		}
	})
	res.raise_for_status()
	return res.json()


def download_file_variable_data(process_instance_id, variable_name):
	url = f"{CAMUNDA_BASE_URL}/process-instance/{process_instance_id}/variables/{variable_name}/data"

	res = requests.get(url)
	res.raise_for_status()
	return res.content


def calculate_download_sv_wait_timing(download_sv_retry_count, task_start_time):
	wait_time = 0
	url = f"{CAMUNDA_BASE_URL}/history/process-instance/"

	finished_after = datetime.datetime.today() - datetime.timedelta(hours=0, minutes=5)
	res = requests.get(
		url=url,
		params={
			"processDefinitionKey": UJJWALA_SV_GENERATION_PROCESS,
			"finishedAfter": "{}".format(finished_after.strftime("%Y-%m-%dT%H:%M:%S.%f+0000"))
		}
	)
	process_list = res.json()

	url = f"{CAMUNDA_BASE_URL}/history/variable-instance"

	report_list = []

	for process in process_list:
		row = {'process_id': process['id']}
		res = requests.get(url=url, params={"processInstanceId": process['id']})
		variable_list = res.json()
		for variable in variable_list:
			if variable['name'] in ['report_start_time', 'report_end_time']:
				row[variable['name']] = variable['value']
		report_list.append(row)

	if report_list:
		df = pd.DataFrame.from_dict(report_list)
		df['report_start_time'] = pd.to_datetime(df['report_start_time'])
		df['report_end_time'] = pd.to_datetime(df['report_end_time'])
		df['report_time'] = (df['report_start_time'] - df['report_end_time']).dt.seconds

		df = df['report_time'].dropna()

		if download_sv_retry_count == 1:
			wait_time = df['report_time'].quantile(0.55)
		elif download_sv_retry_count == 2:
			wait_time = df['report_time'].quantile(0.75)
		elif download_sv_retry_count == 3:
			wait_time = df['report_time'].quantile(0.90)
		elif download_sv_retry_count == 4:
			wait_time = df['report_time'].quantile(0.99)
		wait_time = wait_time

	new_wait_time = datetime.datetime.strptime(task_start_time, "%Y-%m-%d %H:%M:%S") + datetime.timedelta(seconds=wait_time)
	# new_wait_time = task_start_time + datetime.timedelta(seconds=wait_time)

	if new_wait_time < datetime.datetime.now():
		new_wait_time = datetime.datetime.now() + datetime.timedelta(seconds=150)

	return new_wait_time


# Pre Inspection Process Start In Camunda
def start_pre_inspection_review_process_in_camunda(pre_inspection_id):
	# url = "{}/process-definition/key/{}/start".format(CAMUNDA_BASE_URL, "process_review_pre_inspection")
	url = "{}/process-definition/key/{}/start".format("http://192.168.168.4:25252", "process_review_pre_inspection")
	res = requests.post(url, json={
		"variables": {
			"pre_inspection_id": {"value": pre_inspection_id, "type": "long"},
		}
	})

	if res.status_code == 200:
		return True, res.json()['id']
	return False, res.text


def start_process_in_camunda(process_definition_key, variables):
	url = "{}/process-definition/key/{}/start".format(CAMUNDA_BASE_URL, process_definition_key)
	res = requests.post(url, json=variables)

	if res.status_code == 200:
		return True, res.json()['id']
	return False, res.text


def num_there(s):
	return any(i.isdigit() for i in s)


def fetch_payment_profile_variables(application_id, force_main_branch=False):
	res = requests.get(
		"http://192.168.168.4:60612/ujjwala/ujjwala-extra/get_payment_variables/",
        params={"application_id": application_id, 'force_main_branch': force_main_branch}
	)
	res.raise_for_status()
	return res.json()
	# from ujjwala.models import UjjwalaV2Application
	# from reference_data.models import IFSCodeList, RTGSList
	#
	# application = UjjwalaV2Application.objects.get(pk=application_id)
	#
	# old_ifscode = application.ifsc_code.strip().replace(" ", "")
	#
	# bank_code = old_ifscode[:4]
	#
	# new_ifscode = None
	#
	# if num_there(bank_code):
	# 	raise Exception(f"Invalid IFSCode: {old_ifscode}. Manually Correct.")
	#
	# res = requests.get(f"https://ifsc.razorpay.com/{old_ifscode}")
	# if res.status_code == 200:
	# 	new_ifscode = old_ifscode
	# else:
	# 	ifscodelist_obj: IFSCodeList = IFSCodeList.objects.filter(old_ifscode=old_ifscode).first()
	# 	if ifscodelist_obj:
	# 		new_ifscode = ifscodelist_obj.new_ifscode
	# 	else:
	# 		merged_bank_code = IFSCodeList.objects.filter(
	# 			old_ifscode__istartswith=old_ifscode[:4]).first()
	# 		if merged_bank_code:
	# 			rtgs_ifscode = RTGSList.objects.filter(ifscode__istartswith=merged_bank_code.new_ifscode[:4]).first()
	# 			new_ifscode = rtgs_ifscode.ifscode if rtgs_ifscode else None
	#
	# if not new_ifscode:
	# 	raise Exception(f"No Matching IFSCode Found Against Existing IFSCode: {old_ifscode}")
	#
	# return {
	# 	"bank_account": application.bank_account_number,
	# 	"ifscode": new_ifscode,
	# 	"first_name": application.name
	# }



if __name__ == '__main__':
	# connection_disbursement_id = 12735
	# start_ujjwala_sv_process_in_camunda(connection_disbursement_id)
	l = [13627, 14941, 15500]

	for i in l:
		re_push_task_in_camunda_process(i)
