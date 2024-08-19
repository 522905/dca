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
				from_date = options.get('from_date')
				to_date = options.get('to_date')
				sales_order_type = options.get('sales_order_type')
				distributor_code = options.get('distributor_code')

				variables = {
						"variables": {
										"from_date": {"value": from_date, "type": "String"},
										"to_date": {"value": to_date, "type": "String"},
										"sdms_task": {"value": sales_order_type, "type": "String"},
										"distributor_code": {"value": distributor_code, "type": "String"}
								}
				}

				res = start_process_in_camunda_v2('Process_domestic_app', variables=variables)
				print(res)

				for i, so in enumerate(SalesOrder.objects.exclude(
						order_status__in=[
							SalesOrderStatusEnum.COMPLETED, SalesOrderStatusEnum.CANCELLED, SalesOrderStatusEnum.NOT_FOUND
						]).order_by('id')):
					try:
						exist = is_process_exist_in_camunda(
							'process_fetch_sales_order_details_from_sdms', 'sales_order_id', so.id)
						if not exist:
							start_process_fetch_sales_order_details_from_sdms(so.id, so.parent.distributor.code)
					except Exception as e:
						print(e)
						continue
