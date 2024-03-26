import datetime

from django.core.management import BaseCommand

from ujjwala.camunda_functions import start_process_in_camunda_v2


class Command(BaseCommand):
	def add_arguments(self, parser):
		# Positional arguments
		parser.add_argument('from_date', type=str,
		                    default=(datetime.datetime.today() - datetime.timedelta(days=1)).strftime('%d-%b-%Y'))
		parser.add_argument('sales_order_type', type=str, default='sales_order_invoice')

	def handle(self, *args, **options):
		from_date = options.get('from_date')
		sales_order_type = options.get('sales_order_type')

		variables = {
			"variables":
				{
					"from_date": {"value": from_date, "type": "String"},
					"sales_order_type": {"value": sales_order_type, "type": "String"},
				}
		}

		print(options)
		res = start_process_in_camunda_v2('Process_domestic_app', variables=variables)
		print(res)
