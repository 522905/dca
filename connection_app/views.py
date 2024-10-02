import logging

import django_filters
import django_rq
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.core.paginator import Paginator, PageNotAnInteger, EmptyPage
from django.http import Http404, HttpResponseRedirect
from django.shortcuts import render, redirect
from django.urls import reverse
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from django.views.generic import DetailView, ListView, FormView, TemplateView
from django_currentuser.middleware import get_current_user
from django_filters.views import FilterView


from connection_app.enums import PostInspectionStatusEnum, InspectionTypeEnum, PostInspectionActivityTypeEnum, \
	ConnectionApplicationDocumentsEnum
from connection_app.forms import UpdateAddressForm, PostInspectionStartForm, PreviewPostInspectionForm, \
	KitchenPostInspectionForm, PostInspectionForm, UIDPostInspectionForm, ProfilePhotoPostInspectionForm, \
	SurakshaPipePostInspectionForm, CustomerProfileSearchForm, GenerateLeadForm, GenerateNonCustomerLeadForm, \
	CustomerProfileDocumentUploadForm, SalesOrderDetailViewForm, SalesOrderPortabilityForm, SDMSServiceAreaForm
from connection_app.jobs import start_sales_order_portability_process
from connection_app.models import ConnectionApplication, PostInspection, CustomerProfile, Lead, SalesOrder, \
	SalesOrderPortability
from reference_data.models import ServiceType, Distributor
from teams.models import SDMSUser, UserProfile, SDMSServiceArea
from connection_app.filters import SalesOrderFilterSet
from connection_app.jobs import dialogflow_chat_assignment
from datetime import datetime, timedelta
from django.utils import timezone
logger = logging.getLogger(__name__)

def My_clinder_status(unique_id,phone_number):
	from ujjwala.models import FamilyMembers
	# Validate the input
	if not unique_id or len(unique_id) not in [10,12]:
		return "कृपया एक मान्य मोबाइल या उपभोक्ता नंबर दर्ज करें।"

	if len(unique_id) == 10:
		# Try to find the customer profile based on mobile number or consumer number
		application = CustomerProfile.objects.filter(mobile_number=unique_id).first() or \
					  CustomerProfile.objects.filter(consumer_no=unique_id).first()

	if len(unique_id) == 12:
		family_member = FamilyMembers.objects.filter(uid_no=unique_id).first()
		if not family_member:
			try:
				dialogflow_chat_assignment(phone_number)
				return "हम आपके कनेक्शन का विवरण ढूंढने में असमर्थ हैं, इसलिए हम आपको व्हाट्सएप पर हमारे ग्राहक सेवा से जोड़ रहे हैं"
			except Exception as e:
				logger.error(f"the issue in chat assignment {str(e)}")
				return "आपकी ऑर्डर जानकारी उपलब्ध नहीं है, कृपया अपनी ऑर्डर स्थिति की जांच करें। +91 161 520 1005"

		# TODO
		application = CustomerProfile.objects.filter(mobile_number=family_member.parent.sdms_mobile_number).first()

	if not application:
		return "हमें इस मोबाइल और उपभोक्ता नंबर के साथ कोई एप्लिकेशन नहीं मिला, कृपया अपना आधार कार्ड नंबर साझा करें।"

	# Check if the consumer number exists in the found application
	if not application.consumer_no:
		return "उपभोक्ता संख्या मान्य नहीं है, कृपया सही विवरण प्रदान करें।"

	# Find the related sales order
	saleorder = SalesOrder.objects.filter(relationship_id=application.consumer_id).order_by("-id").first()

	if not saleorder:
		return "आपकी कोई ऑर्डर जानकारी नहीं मिली, कृपया अपनी ऑर्डर स्थिति की जांच करें।"

	# Print debug information for development purposes
	print(saleorder.delivery_boy_full_name, saleorder.delivery_boy_login,saleorder.id, "the sale order details")

	# Ensure that saleorder has the necessary details
	if saleorder.order_status not in ["COMPLETED"]:
		try:
			# Retrieve delivery boy details using the delivery boy's login
			delivery_boy_details = SDMSUser.objects.get(delivery_boy_login=saleorder.delivery_boy_login)
			if delivery_boy_details and delivery_boy_details.parent:
				return f"आपके क्षेत्र के सिलेंडर डिलीवरी बॉय का नंबर {delivery_boy_details.parent.phone_number} है, " \
					   f"आपके सिलेंडर पहुंचने के समय के बारे में जानने के लिए कृपया उससे संपर्क करें।"
			else:
				return "डिलीवरी बॉय की जानकारी उपलब्ध नहीं है, कृपया बाद में पुनः प्रयास करें।"
		except SDMSUser.DoesNotExist:
			return "डिलीवरी बॉय की लॉगिन जानकारी मान्य नहीं है, कृपया बाद में पुनः प्रयास करें।"
		except SDMSUser.MultipleObjectsReturned:
			return "डिलीवरी बॉय की लॉगिन जानकारी के लिए कई रिकॉर्ड्स पाए गए, कृपया सहायता केंद्र से संपर्क करें।"
		except Exception as e:
			# Log any unexpected exception for debugging
			print(f"Unexpected error: {e}")
			return "सिस्टम में कुछ गड़बड़ी हो गई है, कृपया बाद में पुनः प्रयास करें।"

	return "आपकी ऑर्डर जानकारी उपलब्ध नहीं है, कृपया अपनी ऑर्डर स्थिति की जांच करें। +91 161 520 1005"


def installation_upload_process_gleam_entry_gate(request):
	application_id = request.GET.get("application_id")
	response = render(request, 'connection_app/fblike.html')
	response.set_cookie('application_id_cookie', application_id)
	return response


def installation_upload_process_gleam_entry_gate_completed(request):
	application_id = request.COOKIES.get('application_id_cookie')
	return redirect('installation_start', pk=application_id)


def index(request):
	# return RedirectView.as_view(url='/connection_app/portal/user_dashboard/', permanent=False)
	return render(request, 'connection_app/index.html')


def web_form_view(request):
	return render(request, "connection_app/web_form.html")
	# def get_context_data(self, **kwargs):
	#     context_data = super().get(**kwargs)
	#     form_fill_area_list = FormFillArea.objects.all()
	#     context_data = context_data.update({
	#         "form_fill_area_list": form_fill_area_list
	#     })
	#     return context_data


class ApplicationStatusView(DetailView):
	model = ConnectionApplication

	def get_template_names(self):
		return 'connection_app/status.html'


class ApplicationReuploadView(DetailView):
	model = ConnectionApplication

	def get_template_names(self):
		return 'connection_app/pendingdata.html'


class ApplicationInstallationView(DetailView):
	model = ConnectionApplication

	def get_template_names(self):
		return 'connection_app/kitchenphoto.html'


@method_decorator(login_required, 'dispatch')
class PostInspectionListView(ListView):
	model = PostInspection
	template_name = 'connection_app/post-inspection/post_inspection_listview.html'

	paginate_by = 20
	permission = 'has_view_permission'

	def get_queryset(self):
		user: User = get_current_user()
		filters = {}
		if not user.is_superuser:
			filters.update({'mechanic': user})
		return PostInspection.objects.filter(**filters).order_by('-submitted_on')


@method_decorator(login_required, 'dispatch')
class PostInspectionStartFormView(FormView):
	model = PostInspection
	template_name = 'connection_app/post-inspection/post_inspection_start_form.html'
	form_class = PostInspectionStartForm

	def form_valid(self, form):
		data = form.cleaned_data

		customer_profile: object = None

		if data.get('consumer_id'):
			customer_profile: CustomerProfile = CustomerProfile.objects.filter(
				consumer_id=data.get('consumer_id')
			).first()

		if not customer_profile:
			if data.get('mobile_number'):
				customer_profile: CustomerProfile = CustomerProfile.objects.filter(
					mobile_number=data.get('mobile_number')
				).first()
				if not customer_profile:
					messages.add_message(
						self.request, messages.ERROR, "No customer found for given mobile number"
					)
					return redirect('connection_app:post_inspection_start')
			else:
				messages.add_message(
					self.request, messages.ERROR, "No customer found for given consumer id"
				)
				return redirect('connection_app:post_inspection_start')

		pi_obj = PostInspection.objects.filter(parent=customer_profile).first()
		if not pi_obj:
			pi_obj = PostInspection.objects.create(
				parent=customer_profile,
				status=PostInspectionStatusEnum.STARTED,
				type=InspectionTypeEnum.MECHANIC,
				mechanic=get_current_user()
			)
			pi_obj.activities.create(activity_type=PostInspectionActivityTypeEnum.KITCHEN_PHOTO_UPDATE)
			pi_obj.activities.create(activity_type=PostInspectionActivityTypeEnum.MAIN_GATE_PHOTO_UPDATE)
			pi_obj.activities.create(activity_type=PostInspectionActivityTypeEnum.PROFILE_PHOTO_UPDATE)
			pi_obj.activities.create(activity_type=PostInspectionActivityTypeEnum.ADDRESS_UPDATE)
			pi_obj.activities.create(activity_type=PostInspectionActivityTypeEnum.UID_PHOTO_UPDATE)
			pi_obj.activities.create(activity_type=PostInspectionActivityTypeEnum.SURAKSHA_PIPE_UPDATE)
			pi_obj.save()

		return redirect('post_inspection_form_view', pk=pi_obj.pk)


@method_decorator(login_required, 'dispatch')
@method_decorator(csrf_exempt, 'dispatch')
class PostInspectionView(FormView):
	model = PostInspection
	template_name = 'connection_app/post-inspection/post_inspection_form.html'
	form_class = PostInspectionForm
	success_url = '.'

	def dispatch(self, request, *args, **kwargs):
		post_inspection = self.get_object()
		if post_inspection.status in (
				PostInspectionStatusEnum.SUBMITTED,
				PostInspectionStatusEnum.ACCEPTED,
		):
			return render(self.request, 'connection_app/post-inspection/post_inspection_status.html', context={
				'post_inspection': post_inspection
			})
		return super().dispatch(request, *args, **kwargs)

	def get_object(self, queryset=None):
		try:
			obj = PostInspection.objects.get(pk=self.kwargs.get('pk'))
		except:
			raise Http404(
				"No %(verbose_name)s found matching the query" %
				{'verbose_name': queryset.model._meta.verbose_name}
			)
		return obj

	def form_valid(self, form):
		return HttpResponseRedirect(self.get_success_url())

	def form_invalid(self, form):
		for error in form.errors.get('__all__'):
			messages.add_message(self.request, messages.ERROR, error)
		return HttpResponseRedirect(".")

	def get_form_kwargs(self):
		kwargs = super().get_form_kwargs()
		kwargs['post_inspection'] = self.get_object()
		return kwargs

	def get_context_data(self, **kwargs):
		context = super().get_context_data(**kwargs)
		post_inspection = self.get_object()
		context.update({
			'post_inspection': post_inspection,
			'customer_profile': self.get_object().parent,
			'profile_photo_update': post_inspection.activities.filter(
				activity_type=PostInspectionActivityTypeEnum.PROFILE_PHOTO_UPDATE).first(),
			'uid_photo_update': post_inspection.activities.filter(
				activity_type=PostInspectionActivityTypeEnum.UID_PHOTO_UPDATE).first(),
			'address_update': post_inspection.activities.filter(
				activity_type=PostInspectionActivityTypeEnum.ADDRESS_UPDATE).first(),
			'kitchen_photo_update': post_inspection.activities.filter(
				activity_type=PostInspectionActivityTypeEnum.KITCHEN_PHOTO_UPDATE).first(),
			'main_gate_photo_update': post_inspection.activities.filter(
				activity_type=PostInspectionActivityTypeEnum.MAIN_GATE_PHOTO_UPDATE).first(),
			'suraksha_pipe_update': post_inspection.activities.filter(
				activity_type=PostInspectionActivityTypeEnum.SURAKSHA_PIPE_UPDATE).first()
		})
		return context


@method_decorator(login_required, 'dispatch')
@method_decorator(csrf_exempt, 'dispatch')
class PostInspectionAddressUpdateView(FormView):
	model = PostInspection
	template_name = 'connection_app/post-inspection/update_address.html'
	form_class = UpdateAddressForm
	success_url = '.'

	def dispatch(self, request, *args, **kwargs):
		post_inspection = self.get_object()
		if post_inspection.activities.filter(
			activity_type=PostInspectionActivityTypeEnum.ADDRESS_UPDATE).first().completed:
			return render(
				self.request, "connection_app/response.html",
				{"heading": "Post Inspection", "message": "Address Already Updated".format(kwargs.get('pk'))}
			)
		if post_inspection.status in (
				PostInspectionStatusEnum.SUBMITTED,
				PostInspectionStatusEnum.ACCEPTED,
		):
			return render(self.request, 'connection_app/post-inspection/post_inspection_status.html', context={
				'post_inspection': post_inspection
			})
		return super().dispatch(request, *args, **kwargs)

	def get_object(self, queryset=None):
		try:
			obj = PostInspection.objects.get(pk=self.kwargs.get('pk'))
		except:
			raise Http404(
				"No %(verbose_name)s found matching the query" %
				{'verbose_name': queryset.model._meta.verbose_name}
			)
		return obj

	def form_valid(self, form):
		form.save()
		return redirect('post_inspection_form_view', pk=self.get_object().pk)

	def get_form_kwargs(self):
		kwargs = super().get_form_kwargs()
		kwargs['post_inspection'] = self.get_object()
		return kwargs

	def get_context_data(self, **kwargs):
		context = super().get_context_data(**kwargs)
		post_inspection = self.get_object()
		context.update({
			'post_inspection': post_inspection,
			'customer_profile': self.get_object().parent,
		})
		return context


@method_decorator(login_required, 'dispatch')
@method_decorator(csrf_exempt, 'dispatch')
class PostInspectionKitchenPhotoUpdateView(FormView):
	model = PostInspection
	template_name = 'connection_app/post-inspection/update_kitchen_photo.html'
	form_class = KitchenPostInspectionForm
	success_url = '.'

	def dispatch(self, request, *args, **kwargs):
		post_inspection = self.get_object()
		if post_inspection.activities.filter(
			activity_type=PostInspectionActivityTypeEnum.KITCHEN_PHOTO_UPDATE).first().completed:
			return render(
				self.request, "connection_app/response.html",
				{"heading": "Post Inspection", "message": "Kitchen Photo Already Updated".format(kwargs.get('pk'))}
			)
		if post_inspection.status in (
				PostInspectionStatusEnum.SUBMITTED,
				PostInspectionStatusEnum.ACCEPTED,
		):
			return render(self.request, 'connection_app/post-inspection/post_inspection_status.html', context={
				'post_inspection': post_inspection
			})
		return super().dispatch(request, *args, **kwargs)

	def get_object(self, queryset=None):
		try:
			obj = PostInspection.objects.get(pk=self.kwargs.get('pk'))
		except:
			raise Http404(
				"No %(verbose_name)s found matching the query" %
				{'verbose_name': queryset.model._meta.verbose_name}
			)
		return obj

	def form_valid(self, form):
		form.save()
		return redirect('post_inspection_form_view', pk=self.get_object().pk)

	def get_form_kwargs(self):
		kwargs = super().get_form_kwargs()
		kwargs['post_inspection'] = self.get_object()
		return kwargs

	def get_context_data(self, **kwargs):
		context = super().get_context_data(**kwargs)
		post_inspection = self.get_object()
		context.update({
			'post_inspection': post_inspection,
			'customer_profile': self.get_object().parent,
		})
		return context


@method_decorator(login_required, 'dispatch')
@method_decorator(csrf_exempt, 'dispatch')
class PostInspectionMainGatePhotoUpdateView(FormView):
	model = PostInspection
	template_name = 'connection_app/post-inspection/update_main_gate_photo.html'
	form_class = PreviewPostInspectionForm
	success_url = '.'

	def dispatch(self, request, *args, **kwargs):
		post_inspection = self.get_object()
		if post_inspection.activities.filter(
			activity_type=PostInspectionActivityTypeEnum.MAIN_GATE_PHOTO_UPDATE).first().completed:
			return render(
				self.request, "connection_app/response.html",
				{"heading": "Post Inspection", "message": "Main Gate Photo Already Updated".format(kwargs.get('pk'))}
			)
		if post_inspection.status in (
				PostInspectionStatusEnum.SUBMITTED,
				PostInspectionStatusEnum.ACCEPTED,
		):
			return render(self.request, 'connection_app/post-inspection/post_inspection_status.html', context={
				'post_inspection': post_inspection
			})
		return super().dispatch(request, *args, **kwargs)

	def get_object(self, queryset=None):
		try:
			obj = PostInspection.objects.get(pk=self.kwargs.get('pk'))
		except:
			raise Http404(
				"No %(verbose_name)s found matching the query" %
				{'verbose_name': queryset.model._meta.verbose_name}
			)
		return obj

	def form_valid(self, form):
		form.save()
		return redirect('post_inspection_form_view', pk=self.get_object().pk)

	def get_form_kwargs(self):
		kwargs = super().get_form_kwargs()
		kwargs['post_inspection'] = self.get_object()
		return kwargs

	def get_context_data(self, **kwargs):
		context = super().get_context_data(**kwargs)
		post_inspection = self.get_object()
		context.update({
			'post_inspection': post_inspection,
			'customer_profile': self.get_object().parent,
		})
		return context


@method_decorator(login_required, 'dispatch')
@method_decorator(csrf_exempt, 'dispatch')
class PostInspectionUIDPhotoUpdateView(FormView):
	model = PostInspection
	template_name = 'connection_app/post-inspection/update_uid_photo.html'
	form_class = UIDPostInspectionForm
	success_url = '.'

	def dispatch(self, request, *args, **kwargs):
		post_inspection = self.get_object()
		if post_inspection.activities.filter(
			activity_type=PostInspectionActivityTypeEnum.UID_PHOTO_UPDATE).first().completed:
			return render(
				self.request, "connection_app/response.html",
				{"heading": "Post Inspection", "message": "UID Photos Already Updated".format(kwargs.get('pk'))}
			)
		if post_inspection.status in (
				PostInspectionStatusEnum.SUBMITTED,
				PostInspectionStatusEnum.ACCEPTED,
		):
			return render(self.request, 'connection_app/post-inspection/post_inspection_status.html', context={
				'post_inspection': post_inspection
			})
		return super().dispatch(request, *args, **kwargs)

	def get_object(self, queryset=None):
		try:
			obj = PostInspection.objects.get(pk=self.kwargs.get('pk'))
		except:
			raise Http404(
				"No %(verbose_name)s found matching the query" %
				{'verbose_name': queryset.model._meta.verbose_name}
			)
		return obj

	def form_valid(self, form):
		form.save()
		return redirect('post_inspection_form_view', pk=self.get_object().pk)

	def get_form_kwargs(self):
		kwargs = super().get_form_kwargs()
		kwargs['post_inspection'] = self.get_object()
		return kwargs

	def get_context_data(self, **kwargs):
		context = super().get_context_data(**kwargs)
		post_inspection = self.get_object()
		context.update({
			'post_inspection': post_inspection,
			'customer_profile': self.get_object().parent,
		})
		return context


@method_decorator(login_required, 'dispatch')
@method_decorator(csrf_exempt, 'dispatch')
class PostInspectionProfilePhotoUpdateView(FormView):
	model = PostInspection
	template_name = 'connection_app/post-inspection/update_profile_photo.html'
	form_class = ProfilePhotoPostInspectionForm
	success_url = '.'

	def dispatch(self, request, *args, **kwargs):
		post_inspection = self.get_object()
		if post_inspection.activities.filter(
			activity_type=PostInspectionActivityTypeEnum.PROFILE_PHOTO_UPDATE).first().completed:
			return render(
				self.request, "connection_app/response.html",
				{"heading": "Post Inspection", "message": "Profile Photo Already Updated".format(kwargs.get('pk'))}
			)
		if post_inspection.status in (
				PostInspectionStatusEnum.SUBMITTED,
				PostInspectionStatusEnum.ACCEPTED,
		):
			return render(self.request, 'connection_app/post-inspection/post_inspection_status.html', context={
				'post_inspection': post_inspection
			})
		return super().dispatch(request, *args, **kwargs)

	def get_object(self, queryset=None):
		try:
			obj = PostInspection.objects.get(pk=self.kwargs.get('pk'))
		except:
			raise Http404(
				"No %(verbose_name)s found matching the query" %
				{'verbose_name': queryset.model._meta.verbose_name}
			)
		return obj

	def form_valid(self, form):
		form.save()
		return redirect('post_inspection_form_view', pk=self.get_object().pk)

	def get_form_kwargs(self):
		kwargs = super().get_form_kwargs()
		kwargs['post_inspection'] = self.get_object()
		return kwargs

	def get_context_data(self, **kwargs):
		context = super().get_context_data(**kwargs)
		post_inspection = self.get_object()
		context.update({
			'post_inspection': post_inspection,
			'customer_profile': self.get_object().parent,
		})
		return context


@method_decorator(login_required, 'dispatch')
@method_decorator(csrf_exempt, 'dispatch')
class PostInspectionSurakshaPipeUpdateView(FormView):
	model = PostInspection
	template_name = 'connection_app/post-inspection/update_suraksha_pipe.html'
	form_class = SurakshaPipePostInspectionForm
	success_url = '.'

	def dispatch(self, request, *args, **kwargs):
		post_inspection = self.get_object()
		if post_inspection.activities.filter(
			activity_type=PostInspectionActivityTypeEnum.SURAKSHA_PIPE_UPDATE).first().completed:
			return render(
				self.request, "connection_app/response.html",
				{"heading": "Post Inspection", "message": "Suraksha Pipe Already Updated".format(kwargs.get('pk'))}
			)

		if post_inspection.status in (
				PostInspectionStatusEnum.SUBMITTED,
				PostInspectionStatusEnum.ACCEPTED,
		):
			return render(self.request, 'connection_app/post-inspection/post_inspection_status.html', context={
				'post_inspection': post_inspection
			})
		return super().dispatch(request, *args, **kwargs)

	def get_object(self, queryset=None):
		try:
			obj = PostInspection.objects.get(pk=self.kwargs.get('pk'))
		except:
			raise Http404(
				"No %(verbose_name)s found matching the query" %
				{'verbose_name': queryset.model._meta.verbose_name}
			)
		return obj

	def form_valid(self, form):
		form.save()
		return redirect('post_inspection_form_view', pk=self.get_object().pk)

	def form_invalid(self, form):
		print(form.errors)
		return redirect('post_inspection_form_view', pk=self.get_object().pk)

	def get_form_kwargs(self):
		kwargs = super().get_form_kwargs()
		kwargs['post_inspection'] = self.get_object()
		return kwargs

	def get_context_data(self, **kwargs):
		context = super().get_context_data(**kwargs)
		post_inspection = self.get_object()
		context.update({
			'post_inspection': post_inspection,
			'customer_profile': self.get_object().parent,
		})
		return context


@method_decorator(login_required, 'dispatch')
class CustomerProfileSearchView(FormView):
	template_name = "connection_app/customer_profile_search.html"
	form_class = CustomerProfileSearchForm

	def form_valid(self, form):
		data = form.cleaned_data

		cp_obj = None
		if data.get('consumer_id'):
			cp_obj = CustomerProfile.objects.filter(consumer_id=data.get('consumer_id')).first()
		elif data.get('mobile_number'):
			cp_obj = CustomerProfile.objects.filter(mobile_number=data.get('mobile_number')).first()
		# elif data.get('customer_profile_id'):
		# 	cp_obj = CustomerProfile.objects.filter(pk=data.get('customer_profile_id')).first()

		if not cp_obj:
			messages.add_message(
				self.request, messages.ERROR, "No Record Found For Given Consumer Id or Mobile Number"
			)
			return HttpResponseRedirect(".")

		return redirect('customer_profile', pk=cp_obj.pk)


@method_decorator(login_required, 'dispatch')
class CustomerProfileView(TemplateView):
	template_name = 'connection_app/customer_profile.html'

	def get_object(self, queryset=None):
		try:
			obj = CustomerProfile.objects.get(pk=self.kwargs.get('pk'))
		except:
			raise Http404(
				"No Customer Profile Exist For Given Id"
			)
		return obj

	def get_context_data(self, **kwargs):
		context = super().get_context_data(**kwargs)

		obj: CustomerProfile = self.get_object()
		context.update({
			"obj": obj,
		})
		return context


@method_decorator(login_required, 'dispatch')
@method_decorator(csrf_exempt, 'dispatch')
class GenerateLeadFormView(FormView):
	model = CustomerProfile
	template_name = 'connection_app/generate_lead_form.html'
	form_class = GenerateLeadForm
	success_url = '.'

	def get_object(self, queryset=None):
		try:
			obj = CustomerProfile.objects.get(pk=self.kwargs.get('pk'))
		except:
			raise Http404(
				"No %(verbose_name)s found matching the query" %
				{'verbose_name': queryset.model._meta.verbose_name}
			)
		return obj

	def form_valid(self, form):
		data = form.cleaned_data
		customer_profile = self.get_object()
		for service_type in data['service_list']:
			Lead.objects.create(
				parent=self.get_object(),
				generated_by=get_current_user(),
				service_type=ServiceType.objects.get(name=service_type),
				name=customer_profile.name,
				mobile_number=customer_profile.mobile_number
			)
		messages.add_message(self.request, messages.INFO,
							 message="Generated Lead Successfully For {}".format(", ".join(data['service_list'])))
		return redirect("customer_profile", pk=self.get_object().pk)

	def get_form_kwargs(self):
		kwargs = super().get_form_kwargs()
		kwargs['service_type_choices'] = tuple(ServiceType.objects.all().values_list('name', 'name'))
		return kwargs

	def get_context_data(self, **kwargs):
		context = super().get_context_data(**kwargs)
		context.update({
			'customer_profile': self.get_object(),
		})
		return context


@method_decorator(login_required, 'dispatch')
@method_decorator(csrf_exempt, 'dispatch')
class GenerateNonCustomerLeadFormView(FormView):
	template_name = 'connection_app/generate_non_customer_lead_form.html'
	form_class = GenerateNonCustomerLeadForm
	success_url = '.'

	def form_valid(self, form):
		data = form.cleaned_data
		for service_type in data['service_list']:
			Lead.objects.create(
				parent=self.get_object(),
				generated_by=get_current_user(),
				service_type=ServiceType.objects.get(name=service_type),
				name=data['name'],
				mobile_number=data['mobile_number']
			)
		messages.add_message(self.request, messages.INFO,
							 message="Generated Lead Successfully For {}".format(", ".join(data['service_list'])))
		return redirect("customer_profile", pk=self.get_object().pk)

	def get_form_kwargs(self):
		kwargs = super().get_form_kwargs()
		kwargs['service_type_choices'] = tuple(ServiceType.objects.all().values_list('name', 'name'))
		return kwargs


@method_decorator(login_required, 'dispatch')
@method_decorator(csrf_exempt, 'dispatch')
class CustomerProfileDocumentUploadFormView(FormView):
	template_name = 'connection_app/customer_profile_document_upload.html'
	form_class = CustomerProfileDocumentUploadForm
	success_url = '.'

	def get_object(self, queryset=None):
		try:
			obj = CustomerProfile.objects.get(pk=self.kwargs.get('pk'))
		except:
			raise Http404(
				"No %(verbose_name)s found matching the query" %
				{'verbose_name': queryset.model._meta.verbose_name}
			)
		return obj

	def dispatch(self, request, *args, **kwargs):
		customer_profile = self.get_object()

		if customer_profile.documents.filter(type=ConnectionApplicationDocumentsEnum.BANK_SUBSIDY_CERTIFICATE_PHOTO).first():
			messages.add_message(self.request, messages.INFO,
								 f"Bank Subsidy Certificate Document Already Submitted.")
			return redirect("customer_profile", pk=self.get_object().pk)
		return super().dispatch(request, *args, **kwargs)

	def form_valid(self, form):
		data = form.cleaned_data

		customer_profile = self.get_object()
		customer_profile.documents.create(
			type=data['document_type'], link=data['document_link']
		)
		messages.add_message(self.request, messages.INFO, f"{data['document_type']} Document Uploaded Successfully.")
		return redirect("customer_profile", pk=self.get_object().pk)

	def get_context_data(self, **kwargs):
		context = super().get_context_data()
		context.update({
			"customer_profile": self.get_object()
		})
		return context

	def get_form_kwargs(self):
		kwargs = super().get_form_kwargs()
		kwargs['initial'] = {'document_type': ConnectionApplicationDocumentsEnum.BANK_SUBSIDY_CERTIFICATE_PHOTO}
		return kwargs


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


class SalesOrderFilter(django_filters.FilterSet):
	class Meta:
		model = SalesOrder
		fields = ['sales_order', 'consumer_name', 'hide_from_view']


@method_decorator(login_required, 'dispatch')
class SalesOrderListView(FilterView):
	model = SalesOrder
	template_name = 'connection_app/sales-order/sales_order_listview.html'

	paginate_by = 10
	permission = 'has_view_permission'
	filterset_class = SalesOrderFilter

	def get_context_data(self, **kwargs):
		context = super().get_context_data(**kwargs)
		queryset = self.get_queryset()
		paginator = Paginator(queryset, self.paginate_by)
		page_number = self.request.GET.get('page')
		page_obj = paginator.get_page(page_number)
		context['page_obj'] = page_obj
		return context

	def get_queryset(self):
		current_user = get_current_user()
		qs = SalesOrder.objects.filter(auto_generated=True).order_by('order_date')

		if self.request.GET.get('show_hidden_records') != 'on':
			qs = qs.exclude(hide_from_view=True)

		if current_user.is_superuser:
			return qs

		sdms_user: SDMSUser = SDMSUser.objects.filter(
			parent__user=current_user,
			distributor__name='Arun Indane'
		).first()

		if not sdms_user:
			return SalesOrder.objects.none()

		qs = qs.objects.filter(delivery_boy_login=sdms_user.delivery_boy_login)

		return qs.order_by('order_date')

 
@method_decorator(login_required, 'dispatch')
@method_decorator(csrf_exempt, 'dispatch')
class SalesOrderDetailFormView(FormView):
	template_name = 'connection_app/sales-order/sales_order_detail_view.html'
	form_class = SalesOrderDetailViewForm
	success_url = '.'

	def get_object(self, queryset=None):
		try:
			obj = SalesOrder.objects.get(pk=self.kwargs.get('pk'))
		except:
			raise Http404(
				"No %(verbose_name)s found matching the query" %
				{'verbose_name': queryset.model._meta.verbose_name}
			)
		return obj

	def form_valid(self, form):
		data = form.cleaned_data
		so_obj = self.get_object()
		so_obj.parent.do_not_auto_generate = data['cancel_auto_booking']
		so_obj.parent.save()
		return redirect("sales_order_list")

	def get_context_data(self, **kwargs):
		context = super().get_context_data()
		context.update({
			"sales_order": self.get_object()
		})
		return context


@method_decorator(login_required, 'dispatch')
class CustomerProfileContactsView(TemplateView):

	template_name = "connection_app/customer_profile_contacts.html"

	def get_object(self, queryset=None):
		try:
			obj = CustomerProfile.objects.get(pk=self.kwargs.get('pk'))
		except:
			raise Http404(
				"No %(verbose_name)s found matching the query" %
				{'verbose_name': queryset.model._meta.verbose_name}
			)
		return obj

	def get_context_data(self, **kwargs):
		context = super().get_context_data(**kwargs)
		context.update({
			"obj": self.get_object()
		})
		return context


@method_decorator(login_required, 'dispatch')
@method_decorator(csrf_exempt, 'dispatch')
class SalesOrderPortabilityFormView(FormView):
	template_name = 'connection_app/sales-order/sales_order_portability.html'
	form_class = SalesOrderPortabilityForm
	success_url = '.'

	def get_object(self, queryset=None):
		try:
			obj = SalesOrder.objects.get(pk=self.kwargs.get('pk'))
		except:
			raise Http404(
				"No %(verbose_name)s found matching the query" %
				{'verbose_name': queryset.model._meta.verbose_name}
			)
		return obj

	def form_valid(self, form):
		data = form.cleaned_data
		sop_obj: SalesOrderPortability = SalesOrderPortability.objects.create(
			sales_order_number=data['sales_order_number'],
			user=get_current_user(),
			distributor_id=data['distributor']
		)
		messages.add_message(self.request, messages.INFO,
							 f"Sales Order Portability Request Initiated. Request Id: {sop_obj.pk}")
		django_rq.enqueue(start_sales_order_portability_process, args=(sop_obj.id,))
		return redirect("connection_app:sales_order_grid_menu_view")

	def get_form_kwargs(self):
		kwargs = super().get_form_kwargs()
		distributor_list = [('', 'Please Select Distributor')]
		distributor_list.extend([
				(obj.id, f"{obj.code} - {obj.name}") for obj in Distributor.objects.all()
			])
		kwargs['distributor_list'] = distributor_list
		return kwargs


class CustomerGridMenuView(TemplateView):
	template_name = 'connection_app/grid_menu.html'

	def get_context_data(self, **kwargs):
		context = super().get_context_data(**kwargs)

		menu = {
			"name": "Customer",
			"items": [
				{
					"name": "Customer Profile",
					"icon": "fa-user",
					"url": reverse("connection_app:customer_profile_search"),
				},
				{
					"name": "Generate Lead",
					"icon": "fa-star",
					"url": reverse("connection_app:customer_profile_search"),
				},
			]
		}

		context.update({
			"menu": menu
		})
		return context


class InspectionGridMenuView(TemplateView):
	template_name = 'connection_app/grid_menu.html'

	def get_context_data(self, **kwargs):
		context = super().get_context_data(**kwargs)

		menu = {
			"name": "Inspection",
			"items": [
				{
					"name": "Start Post Inspection",
					"icon": "fa-user-secret",
					"url": reverse("connection_app:post_inspection_start"),
				},
				{
					"name": "Post Inspection List",
					"icon": "fa-bars",
					"url": reverse("connection_app:post_inspection_list"),
				},
			]
		}

		context.update({
			"menu": menu
		})
		return context


class SalesOrderGridMenuView(TemplateView):
	template_name = 'connection_app/grid_menu.html'

	def get_context_data(self, **kwargs):
		context = super().get_context_data(**kwargs)

		menu = {
			"name": "Sales Order",
			"items": [
				{
					"name": "Sales Order List",
					"icon": "fa-book",
					"url": reverse("connection_app:sales_order_list"),
				},
				{
					"name": "Invoice Sales Order",
					"icon": "fa-credit-card",
					"url": reverse("connection_app:sales_order_portability"),
				},
				{
					"name": "Portability List",
					"icon": "fa-bars",
					"url": reverse("connection_app:sales_order_portability_list"),
				},
				{
					"name": "Customer List",
					"icon": "fa-bars",
					"url": reverse("connection_app:customer_profile_list"),
				}
			]
		}

		context.update({
			"menu": menu
		})
		return context


@method_decorator(login_required, 'dispatch')
class SalesOrderPortabilityListView(ListView):
	model = SalesOrderPortability
	template_name = 'connection_app/sales-order/sales_order_portability_listview.html'

	paginate_by = 20
	permission = 'has_view_permission'

	#
	# def dispatch(self, request, *args, **kwargs):
	# 	if request.method == 'POST':
	# 		return redirect(reverse("connection_app:sales_order_list") + "?hide_from_view={}".format("on"))
	# 	return super().dispatch(request, *args, **kwargs)

	def get_queryset(self):
		current_user = get_current_user()

		if current_user.is_superuser:
			return SalesOrderPortability.objects.all()
		else:
			return SalesOrderPortability.objects.filter(user=get_current_user())

	def get_context_data(self, *, object_list=None, **kwargs):
		context = super().get_context_data(object_list=object_list, **kwargs)
		list_qs = self.get_queryset()
		paginator = Paginator(list_qs, self.paginate_by)

		page = self.request.GET.get('page')

		try:
			list_qs = paginator.page(page)
		except PageNotAnInteger:
			list_qs = paginator.page(1)
		except EmptyPage:
			list_qs = paginator.page(paginator.num_pages)
		context['list_qs'] = list_qs

		return context

@method_decorator(login_required, 'dispatch')
class CustomerProfileListView(ListView):
    model = CustomerProfile
    template_name = 'connection_app/customer-profile/customer_profile_listview.html'

    paginate_by = 20
    permission = 'has_view_permission'

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.service_area_list = []
        self.distributor_list = []
        self.inactive_customer_list = []

    def dispatch(self, request, *args, **kwargs):
        current_user = get_current_user()
        user_profile = UserProfile.objects.get(user=current_user)

        if not user_profile:
            return

        return super().dispatch(request, *args, **kwargs)

    def get_queryset(self):
        current_user = get_current_user()
        user_profile = UserProfile.objects.get(user=current_user)
        days = self.request.GET.get('days', "30")
        now = timezone.now()
        days_ago = now - timedelta(days=int(days) if days else 30)

        self.service_area_list = user_profile.sdms_service_areas.values_list('area_name', flat=True)
        self.distributor_list = user_profile.sdmsuser_set.values_list('distributor__code', flat=True)

        # Apply filters from the request (GET method)
        if self.request.method == 'GET':
            self.service_area_list = self.request.GET.getlist('sdms_service_area') or self.service_area_list
            self.distributor_list = self.request.GET.getlist('distributor') or self.distributor_list

        # Get recent sales orders (placed in the last X days)
        recent_sales_orders = SalesOrder.objects.filter(order_date__gte=days_ago).values("parent_id")

        # Filter active customers (placed orders in the last 30 days)
        active_customers = CustomerProfile.objects.filter(
            distributor_code__in=self.distributor_list,
            service_area__in=self.service_area_list,
            id__in=recent_sales_orders
        ).distinct().order_by("id")

        # Filter inactive customers (no orders in the last 30 days)
        self.inactive_customer_list = CustomerProfile.objects.filter(
            distributor_code__in=self.distributor_list,
            service_area__in=self.service_area_list
        ).exclude(
            id__in=recent_sales_orders
        ).order_by("id")

        return active_customers

    def get_context_data(self, *, object_list=None, **kwargs):
        context = super().get_context_data(object_list=object_list, **kwargs)
        initial_data = {
            'sdms_service_area': self.request.GET.getlist('sdms_service_area')
        }
        context['filter_form'] = SDMSServiceAreaForm(
            user_profile=UserProfile.objects.get(user=get_current_user()), data=initial_data
        )

        # Paginate active customers
        active_customers = self.get_queryset()
        active_paginator = Paginator(active_customers, self.paginate_by)
        active_page = self.request.GET.get('page')
        try:
            active_customers = active_paginator.page(active_page)
        except PageNotAnInteger:
            active_customers = active_paginator.page(1)
        except EmptyPage:
            active_customers = active_paginator.page(active_paginator.num_pages)
        context['list_qs'] = active_customers

        # Paginate inactive customers
        inactive_customers = self.inactive_customer_list
        inactive_paginator = Paginator(inactive_customers, self.paginate_by)
        inactive_page = self.request.GET.get('inactive_page')
        try:
            inactive_customers = inactive_paginator.page(inactive_page)
        except PageNotAnInteger:
            inactive_customers = inactive_paginator.page(1)
        except EmptyPage:
            inactive_customers = inactive_paginator.page(1)  # Redirect to first page on error
        context['inactive_customer_list'] = inactive_customers

        # Preserve all query parameters except page and inactive_page
        query_params = self.request.GET.copy()
        query_params.pop('page', None)
        query_params.pop('inactive_page', None)
        context['query_params'] = query_params.urlencode()

        # Add additional filters info
        context['filters'] = {
            "Distributor": ", ".join(self.distributor_list),
            "Service Area": ", ".join(self.service_area_list)
        }

        return context
