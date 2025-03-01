from django.core.management import BaseCommand

from connection_app.jobs import start_read_customer_profile

class Command(BaseCommand):

	def handle(self, *args, **options):
		from connection_app.models import SalesOrder, CustomerProfile, ConnectionApplication

		for cp_obj in CustomerProfile.objects.filter(is_dirty=True):
			start_read_customer_profile(cp_obj.id)