from django.views.generic.edit import FormView
from django.urls import reverse_lazy
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync
import requests, json, re
from django.http import JsonResponse
from django.views import View
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from teams.models import UserProfile
from django.shortcuts import render
from .forms import VicidialDeliveryBoyForm
from .ak_jobs import VicidialService
import logging

logger = logging.getLogger(__name__)

vicidial_service = VicidialService()


@csrf_exempt
def vicidial_webhook(request):
	logger.info(f"Received webhook request {request}")

	if request.method == "GET":
		session_id = request.GET.get("campaign")  # Get session_id from query params
		logger.info(f"Received webhook for session_id: {session_id}")

		data = request.GET.dict()  # Capture all query parameters as data

		# Define the group name based on session_id
		group_name = f"vicidial_{session_id}"

		# Get the channel layer and send data to the group
		channel_layer = get_channel_layer()
		async_to_sync(channel_layer.group_send)(
			group_name,
			{
				"type": "send_data",  # Matches `send_data` method in VicidialConsumer
				"data": data
			}
		)

		return JsonResponse({"status": "received"})


def validate_no_special_characters(value):
	return re.sub(r'[!@#$%^&*(),.?":{}|<>]', '', value)


@csrf_exempt
def delivery_boy_signup_view(request):
    if request.method == "POST":
        try:
            current_user = request.user
            resolve_Id = UserProfile.objects.get(user=current_user)
            list_id = "88" + str(resolve_Id.id)
            phone_no = resolve_Id.phone_number

            # Get the cleaned form data
            data = {
                'agent_fullname': str(current_user.first_name) + " " + str(current_user.last_name),
                'agent_user': validate_no_special_characters(current_user.username),
                'agent_pass': current_user.id,
                'phone_number': phone_no,
                'list_id': list_id,
            }

            result = vicidial_service.is_user_delivery_boy(data)

            # Check the result and handle responses
            if result.get('status') == 'success':
                return JsonResponse({
                    'status': 'success',
                    'message': result.get('message', 'Submission successful!')
                }, status=200)
            else:
                return JsonResponse({
                    'status': 'error',
                    'message': result.get('message', 'An error occurred while processing the request.')
                }, status=400)
        except UserProfile.DoesNotExist:
            return JsonResponse({
                'status': 'error',
                'message': 'User profile not found.'
            }, status=404)
        except Exception as e:
            logger.error(f"An error occurred: {e}")
            return JsonResponse({
                'status': 'error',
                'message': 'An unexpected error occurred.'
            }, status=500)
    else:
        return render(request, 'connection_app/customer-profile/vicidial_delivery_form.html')


@method_decorator(csrf_exempt, name='dispatch')
class AgentActionView(View):
	def post(self, request, action=None):
		# Parse the JSON payload
		body = json.loads(request.body.decode('utf-8'))
		agent_user = body.get('agent_user').replace(".", "") if 'agent_user' in body else request.user.username.replace(
			".", "")
		dispo_code = body.get('disposition', None)
		callback_datetime = body.get('datetime', None)
		phone_number = body.get('phone_number', None)
		status = body.get('status', None)

		if action == "hangup":
			response_data = vicidial_service.hangup(agent_user)
		elif action == "dispostion" and dispo_code:
			response_data = vicidial_service.dispo(agent_user, dispo_code,callback_datetime)
		elif action == "toggle" and status:
			response_data = vicidial_service.toggle(agent_user, status)
		elif action == "isloggedin":
			response_data = vicidial_service.is_logged_in(agent_user)
		elif action == "CallAgent":
			response_data = vicidial_service.CallAgent(agent_user)
		elif action == "Imp_logout":
			response_data = vicidial_service.Imp_logout(agent_user)
		elif action == "logout":
			response_data = vicidial_service.logout(agent_user)
		elif action == "login":
			response_data = vicidial_service.update_phone(agent_user=agent_user,phone_number=phone_number,request= request)
		else:
			return JsonResponse({"status": "error", "message": "Invalid action or missing parameters."})
		print(f"the response we got is {response_data}")

		if hasattr(response_data, 'content'):
			return JsonResponse(response_data.content.decode(), safe=False)

		return JsonResponse(response_data, safe=False)


@csrf_exempt
def check_access(request):
	url = "http://192.168.168.3"
	user_id = request.user.username.replace(".", "")

	# user_id = "false"
	# Construct the first query URL
	query = f"{url}/agc/api.php?source=test&user=ashish&pass=phone321&user_id={user_id}&function=agent_exists"

	try:
		response = requests.get(query)
		response.raise_for_status()
	except requests.RequestException as e:
		logger.error(f"Error during the first API call: {e}")
		return render(request, 'connection_app/customer-profile/vicidial_delivery_form.html',
					  {'processed_username': user_id})

	if "SUCCESS" in response.text:
		# Construct the second query URL
		query2 = f"{url}/vicidial/non_agent_api.php?source=test&user=ashish&pass=phone321&function=list_with_campaignId&campaign_id={user_id}"

		try:
			response2 = requests.get(query2)
			response2.raise_for_status()
		except requests.RequestException as e:
			logger.error(f"Error during the second API call: {e}")
			return render(request, 'connection_app/customer-profile/vicidial_delivery_form.html',
						  {'processed_username': user_id})

		if "ERROR" not in response2.text:
			print(f"the response we got is {response2.text}")
			return render(request, 'connection_app/customer-profile/vicidial_delivery_boy_panel.html',
						  {'processed_username': user_id})

	return render(request, 'connection_app/customer-profile/vicidial_delivery_form.html',
				  {'processed_username': user_id})


#  code of views.py
from django.http import JsonResponse
from .ak_jobs import VicidialService

#
# @method_decorator(login_required, 'dispatch')
# class CustomerProfileListView(ListView):
# 	model = CustomerProfile
# 	template_name = 'connection_app/customer-profile/customer_profile_listview.html'
# 	paginate_by = 20
# 	permission = 'has_view_permission'
#
# 	def __init__(self, **kwargs):
# 		super().__init__(**kwargs)
# 		self.service_area_list = []
# 		self.distributor_list = []
# 		self.inactive_customer_list = []
# 		self.active_customer_list = []
#
# 	def get_user_profile(self):
# 		try:
# 			return UserProfile.objects.get(user=self.request.user)
# 		except UserProfile.DoesNotExist:
# 			return None
#
# 	def load_customer_lists(self, request_data):
# 		user_profile = self.get_user_profile()
# 		if not user_profile:
# 			return False
#
# 		# Get filter parameters
# 		days = request_data.get('days', "30")
# 		now = timezone.now()
# 		try:
# 			days_ago = now - timedelta(days=int(days))
# 		except ValueError:
# 			days_ago = now - timedelta(days=30)
#
# 		# Get service areas and distributors
# 		self.service_area_list = request_data.getlist(
# 			'sdms_service_area') or user_profile.sdms_service_areas.values_list('area_name', flat=True)
# 		self.distributor_list = request_data.getlist('distributor') or user_profile.sdmsuser_set.values_list(
# 			'distributor__code', flat=True)
#
# 		# Get recent sales orders
# 		recent_sales_orders = SalesOrder.objects.filter(
# 			order_date__gte=days_ago
# 		).values("parent_id")
#
# 		# Load active customers
# 		self.active_customer_list = CustomerProfile.objects.filter(
# 			distributor_code__in=self.distributor_list,
# 			service_area__in=self.service_area_list,
# 			id__in=recent_sales_orders
# 		).distinct().order_by("id")
#
# 		# Load inactive customers
# 		self.inactive_customer_list = CustomerProfile.objects.filter(
# 			distributor_code__in=self.distributor_list,
# 			service_area__in=self.service_area_list
# 		).exclude(
# 			id__in=recent_sales_orders
# 		).order_by("id")
#
# 		return True
#
# 	def dispatch(self, request, *args, **kwargs):
# 		user_profile = self.get_user_profile()
# 		if not user_profile:
# 			return redirect('error_page')
# 		return super().dispatch(request, *args, **kwargs)
#
# 	def get_queryset(self):
# 		success = self.load_customer_lists(self.request.GET)
# 		if not success:
# 			return CustomerProfile.objects.none()
# 		return self.active_customer_list
#
# 	def get_context_data(self, *, object_list=None, **kwargs):
# 		context = super().get_context_data(object_list=object_list, **kwargs)
# 		user_profile = self.get_user_profile()
#
# 		# Set up filter form
# 		initial_data = {
# 			'sdms_service_area': self.request.GET.getlist('sdms_service_area')
# 		}
# 		if user_profile:
# 			context['filter_form'] = SDMSServiceAreaForm(user_profile=user_profile, data=initial_data)
#
# 		# Paginate active customers
# 		active_paginator = Paginator(self.active_customer_list, self.paginate_by)
# 		active_page = self.request.GET.get('page')
# 		try:
# 			active_customers = active_paginator.page(active_page)
# 		except PageNotAnInteger:
# 			active_customers = active_paginator.page(1)
# 		except EmptyPage:
# 			active_customers = active_paginator.page(active_paginator.num_pages)
# 		context['list_qs'] = active_customers
#
# 		# Paginate inactive customers
# 		inactive_paginator = Paginator(self.inactive_customer_list, self.paginate_by)
# 		inactive_page = self.request.GET.get('inactive_page')
# 		try:
# 			inactive_customers = inactive_paginator.page(inactive_page)
# 		except PageNotAnInteger:
# 			inactive_customers = inactive_paginator.page(1)
# 		except EmptyPage:
# 			inactive_customers = inactive_paginator.page(inactive_paginator.num_pages)
# 		context['inactive_customer_list'] = inactive_customers
#
# 		# Preserve query parameters
# 		query_params = self.request.GET.copy()
# 		query_params.pop('page', None)
# 		query_params.pop('inactive_page', None)
# 		context['query_params'] = query_params.urlencode()
# 		context['days'] = self.request.GET.get('days', "30")
# 		# Add filter information
# 		context['filters'] = {
# 			"Distributor": ", ".join(self.distributor_list),
# 			"Service Area": ", ".join(self.service_area_list)
# 		}
#
# 		return context
#
# 	def handle_vicidial(self, request):
# 		# Ensure lists are loaded before processing
# 		success = self.load_customer_lists(request.POST)
# 		if not success:
# 			return JsonResponse({
# 				"status": False,
# 				"message": "Failed to load customer data"
# 			})
#
# 		if not self.inactive_customer_list.exists():
# 			return JsonResponse({
# 				"status": False,
# 				"message": "No inactive customers found to export"
# 			})
#
# 		current_user = self.request.user
# 		Campaign_name = str(current_user).replace(".", "")
# 		resolve_Id = UserProfile.objects.get(user=current_user).id
# 		list_id = "88" + str(resolve_Id)
# 		send_inactive_to_vicidial = request.POST.get("add_to_vicidial", False)
#
# 		if not send_inactive_to_vicidial:
# 			return JsonResponse({
# 				"status": False,
# 				"message": "Export to ViciDial not requested"
# 			})
#
# 		# Prepare vicidial leads
# 		vicidial_leads = [
# 			{
# 				"phone_number": customer.mobile_number,
# 				"first_name": customer.name,
# 				"address1": customer.address,
# 				"address2": customer.consumer_no,
# 				"address3": customer.consumer_no,
# 			}
# 			for customer in self.inactive_customer_list
# 		]
#
# 		try:
# 			vicidial_service = VicidialService()
# 			isListExist = vicidial_service.list_info(list_id=list_id, agent_user=Campaign_name)
#
# 			if isListExist["status"] == "error":
# 				return JsonResponse({
# 					"status": False,
# 					"message": "Please use registered phone number"
# 				})
#
# 			if not isListExist["campaign"]:
# 				return JsonResponse({
# 					"status": False,
# 					"message": "Internal server error contact to admin"
# 				})
#
# 			response = vicidial_service.Add_leadsToVicidial(data=vicidial_leads, list_id=list_id)
# 			success = response.get("status", False)
#
# 			return JsonResponse({
# 				"status": success,
# 				"list_loaded_successfully": success,
# 				"message": response.get("message", "Operation completed")
# 			})
#
# 		except Exception as e:
# 			return JsonResponse({
# 				"status": False,
# 				"message": f"Error processing request: {str(e)}"
# 			})
#
# 	def post(self, request, *args, **kwargs):
# 		respnse_has = self.handle_vicidial(request)
# 		print(f"the response is {respnse_has}")
# 		return respnse_has
#

# # code of url.py

# # path('submit-delivery-boy-form/',
# #        views.submit_delivery_boy_form,
# #        name='submit_delivery_boy_form'
# # ),
# path('vicidial_webhook/',
# 	 ak_views.vicidial_webhook,
# 	 name='vicidial_webhook'
# 	 ),
# path('vicidial-signup/',
# 	 ak_views.DeliveryBoySignupView.as_view(),
# 	 name='vicidial-signup'
# 	 ),
# path("check-access/"
# 	 , ak_views.check_access,
# 	 name="check_access"
# 	 ),
# path('agent/action/<str:action>/',
# 	 ak_views.AgentActionView.as_view(),
# 	 name='agent_action'
# 	 ),
# path('load-data-list/',
# 	 ak_views.AgentActionView.as_view(),
# 	 name='agent_action'
# 	 ),
#
#
# # code of forms.py
#
# from django.core.exceptions import ValidationError
# import re
#
# # Validators
# def validate_no_special_characters(value):
#     if re.search(r'[!@#$%^&*(),.?":{}|<>]', value):
#         raise ValidationError("Special characters are not allowed in this field.")
#
# def validate_only_digits(value):
#     if not value.isdigit():
#         raise ValidationError("Only digits are allowed.")
#
# class VicidialDeliveryBoyForm(forms.Form):
#     agent_fullname = forms.CharField(
#         widget=forms.TextInput(attrs={
#             'class': 'form-control',
#             'placeholder': 'Full Name',
#             'required': True,
#             'id': 'fullname'
#         }),
#         label="Full Name",
#         validators=[validate_no_special_characters]
#     )
#
#     agent_user = forms.CharField(
#         max_length=8,
#         widget=forms.TextInput(attrs={
#             'class': 'form-control',
#             'placeholder': 'Username',
#             'readonly': True,
#             'required': True,
#             'id': 'username'
#         }),
#         label="Username",
#         help_text="Username should be alphanumeric without special characters."
#     )
#
#     agent_pass = forms.CharField(
#         widget=forms.PasswordInput(attrs={
#             'class': 'form-control',
#             'placeholder': 'Password',
#             'required': True,
#             'id': 'user-pass'
#         }),
#         label="Password",
#         help_text="Enter a secure password."
#     )
#
#     phone_number = forms.CharField(
#         min_length=10,
#         max_length=10,
#         widget=forms.TextInput(attrs={
#             'class': 'form-control',
#             'placeholder': 'Phone Number',
#             'required': True,
#             'id': 'phone_number'
#         }),
#         label="Phone Number",
#         validators=[validate_only_digits],
#         help_text="Phone number must be exactly 10 digits."
#     )
#
#     phone_login = forms.CharField(
#         widget=forms.TextInput(attrs={
#             'class': 'form-control',
#             'placeholder': 'Phone ID',
#             'required': True,
#             'id': 'phone_login'
#         }),
#         label="Phone ID",
#         validators=[validate_no_special_characters],
#         help_text="Phone ID should not contain special characters."
#     )
#
#     phone_pass = forms.CharField(
#         widget=forms.PasswordInput(attrs={
#             'class': 'form-control',
#             'placeholder': 'Phone Password',
#             'required': True,
#             'id': 'phone_pass'
#         }),
#         label="Phone Password",
#         help_text="Enter the phone password."
#     )
