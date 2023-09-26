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


	def __process_omc_dedup_result__v2(self, res_code):
		"""
		{
		    "TRANSACID": "20230923121515-56592777",
		    "CON_STATE": null,
		    "CDP_ID": null,
		    "KYC_ID": null,
		    "CONSUMER_NO": null,
		    "LPG_ID": null,
		    "OMC_CODE": "3",
		    "DEDUP_RESULT": "Reject",
		    "DEMO_RESULT": null,
		    "COUNTERPART": [
		        {
		            "CON_STATE": "Consumer",
		            "CDP_ID": "1328115271",
		            "KYC_ID": null,
		            "LPG_ID": "10000000111494923",
		            "OMC_CODE": "1",
		            "DEDUP_TYP": "A",
		            "DEDUP_GRPID": "1",
		            "SUSPFLAG": null,
		            "DISTR_CODE": "188177",
		            "DISTR_NAME": "MANASWINI BHARATGAS GRAMIN VITRAK",
		            "DISTR_ADDR1": "AT/PO ERABANGA",
		            "DISTR_ADDR2": "PS GOP VIA BIRATUNG",
		            "DISTR_ADDR3": null,
		            "CONS_NAME": "KUNTALA BARAL",
		            "CONS_NO": "111494923",
		            "CONS_ADDR1": "- W/O-PABITRA MOHAN BARAL",
		            "CONS_ADDR2": "AT-KHANDASAHI PO-RAHANGA",
		            "CONS_ADDR3": "PURI Odisha",
		            "LANDMARK": "PS-GOP",
		            "VILL_TOWN": "409424",
		            "PIN_CODE": "752110",
		            "KYC_DATE": "20210821000000",
		            "SV_DATE": null,
		            "SEED_DATE": null,
		            "INSTL_DATE": "20210907183500",
		            "PPAC_DISTCODE": "2222",
		            "PPAC_STATCODE": null,
		            "CONS_STATUS": "1A",
		            "RATION_CARD": null,
		            "RELATIONCODE": "F",
		            "FAM_MEMBRNAME": "PABITRA MOHAN BARAL",
		            "ERROR_CODE": "ZZM_MSGCLS-015",
		            "ERROR_MSG": "Duplicate Aadhaar found in CDP"
		        }
		    ]
		}
		"""
		if resp.get('DEDUP_RESULT', ''):
			return resp.get('COUNTERPART')
		elif resp.get('ERRORS', ''):
			errors = resp.get('ERRORS')
			if errors[0]['ERROR_CODE'] == 0:
				return "Success"
		else:
			return "Technical Error, Kindly try again"


	def omc_aadhar_dedup(self, aadhar_no):
		# resp = self.session.post(OMC_DEDUP_URL, data={
		# 	'requestType': 'A',
		# 	'aadharNo': aadhar_no,
		# 	'account': '',
		# 	'bankCode': '',
		# })
		resp = self.session.post(OMC_DEDUP_URL, data={
			'requestType': '02',
			'aadhaar': aadhar_no,
			'atr': '',
			'ifscState': '',
		})
		resp = resp.text

		if not resp:
			self.login()
			return self.omc_aadhar_dedup(aadhar_no)

		resp = json.loads(resp)
		# return {
		# 	'HPCL': self.__process_omc_dedup_result__(resp[0]),
		# 	'BPLC': self.__process_omc_dedup_result__(resp[1]),
		# 	'IOCL': self.__process_omc_dedup_result__(resp[2])
		# }
		return resp


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