import datetime

import pandas as pd
import requests

# Camunda Production URL
# CAMUNDA_WEB_ROOT_URL = "https://process.arungas.com"
# Camunda Development URL
CAMUNDA_WEB_ROOT_URL = "http://192.168.168.4:25252"

# Camunda Base URL
CAMUNDA_BASE_URL = f"{CAMUNDA_WEB_ROOT_URL}/engine-rest"
UJJWALA_SV_GENERATION_PROCESS = 'ujjwala_sv_generation'


def start_ujjwala_sv_process_in_camunda(connection_disbursement_id):
	from ujjwala.models import ConnectionDisbursement, DisbursementDrive

	ci_obj = ConnectionDisbursement.objects.get(pk=connection_disbursement_id)

	sv_priority = ci_obj.disbursement_drive.priority - ConnectionDisbursement.objects.filter(
		disbursement_drive_id=ci_obj.disbursement_drive_id).order_by('-walk_in_date').count()
	url = "{}/process-definition/key/{}/start".format(CAMUNDA_BASE_URL, UJJWALA_SV_GENERATION_PROCESS)
	res = requests.post(url, json={
		"variables": {
			"connection_disbursement_id": {"value": ci_obj.id, "type": "string"},
			"consumer_id": {"value": ci_obj.parent.consumer_id, "type": "string"},
			"application_id": {"value": ci_obj.parent_id, "type": "string"},
			"name": {"value": ci_obj.parent.name, "type": "string"},
			"product": {"value": ci_obj.parent.product, "type": "string"},
			"sv_priority": {"value": sv_priority, "type": "string"},
		}
	})

	if res.status_code == 200:
		return True, res.json()['id']
	return False, res.text


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

	new_wait_time = task_start_time + datetime.timedelta(seconds=wait_time)

	if new_wait_time < datetime.datetime.now():
		new_wait_time = datetime.datetime.now() + datetime.timedelta(seconds=150)

	return new_wait_time


if __name__ == '__main__':
	connection_disbursement_id = 12735
	start_ujjwala_sv_process_in_camunda(connection_disbursement_id)
