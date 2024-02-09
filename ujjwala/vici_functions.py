import requests


def update_lead_in_out1005_campaign(mobile):
	query = """
	http://vici.arungas.com/vicidial/non_agent_api.php?source=localhost&user=6666&pass=C00lerMaster101&function=update_lead&phone_number={}&search_method=PHONE_NUMBER&list_id=602&search_location=LIST&insert_if_not_found=Y&campaign_id=OUTG1005&phone_code=1&status=MSDCAL&reset_lead=Y
	""".format(mobile)
	res = requests.post(query)
	return res


def update_lead_in_ujjwala_welcome(mobile):
	res = requests.post(
		"http://vici.arungas.com/vicidial/non_agent_api.php?source=ujjwala&user=6666&pass=C00lerMaster101"
		"&function=add_lead&phone_number={}&list_id=1007".format(mobile)
	)
	return res


def update_lead_in_ujjwala_enquiry_list(mobile):
	res = requests.post(
		"http://vici.arungas.com/vicidial/non_agent_api.php?source=ujjwala&user=6666&pass=C00lerMaster101"
		"&function=add_lead&phone_number={}&list_id=77771".format(mobile)
	)
	return res


def add_lead_to_vicidial(contact_mobile, name, id):
	res = requests.post(
		"http://vici.arungas.com/vicidial/non_agent_api.php?source=ujjwala&user=6666&pass=C00lerMaster101"
		"&function=add_lead&phone_number={}&phone_code=1&list_id=1001&first_name={}&last_name={}".format(contact_mobile,
		                                                                                                 name, id)
	)
	return res
