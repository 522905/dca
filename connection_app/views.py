from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import Http404, HttpResponseRedirect
from django.shortcuts import render, redirect
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from django.views.generic import DetailView, ListView, FormView
from django_currentuser.middleware import get_current_user

from connection_app.enums import PostInspectionStatusEnum, InspectionTypeEnum
from connection_app.forms import ChangeAddressForm, PostInspectionStartForm, PreviewPostInspectionForm, \
	KitchenPostInspectionForm
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
@method_decorator(csrf_exempt, 'dispatch')
class PostInspectionView(FormView):
	model = PostInspection
	post_inspection_step0_template = 'connection_app/post-inspection/steps/step0.html'
	post_inspection_step1_template = 'connection_app/post-inspection/steps/step1.html'
	post_inspection_step2_template = 'connection_app/post-inspection/steps/step2.html'
	post_inspection_step3_template = 'connection_app/post-inspection/steps/step3.html'
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

	def get_form_class(self):
		pi_obj = self.get_object()
		if pi_obj.status in (
			PostInspectionStatusEnum.CHANGE_ADDRESS, PostInspectionStatusEnum.REJECTED, PostInspectionStatusEnum.REDO):
			return ChangeAddressForm
		elif pi_obj.status == PostInspectionStatusEnum.KITCHEN_PHOTO:
			return KitchenPostInspectionForm
		elif pi_obj.status == PostInspectionStatusEnum.PREVIEW_INSPECTION:
			return PreviewPostInspectionForm

	def form_valid(self, form):
		form.save()
		return HttpResponseRedirect(self.get_success_url())

	def get_template_names(self):
		pi_obj = self.get_object()
		if pi_obj.status in (
				PostInspectionStatusEnum.CHANGE_ADDRESS,
				PostInspectionStatusEnum.REJECTED,
				PostInspectionStatusEnum.REDO,
		):
			return self.post_inspection_step0_template
		elif pi_obj.status == PostInspectionStatusEnum.KITCHEN_PHOTO:
			return self.post_inspection_step1_template
		elif pi_obj.status == PostInspectionStatusEnum.PREVIEW_INSPECTION:
			return self.post_inspection_step3_template

	def get_form_kwargs(self):
		kwargs = super().get_form_kwargs()
		pi_obj = self.get_object()
		kwargs['post_inspection'] = pi_obj
		return kwargs

	def get_context_data(self, **kwargs):
		context = super().get_context_data(**kwargs)
		return context


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
				status=PostInspectionStatusEnum.CHANGE_ADDRESS,
				type=InspectionTypeEnum.MECHANIC,
				mechanic=get_current_user()
			)
		return redirect('post_inspection_form_view', pk=pi_obj.pk)
