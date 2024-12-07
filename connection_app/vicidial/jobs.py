# Description: This file contains the helper functions to interact with the Vicidial API.
# the functions are used to add a new user, phone, campaign, and list to Vicidial.
import logging, re, json, requests, csv
from django.http import JsonResponse
from io import StringIO  # If the CSV is provided as a string

VICIDIAL_NON_AGENT_API = "http://192.168.168.3/vicidial/non_agent_api.php"
VICIDIAL_AGENT_API = "http://192.168.168.3/agc/api.php"
VICIDIAL_AGENT_API_PANEL = "http://192.168.168.3/agc/vicidial.php"
VICIDIAL_CAMPAIGN_API = "http://192.168.168.3/vicidial/add_campaign_api.php"
VICIDIAL_IMP_LOGOUT = "http://192.168.168.3//vicidial/api_log_agent_out.php"
API_USER = "ashish"
API_PASS = "phone321"

# Logging configuration for debugging
logging.basicConfig(level=logging.INFO)


def check_user_status(user_id, csv_data):
	# Parse the CSV data
	csv_file = StringIO(csv_data)  # Replace csv_data with the actual CSV string
	reader = csv.reader(line.strip() for line in csv_file)

	for row in reader:
		# print(row , len(row) , type(row) ,str(user_id))
		if len(row) > 3 and row[0] == str(user_id):
			return row[3]

	return None



def make_api_request(url, payload, data=None, flag=False):
	# if "SUCCESS" in response.text or "ALREADY EXISTS" in response.text or "user,campaign_id,session_id" in response.text:
	"""Helper function to make API calls and handle errors."""
	try:
		response = requests.post(url, params=payload, data=data)  # Add a timeout
		print(f"the request has commited {response.text}, {type(response), response}")

		if flag:
			return response
		# Check for the existence of the 'status' key and whether it's a success
		if any(keyword in response.text for keyword in
			   ["SUCCESS", "ALREADY EXISTS", "user,campaign_id,session_id", "list_id|list_name|campaign_id|",
				"success"]):
			return {"status": "success", "message": response.text}
		return {"status": "error", "message": response.text}

	except requests.exceptions.Timeout:
		logging.error(f"Timeout error on request to {url}")
		return {"status": "error", "message": "Request timed out"}
	except requests.exceptions.RequestException as e:
		logging.error(f"Request failed: {str(e)}")
		return {"status": "error", "message": str(e)}
	except ValueError:
		# Handle case where the response isn't JSON (e.g., API is down, wrong format)
		logging.error(f"Invalid JSON response from {url}")
		return {"status": "error", "message": "Invalid response format"}


class VicidialService:
	def __init__(self, user=API_USER, password=API_PASS):
		self.user = user
		self.password = password

	def login_old(self, user, user_pass, phone_login, phone_pass):
		query = f"{VICIDIAL_AGENT_API_PANEL}/agc/vicidial.php?source=login-vicidial&phone_login={phone_login}&phone_pass={phone_pass}&VD_login={user}&VD_pass={user_pass}&VD_campaign=POD02&SUBMIT=SUBMIT"

		response = requests.get(query)
		title_tags = re.findall(r'<title>(.*?)</title>', response.text, re.IGNORECASE)
		print(f"the response we got is {title_tags}")

		# Check if there's only one <title> tag and its content is exactly "Agent web client"
		if len(title_tags) == 1 and title_tags[0].strip() == "Agent web client":
			return JsonResponse({"message": "login successful", "status": "success"}, safe=False)
		else:
			return JsonResponse({"message": "login error", "status": "error"}, safe=False)

	def login(self, agent_user,  phone_number):
		if not phone_number and not agent_user:
			return {"status": "error", "message": "Phone number and agent user are required."}
		# Step 1: change the phone number for calling
		respnse = self.update_phone({"agent_user": agent_user, "phone_number": phone_number})
		if respnse["status"] == "error":
			return respnse

	def hangup(self, agent_user):
		# Step 1: Hangup agent call
		hangup_payload = {
			"user": self.user,
			"pass": self.password,
			"agent_user": agent_user,
			"source": "external_hangup_delivery_agent_call",
			"function": "external_hangup",
			"value": 1
		}
		return make_api_request(VICIDIAL_AGENT_API, hangup_payload)

	def dispo(self, agent_user, dispo_code,callback_datetime):
		dispo_payload = {
			"user": self.user,
			"pass": self.password,
			"agent_user": agent_user,
			"function": "external_status",
			"source": "external_dispo_delivery_agent_call",
			"value": dispo_code,
			"callback_datetime": callback_datetime,
			"callback_type": "USERONLY"
		}
		return make_api_request(VICIDIAL_AGENT_API, dispo_payload)

	def toggle(self, agent_user, status):
		# Step 1: Toggle agent calling status
		toggle_payload = {
			"user": self.user,
			"pass": self.password,
			"agent_user": agent_user,
			"function": "external_pause",
			"source": "external_toggle_calling_status",
			"value": status
		}
		result = make_api_request(VICIDIAL_AGENT_API, toggle_payload)
		if result["status"] == "error":
			return result
		print(f"the result we got is {result} and {type(result), result['message']}")
		message = result["message"]
		# If the toggle is successful
		return {"status": "success", "message": f"{message}."}

	def is_logged_in(self, agent_user):
		# Step 1: Check if the agent is logged in
		check_payload = {
			"user": self.user,
			"pass": self.password,
			"function": "logged_in_agents",
			"source": "external_logout_agent",
			"stage": "csv",
			"header": "YES",
		}
		result = make_api_request(VICIDIAL_NON_AGENT_API, check_payload)
		if result["status"] != "error":
			# Check if the agent is logged in
			if agent_user in result["message"]:
				return {"status": "success", "message": f"{agent_user} is logged in.", "data": result["message"]}
			return {"status": "error", "message": f"{agent_user} is not logged in."}
		return result

	def Imp_logout(self, agent_user):
		imp_logout_payload = {
			"auth_user": self.user,
			"auth_pw": self.password,
			"user": agent_user,
		}
		response = make_api_request(VICIDIAL_IMP_LOGOUT,payload=None ,data=json.dumps(imp_logout_payload), flag=True)
		print(f"the response we got is {response}")
		if response.status_code == 200:
			return {"status": "success", "message": "Logout successful."}
		return {"status": "error", "message": "Logout failed.", "response": response.text}

	def logout(self, agent_user):
		logout_payload = {
			"user": self.user,
			"pass": self.password,
			"agent_user": agent_user,
			"function": "logout",
			"source": "external_logout_agent",
			"value": "LOGOUT"
		}
		response = make_api_request(VICIDIAL_AGENT_API, logout_payload)
		print(f"the response we got is {response}")

		if response["status"] != "error" or "agent_user is not logged in" in response["message"]:
			check_logout = self.is_logged_in(agent_user)
			if check_logout["status"] == "error":
				return {"status": "success", "message": "Logout successful."}

			check_status = check_user_status(agent_user, check_logout["data"])
			if check_status in ["WRAPUP", "DISPO", "INCALL", "MANUAL", "RING", "QUEUE"]:
				return {"status": "error", "message": "Logout failed. Agent is still in a call."}

			return {"status": "success", "message": "Logout successful."}

		return response

	def Add_leadsToVicidial(self, data, list_id="5555"):
		lead_parms = {
			"source": "test",
			"function": "add_lead_list",
			"user": self.user,
			"pass": self.password,
			"list_id": list_id,
		}

		lead_payload = json.dumps(data)
		if lead_payload:
			print(f"the lead_payload we got is {len(lead_payload)}")
		result = make_api_request(VICIDIAL_NON_AGENT_API, lead_parms, lead_payload)
		print(f"the result we got is {result}")
		if result["status"] == "error":
			print("Error in creating lead", result, result.get("message"))
			return result
		return {"status": "success", "message": "Successfully added leads."}

	def CallAgent(self, agent_user):
		call_payload = {
			"user": self.user,
			"pass": self.password,
			"function": "call_agent",
			"source": "external_call_delivery_agent",
			"agent_user": agent_user,
			"value": "CALL"
		}
		result = make_api_request(VICIDIAL_AGENT_API, call_payload)
		if result["status"] == "error":
			return result
		return {"status": "success", "message": "Call placed successfully."}

	def update_phone(self, agent_user,  phone_number,request=None):
		if not phone_number and not agent_user:
			return {"status": "error", "message": "Phone number and agent user are required."}

		phone_load = {
			"user": self.user,
			"pass": self.password,
			"function": "update_phone",
			"source": "external_update_phone",
			"extension": agent_user,
			"dialplan_number": phone_number,
			"server_ip": "192.168.168.3",
		}
		result = make_api_request(VICIDIAL_NON_AGENT_API, phone_load)
		if result["status"] == "error":
			return result
		return {"status": "success", "message": "Phone updated successfully.", "pass": request.user.id}

	def list_info(self, list_id, agent_user):
		list_payload = {
			"user": self.user,
			"pass": self.password,
			"function": "list_info",
			"source": "external_list_info",
			"list_id": list_id,
			"header": "YES",
		}
		result = make_api_request(VICIDIAL_NON_AGENT_API, list_payload)
		if result["status"] != "error":
			if str(agent_user) in result["message"]:
				return {"status": "success", "campaign": True, "message": f"{agent_user} is in the list."}
			return {"status": "success", "campaign": False, "message": f"{agent_user} is not in the list."}
		return result

	def is_user_delivery_boy(self, data):
		# Step 1: Add Vicidial user
		user_payload = {
			"user": self.user,
			"pass": self.password,
			"function": "add_user",
			"source": "external_add_delivery_agent",
			"agent_user": data['agent_user'],
			"agent_pass": data['agent_pass'],
			"agent_full_name": data['agent_fullname'],
			"agent_user_group": "delivery_agents",
			"agent_user_level": "4"
		}
		result = make_api_request(VICIDIAL_NON_AGENT_API, user_payload)
		if result["status"] == "error":
			print("Error in creating user", result)
			return result

		# Step 2: Add Vicidial phone
		phone_payload = {
			"user": self.user,
			"pass": self.password,
			"function": "add_phone",
			"source": "external_add_delivery_agent_phone",
			"extension": data['agent_user'],
			"phone_login": data['agent_user'],
			"voicemail_id": data['phone_number'],
			"dialplan_number": data['phone_number'],
			"outbound_cid": data['phone_number'],
			"phone_pass": data['agent_pass'],
			"registration_password": f"reg_{data['agent_pass']}",
			"phone_full_name": f"ext{data['agent_user']}",
			"server_ip": "192.168.168.3",
			"protocol": "EXTERNAL",
			"local_gmt": "-5.00"
		}
		result = make_api_request(VICIDIAL_NON_AGENT_API, phone_payload)
		if result["status"] == "error":
			print("Error in creating phone", result)
			return result

		# Step 3: Create a campaign for the delivery boy
		campaign_payload = {
			"user": self.user,
			"pass": self.password,
			"campaign_id": data['agent_user'],
			"campaign_name": data['agent_fullname'],
			'original_campaign_id': 'POD02',
			'copy_campaign': True
		}
		result = make_api_request(VICIDIAL_CAMPAIGN_API, campaign_payload)
		if result["status"] == "error":
			print("Error in creating campaign", result)
			return result

		# Step 4: Add a list for the delivery boy's campaign
		list_payload = {
			"source": "test",
			"function": "add_list",
			"user": self.user,
			"pass": self.password,
			"list_id": data['list_id'],
			"list_name": f"{data['agent_user']} list",  # 2-30 characters
			"campaign_id": data["agent_user"],
			"active": "Y",
			"list_description": f"Delivery list for {data['agent_user']} campaign",
		}
		result = make_api_request(VICIDIAL_NON_AGENT_API, list_payload)
		if result["status"] == "error":
			print("Error in creating list", result)
			return result

		# If all steps are successful
		return {"status": "success", "message": "Successfully added user, phone, campaign, and list."}
