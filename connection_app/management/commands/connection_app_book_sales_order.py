import datetime

from django.core.management import BaseCommand

from ujjwala.camunda_functions import start_process_in_camunda_v2


class Command(BaseCommand):
	# def add_arguments(self, parser):
	# 	# Positional arguments
	# 	parser.add_argument('-sd', '--so_date', type=str,
	# 	                    default=(datetime.datetime.today() - datetime.timedelta(days=1)).strftime('%d-%b-%Y'))
	# 	# parser.add_argument('-fd', '--from_date', type=str,
	# 	#                     default=(datetime.datetime.today() - datetime.timedelta(days=1)).strftime('%d-%b-%Y'))
	# 	# parser.add_argument('-td', '--to_date', type=str, default=datetime.datetime.today().strftime('%d-%b-%Y'))
	# 	# parser.add_argument('-sot', '--sales_order_type', type=str, default='sales_order_invoice')

	def handle(self, *args, **options):
		from connection_app.models import BookSalesOrder

		for bso_obj in BookSalesOrder.objects.all():
			if not bso_obj.camunda_process_id:
				variables = {
					"variables": {
							"consumer_id": {"value": bso_obj.customer_profile.consumer_id, "type": "String"},
							"book_sales_order_id": {"value": bso_obj.id, "type": "Long"},
							"sdms_task": {"value": "book_sales_order", "type": "String"},
							"distributor_code": {"value": bso_obj.customer_profile.distributor_code, "type": "String"},
							"distributor_name": {"value": bso_obj.customer_profile.distributor_name, "type": "String"},
						}
					}
				res, pid = start_process_in_camunda_v2('Process_domestic_app', variables=variables)
				bso_obj.camunda_process_id = pid
				bso_obj.save()
				print(pid)
