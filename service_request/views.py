import datetime

import requests
from django.contrib.auth.decorators import login_required
from django.http import Http404
from django.shortcuts import render, redirect
# Create your views here.
from django.urls import reverse
from django.utils.decorators import method_decorator
from django.views.generic import FormView, ListView, TemplateView
from django_currentuser.middleware import get_current_user

from domestic_app.settings import CAMUNDA_WEB_ROOT_URL
from service_request.enums import ServiceRequestTypeStatusEnum, ServiceRequestTypeEnum
from service_request.forms import ServiceRequestReviewForm
from service_request.models import ServiceRequest
from ujjwala.models import UjjwalaV2Application
from ujjwala.ujjwala_functions import can_resolve_service_request


CAMUNDA_USER_TASK_ID_URL = f'{CAMUNDA_WEB_ROOT_URL}/camunda/app/tasklist/default/#/?task='


@method_decorator(login_required, 'dispatch')
class DashboardView(TemplateView):
	template_name = "connection_app/dashboard.html"

	def get_context_data(self, **kwargs):
		context = super().get_context_data(**kwargs)
		user = get_current_user()

		context.update({
			"user": user
			# "sales_order_portability_queryset": SalesOrderPortability.objects.filter(user=get_current_user()),
			# "sales_order_portability_status": SalesOrderPortabilityStatusEnum.choices
		})
		return context


@method_decorator(login_required, 'dispatch')
class ServiceRequestChangeAddressListView(ListView):
	model = ServiceRequest

	paginate_by = 20
	permission = 'has_view_permission'

	def dispatch(self, request, *args, **kwargs):
		user = get_current_user()
		if not can_resolve_service_request(user):
			return render(request, 'ujjwala/no_permissions.html')
		return super().dispatch(request, *args, **kwargs)

	def get_queryset(self):
		return ServiceRequest.objects.filter(status='PENDING',
		                                     service_request_type=ServiceRequestTypeEnum.UPDATE_ADDRESS).order_by('-id')

	def get_template_names(self):
		return 'service_request/service_request_listview.html'


@method_decorator(login_required, 'dispatch')
class ServiceRequestChangePhoneNumberListView(ListView):
	model = ServiceRequest

	paginate_by = 20
	permission = 'has_view_permission'

	def dispatch(self, request, *args, **kwargs):
		user = get_current_user()
		if not can_resolve_service_request(user):
			return render(request, 'ujjwala/no_permissions.html')
		return super().dispatch(request, *args, **kwargs)

	def get_queryset(self):
		return ServiceRequest.objects.filter(
			status='PENDING', service_request_type=ServiceRequestTypeEnum.CHANGE_PHONE_NUMBER).order_by('-id')

	def get_template_names(self):
		return 'service_request/service_request_listview.html'


@method_decorator(login_required, 'dispatch')
class ServiceRequestOthersListView(ListView):
	model = ServiceRequest

	paginate_by = 20
	permission = 'has_view_permission'

	def dispatch(self, request, *args, **kwargs):
		user = get_current_user()
		if not can_resolve_service_request(user):
			return render(request, 'ujjwala/no_permissions.html')
		return super().dispatch(request, *args, **kwargs)

	def get_queryset(self):
		return ServiceRequest.objects.filter(
			status='PENDING').exclude(
			service_request_type__in=[
				ServiceRequestTypeEnum.CHANGE_PHONE_NUMBER, ServiceRequestTypeEnum.UPDATE_ADDRESS
			]
		).order_by('-id')

	def get_template_names(self):
		return 'service_request/service_request_listview.html'


@method_decorator(login_required, 'dispatch')
class ServiceRequestView(FormView):
	template_name = 'service_request/service_request.html'
	form_class = ServiceRequestReviewForm

	def get_success_url(self):
		return reverse('service_request:index')

	def dispatch(self, request, *args, **kwargs):
		user = get_current_user()
		if not can_resolve_service_request(user):
			return render(request, 'ujjwala/no_permissions.html')
		return super().dispatch(request, *args, **kwargs)

	def get_object(self, queryset=None):
		try:
			obj = ServiceRequest.objects.get(pk=self.kwargs.get('pk'))
		except:
			raise Http404(
				"No Application Exist For Given Application Id"
			)
		return obj

	def get_context_data(self, **kwargs):
		context = super().get_context_data(**kwargs)
		obj = self.get_object()
		res = requests.get(
			f"https://camunda.dca.arungas.com/engine-rest/process-instance/{obj.camunda_process_id}/variables")
		res.raise_for_status()
		process_vars = res.json()

		request_app = process_vars.get('dca_app')

		application = UjjwalaV2Application.objects.get(pk=obj.form_data.get('application_id'))


		# for k, v in process_vars.items():
		# 	context[k] = v['value']

		context.update({
			"obj": obj,
			"application": application,
			"sr_request_template": "service_request/sr_" + obj.service_request_type.lower() + ".html",
		})
		return context

	# def get_form_class(self):
	# 	obj = self.get_object()
	#
	# 	if obj.service_request_type == ServiceRequestTypeEnum.UPDATE_ADDRESS:
	# 		return ReviewUpdatedAddressForm
	# 	elif obj.service_request_type == ServiceRequestTypeEnum.CHANGE_PHONE_NUMBER:
	# 		return ChangePhoneNumberForm
	# 	elif obj.service_request_type == ServiceRequestTypeEnum.CHANGE_CYLINDER_TO_14_2_KG:
	# 		return ChangeCylinderForm

	# def get_form_kwargs(self):
	# 	kwargs = super().get_form_kwargs()
	# 	obj = self.get_object()
	#
	# 	if obj.service_request_type == ServiceRequestTypeEnum.UPDATE_ADDRESS:
	# 		kwargs['initial'] = json.loads(obj.form_data['new_address'])
	# 	# elif obj.service_request_type == ServiceRequestTypeEnum.CHANGE_PHONE_NUMBER:
	# 	# 	kwargs['initial'] = json.loads(obj.form_data)
	#
	# 	return kwargs

	def form_valid(self, form):
		obj = self.get_object()
		obj.reviewed_by = get_current_user()
		obj.reviewed_on = datetime.datetime.now()
		obj.save()

		data = form.cleaned_data
		review_status = ServiceRequestTypeStatusEnum.REJECTED \
			if data['review_status'] == 'REJECTED' else ServiceRequestTypeStatusEnum.SUCCESS

		res = requests.get(f'{CAMUNDA_WEB_ROOT_URL}/engine-rest/task',
		                   params={'processInstanceId': f'{obj.camunda_process_id}',
		                           'taskDefinitionKey': 'Activity_verify_dca_service_request'})
		res.raise_for_status()

		res = requests.post(
			f"https://dca.arungas.com/engine-rest/task/{res.json()[0]['id']}/submit-form",
            json={
	            'variables': {
		            "review_status": {"value": review_status, "type": "String"},
		            "description": {"value": data.get('description'), "type": "String"},
		            "rejected_reason": {"value": data.get('rejected_reason'), "type": "String"},
                }
            }
		)
		res.raise_for_status()

		return redirect(self.get_success_url())


class MainMenuGridMenuView(TemplateView):
	template_name = 'ujjwala/grid_menu.html'

	def get_context_data(self, **kwargs):
		context = super().get_context_data(**kwargs)

		menu_items = [
				{
					"name": "Address",
					"icon": "fa fa-address-card",
					"url": reverse("service_request:service_request_change_address_list"),
				},
				{
					"name": "Phone Number",
					"icon": "fa fa-phone",
					"url": reverse("service_request:service_request_change_phone_number_list"),
				},
	             {
		             "name": "Others",
		             "icon": "fa fa-list-alt",
		             "url": reverse("service_request:service_request_others_list"),
	             },
				# {
				# 	"name": "Share Form Link",
				# 	"icon": "fa-share-square",
				# 	"url": reverse("ujjwala:share_web_form_link"),
				# },
			]

		# if can_process_change_cylinder_request(get_current_user()):
		# 	menu_items.append(
		# 		{
		# 			"name": "Change Cylinder",
		# 			"icon": "fa fa-exchange",
		# 			"url": reverse("ujjwala:change_cylinder_request_list"),
		# 		}
		# 	)

		context.update({
			"menu": {
				"name": "Main Menu",
				"items": menu_items
			}
		})
		return context