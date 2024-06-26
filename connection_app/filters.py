import django_filters
from django_filters import FilterSet

from connection_app.models import SalesOrder, CustomerProfile


class SalesOrderFilterSet(FilterSet):
	consumer_id = django_filters.NumberFilter(field_name='consumer_id', label="Consumer Id:")

	class Meta:
		model = CustomerProfile
		fields = ['consumer_id']

	@property
	def qs(self):
		qs = super().qs
		consumer_id = self.data.get('consumer_id')

		if consumer_id in [None, '']:
			return qs.none()
		return qs
