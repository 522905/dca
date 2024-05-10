from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.http import Http404, HttpResponseRedirect
from django.shortcuts import render, redirect
from django.urls import reverse
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from django.views.generic import DetailView, ListView, FormView, TemplateView
from django.views.generic.edit import ProcessFormView
from django_currentuser.middleware import get_current_user

from connection_app.enums import PostInspectionStatusEnum, InspectionTypeEnum, PostInspectionActivityTypeEnum, \
	ConnectionApplicationDocumentsEnum
from connection_app.forms import UpdateAddressForm, PostInspectionStartForm, PreviewPostInspectionForm, \
	KitchenPostInspectionForm, PostInspectionForm, UIDPostInspectionForm, ProfilePhotoPostInspectionForm, \
	SurakshaPipePostInspectionForm, CustomerProfileSearchForm, GenerateLeadForm, GenerateNonCustomerLeadForm, \
	CustomerProfileDocumentUploadForm, SalesOrderDetailViewForm, SalesOrderListViewFilterForm
from connection_app.models import ConnectionApplication, PostInspection, CustomerProfile, Lead, SalesOrder
from reference_data.models import ServiceType
from teams.models import UserProfile, SDMSUser


def installation_upload_process_gleam_entry_gate(request):
	application_id = request.GET.get("application_id")
	response = render(request, 'connection_app/fblike.html')
	response.set_cookie('application_id_cookie', application_id)
	return response


def installation_upload_process_gleam_entry_gate_completed(request):
	application_id = request.COOKIES.get('application_id_cookie')
	return redirect('installation_start', pk=application_id)


def index(request):
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
				self.request, "domestic/response.html",
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
				self.request, "domestic/response.html",
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
				self.request, "domestic/response.html",
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
				self.request, "domestic/response.html",
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
				self.request, "domestic/response.html",
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
				self.request, "domestic/response.html",
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
		})
		return context
	

@method_decorator(login_required, 'dispatch')
class SalesOrderListView(ListView):
	model = SalesOrder
	template_name = 'connection_app/sales-order/sales_order_listview.html'

	paginate_by = 20
	permission = 'has_view_permission'
	#
	# def dispatch(self, request, *args, **kwargs):
	# 	if request.method == 'POST':
	# 		return redirect(reverse("connection_app:sales_order_list") + "?hide_from_view={}".format("on"))
	# 	return super().dispatch(request, *args, **kwargs)

	def get_queryset(self):
		current_user = get_current_user()
		qs = SalesOrder.objects.filter(auto_generated=True)

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


	def get_context_data(self, *, object_list=None, **kwargs):
		context = super().get_context_data(object_list=object_list, **kwargs)
		context.update({
			"filter_form": SalesOrderListViewFilterForm(
				initial={'show_hidden_records': self.request.GET.get('show_hidden_records')})
		})
		return context

 
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

	def dispatch(self, request, *args, **kwargs):
		# sales_order = self.get_object()

		# if sales_order.documents.filter(type=ConnectionApplicationDocumentsEnum.BANK_SUBSIDY_CERTIFICATE_PHOTO).first():
		# 	messages.add_message(self.request, messages.INFO,
		# 	                     f"Bank Subsidy Certificate Document Already Submitted.")
		# 	return redirect("customer_profile", pk=self.get_object().pk)
		return super().dispatch(request, *args, **kwargs)

	def form_valid(self, form):
		# data = form.cleaned_data

		# customer_profile = self.get_object()
		# customer_profile.documents.create(
		# 	type=data['document_type'], link=data['document_link']
		# )
		# messages.add_message(self.request, messages.INFO, f"{data['document_type']} Document Uploaded Successfully.")
		return redirect("sales_order", pk=self.get_object().pk)

	def get_context_data(self, **kwargs):
		context = super().get_context_data()
		context.update({
			"sales_order": self.get_object()
		})
		return context

	def get_form_kwargs(self):
		kwargs = super().get_form_kwargs()
		# kwargs['initial'] = {'document_type': ConnectionApplicationDocumentsEnum.BANK_SUBSIDY_CERTIFICATE_PHOTO}
		return kwargs
	


