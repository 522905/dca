from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import Http404, HttpResponseRedirect
from django.shortcuts import render, redirect
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from django.views.generic import DetailView, ListView, FormView
from django_currentuser.middleware import get_current_user

from connection_app.enums import PostInspectionStatusEnum, InspectionTypeEnum, PostInspectionActivityTypeEnum
from connection_app.forms import UpdateAddressForm, PostInspectionStartForm, PreviewPostInspectionForm, \
	KitchenPostInspectionForm, PostInspectionForm, UIDPostInspectionForm, ProfilePhotoPostInspectionForm
from connection_app.models import ConnectionApplication, PostInspection, CustomerProfile
from ujjwala.forms import KitchenPreInspectionForm


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
		return PostInspection.objects.filter(
			mechanic=get_current_user()
		).order_by('-submitted_on')


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
			else:
				messages.add_message(
					self.request, messages.ERROR, "No customer found for given consumer id"
				)
				return redirect('post_inspection_start')

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
		form.save()
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
		print("Error")

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
	form_class = KitchenPostInspectionForm
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