from datetime import timedelta

import django_filters
from django.contrib.auth.decorators import login_required
from django.db.models import Count, Q
from django.db.models.functions import TruncDate
from django.http import Http404
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.views.generic import TemplateView, FormView
from organizations.models import OrganizationOwner, OrganizationUser

from reference_data.models import Distributor
from teams.enums import UserProfileTypeEnum
from teams.models import UserProfile
from .enums import SalesOrderStatusEnum
from .models import SalesOrder, CustomerProfile
from django.http import HttpResponseRedirect
from django.urls import reverse

class SalesOrderFilter(django_filters.FilterSet):
	delivery_boy = django_filters.ModelChoiceFilter(
		queryset=UserProfile.objects.filter(sdmsuser__delivery_boy_login__isnull=False),
		field_name="delivery_boy_login",
		to_field_name="delivery_boy_login",
		label="Delivery Boy"
	)
	start_date = django_filters.DateFilter(field_name="delivery_date", lookup_expr="gte", label="Start Date")
	end_date = django_filters.DateFilter(field_name="delivery_date", lookup_expr="lte", label="End Date")

	class Meta:
		model = SalesOrder
		fields = ["delivery_boy", "start_date", "end_date"]


class BaseSalesView(TemplateView):
	def get_queryset(self):
		current_user = self.request.user.id
		# Check if the user is an organization admin
		owner = OrganizationOwner.objects.filter(organization_user__user=current_user).first()
		if owner:
			# Get all delivery boys in the organization
			organization_users = OrganizationUser.objects.filter(organization=owner.organization)
			user_ids = organization_users.values_list("user_id", flat=True)
			delivery_boy_logins = UserProfile.objects.filter(user_id__in=user_ids).values_list(
				"sdmsuser__delivery_boy_login", flat=True
			)
		else:
			# Add current user's delivery logins
			delivery_boy_logins = UserProfile.objects.get(
				user_id=current_user
			).sdmsuser_set.values("delivery_boy_login")

		# Filter sales orders
		queryset = SalesOrder.objects.filter(
			delivery_confirmed_by__in=delivery_boy_logins,
			order_status=SalesOrderStatusEnum.COMPLETED
		)

		# Apply date range filter
		start_date = self.request.GET.get("start_date")
		if not start_date:
			start_date = timezone.now() - timedelta(days=10)
		end_date = self.request.GET.get("end_date")
		if start_date:
			queryset = queryset.filter(delivery_date__gte=start_date)
		if end_date:
			queryset = queryset.filter(delivery_date__lte=end_date)
		# Truncate delivery_date to date only
		queryset = queryset.annotate(delivery_date_only=TruncDate('delivery_date'))

		return queryset

	def get_context_data(self, **kwargs):
		current_user = self.request.user.id
		context = super().get_context_data(**kwargs)
		queryset = self.get_queryset()
		if queryset.count() == 0:
			return context

		is_organization_admin = OrganizationOwner.objects.filter(organization_user__user=current_user).exists()
		# Generate statistics using Django ORM
		stats = queryset.values('delivery_date_only', 'delivery_confirm_full_name').annotate(
			otp_count=Count('id', filter=Q(delivery_confirmation_type='OTP')),
			override_count=Count('id', filter=Q(delivery_confirmation_type='Override'))
		)

		stats = sorted(stats, key=lambda x: x['delivery_date_only'])

		# Calculate totals and percentages
		for stat in stats:
			stat['Total'] = stat['otp_count'] + stat['override_count']
		# stat['OTP_Percentage'] = (stat['otp_count'] / stat['Total']) * 100 if stat['Total'] > 0 else 0

		context["total_otp"] = sum(stat['otp_count'] for stat in stats)
		context["total_override"] = sum(stat['override_count'] for stat in stats)
		context["total_orders"] = sum(stat['Total'] for stat in stats)
		context["daily_stats"] = list(stats)
		context["is_organization_admin"] = is_organization_admin

		# Add delivery boys for filtering
		delivery_boy_logins = queryset.values_list("delivery_boy_login", flat=True).distinct()
		context["delivery_boys"] = UserProfile.objects.filter(sdmsuser__delivery_boy_login__in=delivery_boy_logins)

		return context


class DashboardSalesView(BaseSalesView):
	template_name = "connection_app/dashboard.html"

	def get_context_data(self, **kwargs):
		current_user = self.request.user.id
		is_deliveryboy = UserProfile.objects.filter(user_id=current_user,
													type=UserProfileTypeEnum.DELIVERY_BOY).exists()
		if not is_deliveryboy:
			return
		context = super().get_context_data(**kwargs)

		# Get the total number of sales orders
		return context


class SalesProcessedView(BaseSalesView):
	model = SalesOrder
	template_name = "connection_app/sales_order_processed.html"
	filterset_class = SalesOrderFilter

	def get_context_data(self, **kwargs):
		context = super().get_context_data(**kwargs)

		# Get the total number of sales orders
		return context

from django import forms

class DistributorChoiceForm(forms.Form):
	distributor = forms.ModelChoiceField(
        queryset=Distributor.objects.filter(Q(code="0000305948") | Q(code="0000110338")),  # Get all distributors
        to_field_name="id",  # This will use 'id' as the value
        empty_label="Select Distributor",  # Optional empty label
        widget=forms.Select(attrs={'class': 'form-control'})  # Optional styling
    )

@method_decorator(login_required, 'dispatch')
class CustomerProfileFormView(TemplateView):
	template_name = 'connection_app/customer_profile.html'
	form = DistributorChoiceForm

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
		 	"form": self.form,
		})
		return context

	def post(self,request,*args,**kwargs):
		form = DistributorChoiceForm(request.POST)
		obj = self.get_object()

		if form.is_valid():
			dist = form.cleaned_data['distributor']
			obj.distributor_id = dist.id
			obj.distributor_code = dist.code
			obj.distributor_name = dist.name
			obj.is_dirty = True
			obj.save()

			# Redirect after successful form submission
			return HttpResponseRedirect(reverse('customer_profile', kwargs={'pk': obj.pk}))




