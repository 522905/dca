from datetime import timedelta

from django.utils import timezone
from django.views.generic import TemplateView
from organizations.models import OrganizationOwner , OrganizationUser
import django_filters
from .models import SalesOrder
from teams.models import UserProfile
import pandas as pd


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
			delivery_boy_logins = UserProfile.objects.get(user_id=current_user).sdmsuser_set.values(
				"delivery_boy_login")

		# Filter sales orders
		queryset = SalesOrder.objects.filter(
			delivery_boy_login__in=delivery_boy_logins
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

		return queryset

	def get_context_data(self, **kwargs):
		current_user = self.request.user.id
		context = super().get_context_data(**kwargs)
		queryset = self.get_queryset()
		if queryset.count() == 0:
			return context

		is_organization_admin = OrganizationOwner.objects.filter(organization_user__user=current_user).exists()
		df = pd.DataFrame(list(queryset.values("delivery_date", "delivery_boy_login", "delivery_confirmation_type",
											   "delivery_boy_full_name")))
		# Convert the 'delivery_date' column to only date
		df['delivery_date'] = pd.to_datetime(df['delivery_date']).dt.date
		if not df.empty:
			# Group by order_date and delivery_boy_login, then aggregate confirmation types
			stats = (
				df.groupby(["delivery_date", "delivery_boy_full_name", "delivery_confirmation_type"])
				.size()
				.unstack(fill_value=0)
				.reset_index()
			)

			# Calculate totals and percentages
			stats["Total"] = stats["OTP"] + stats["Override"]
			stats["OTP_Percentage"] = (stats["OTP"] / stats["Total"]) * 100
			context["total_otp"] = stats["OTP"].sum()
			context["total_override"] = stats["Override"].sum()
			context["total_orders"] = stats["Total"].sum()
			# Format data for frontend as a list of dictionaries
			stats["delivery_date"] = stats["delivery_date"]  # Format date as string
			context["daily_stats"] = stats.to_dict(orient="records")
			context["is_organization_admin"] = is_organization_admin
		# Add delivery boys for filtering
		delivery_boy_logins = queryset.values_list("delivery_boy_login", flat=True).distinct()
		context["delivery_boys"] = UserProfile.objects.filter(sdmsuser__delivery_boy_login__in=delivery_boy_logins)

		return context


class DashboardSalesView(BaseSalesView):
	template_name = "connection_app/dashboard.html"

	def get_context_data(self, **kwargs):
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
