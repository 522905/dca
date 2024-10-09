import datetime

from django.core.management import BaseCommand

from connection_app.camunda_functions import start_process_fetch_sales_order_details_from_sdms
from connection_app.enums import SalesOrderStatusEnum
from connection_app.models import SalesOrder
from ujjwala.camunda_functions import start_process_in_camunda_v2, is_process_exist_in_camunda


class Command(BaseCommand):
		def add_arguments(self, parser):
				# Positional arguments
				parser.add_argument('-fd', '--from_date', type=str,
									default=(datetime.datetime.today() - datetime.timedelta(days=1)).strftime(
										'%d-%b-%Y'))
				parser.add_argument('-td', '--to_date', type=str,
									default=datetime.datetime.today().strftime('%d-%b-%Y'))
				parser.add_argument('-sot', '--sales_order_type', type=str, default='fetch_sales_order')
				parser.add_argument('-dc', '--distributor_code', type=str, default='0000305948')

		def handle(self, *args, **options):
				for i, so in enumerate(SalesOrder.objects.exclude(
						order_status__in=[
							SalesOrderStatusEnum.COMPLETED, SalesOrderStatusEnum.CANCELLED, SalesOrderStatusEnum.NOT_FOUND
						]).order_by('id')):
					try:
						exist = is_process_exist_in_camunda(
							'process_fetch_sales_order_details_from_sdms', 'sales_order_id', so.id
						)
						if not exist:
							if so.parent.distributor:
								start_process_fetch_sales_order_details_from_sdms(so.id, so.parent.distributor.code)
							elif "arun gas" in so.distributor_name.lower():
								start_process_fetch_sales_order_details_from_sdms(so.id, "0000110338")
							elif "arun indane" in so.distributor_name.lower():
								start_process_fetch_sales_order_details_from_sdms(so.id, "0000305948")
							else:
								print("Could Not Find Valid Distributor")
					except Exception as e:
						print(e)
						continue
