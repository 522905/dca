import datetime

from django.core.management import BaseCommand

from connection_app.functions import get_delivery_boy_login
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
		from connection_app.models import CustomerProfile

		# for i in [10223, 10035, 15776, 71128, 40728, 62625, 41853, 64722, 51425, 63289]:
		# 	BookSalesOrder.objects.create(customer_profile_id=i)

		for bso_obj in BookSalesOrder.objects.all():
			if not bso_obj.camunda_process_id:
				try:
					variables = {
						"variables": {
								"consumer_id": {"value": bso_obj.customer_profile.consumer_id, "type": "String"},
								"book_sales_order_id": {"value": bso_obj.id, "type": "Long"},
								"sdms_task": {"value": "book_sales_order", "type": "String"},
								"distributor_code": {"value": bso_obj.customer_profile.distributor_code, "type": "String"},
								"distributor_name": {"value": bso_obj.customer_profile.distributor_name, "type": "String"},
								"delivery_boy_login": {
									"value": get_delivery_boy_login(bso_obj.customer_profile.id), "type": "String"
								},
							}
						}
					res, pid = start_process_in_camunda_v2('Process_book_sales_order', variables=variables)
					bso_obj.camunda_process_id = pid
					bso_obj.save()
					print(pid)
				except Exception as e:
					bso_obj.error_log = str(e)
					bso_obj.save()
					continue
