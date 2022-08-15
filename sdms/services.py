import json

import requests

LOGIN_URL = 'https://spandan.indianoil.co.in/ePIC/DealerLoginAuthentication'
OMC_DEDUP_URL = 'https://spandan.indianoil.co.in/ePIC/OmcDedup'


class LoginRequired(Exception):
	pass


class IoclOmcDedup():

	def __init__(self, user, password):
		self.session = requests.Session()
		self.user = user
		self.password = password

	def login(self):
		return self.session.post(
			LOGIN_URL,
			data={
				'LogId': self.user,
				'LogPwd': self.password,
				'LogType': 2
			}
		)

	def __process_omc_dedup_result__(self, res_code):
		"""
		if (hpres === 'A' || hpres === 'P')
		{
			document.getElementById('hpc_' + row_num).innerHTML = "Present";
			document.getElementById('hpc_' + row_num).style.color = "#009933";
			document.getElementById('hpc_' + row_num).style.fontSize = "13px";
		} else if (hpres === 'N')
		{
			document.getElementById('hpc_' + row_num).innerHTML = "Not Present";
			document.getElementById('hpc_' + row_num).style.color = "#e62e00";
			document.getElementById('hpc_' + row_num).style.fontSize = "13px";
		} else if (hpres === 'I')
		{
			document.getElementById('hpc_' + row_num).innerHTML = "Invalid Input";
			document.getElementById('hpc_' + row_num).style.color = "#e68a00";
			document.getElementById('hpc_' + row_num).style.fontSize = "13px";
		} else
		{
			document.getElementById('hpc_' + row_num).innerHTML = "Technical Error, Kindly try again";
			document.getElementById('hpc_' + row_num).style.color = "#0066ff";
			document.getElementById('hpc_' + row_num).style.fontSize = "12px";
		}
		"""
		if res_code in ('A', 'P'):
			return "Present"
		elif res_code == 'N':
			return "Not Present"
		elif res_code == 'I':
			return "Invalid Input"
		else:
			return "Technical Error, Kindly try again"


	def omc_aadhar_dedup(self, aadhar_no):
		resp = self.session.post(OMC_DEDUP_URL, data={
			'requestType': 'A',
			'aadharNo': aadhar_no,
			'account': '',
			'bankCode': '',
		})
		resp = resp.text

		if not resp:
			self.login()
			return self.omc_aadhar_dedup(aadhar_no)

		resp = json.loads(resp)
		return {
			'HPCL': self.__process_omc_dedup_result__(resp[0]),
			'BPLC': self.__process_omc_dedup_result__(resp[1]),
			'IOCL': self.__process_omc_dedup_result__(resp[2])
		}


if __name__ == '__main__':
	dedup_portal = IoclOmcDedup('305948', 'Arun@305948')
	# dedup_portal.login()

	resp = dedup_portal.omc_aadhar_dedup('984336989869')

	for omc, status in resp.items():
		if status == 'Present':
			{
				'distributor_name': omc,
				'consumer_id': 'NotAvail-CheckWithDistributor',
				'contact_address': ''
			}

	print(resp)