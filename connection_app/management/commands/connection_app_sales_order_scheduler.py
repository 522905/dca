import datetime
from django.core.management import BaseCommand
from ujjwala.camunda_functions import start_process_in_camunda_v2


class Command(BaseCommand):
    def add_arguments(self, parser):
        # Positional arguments
        parser.add_argument('-fd', '--from_date', type=str,
                            default=(datetime.datetime.today() - datetime.timedelta(days=1)).strftime('%d-%b-%Y'))
        parser.add_argument('-td', '--to_date', type=str,
                            default=datetime.datetime.today().strftime('%d-%b-%Y'))
        parser.add_argument('-sot', '--sales_order_type', type=str, default='fetch_sales_order')
        parser.add_argument('-dc', '--distributor_code', type=str, default='0000305948')

    def handle(self, *args, **options):
        # Parse date strings into datetime objects
        from_date_str = options.get('from_date')
        to_date_str = options.get('to_date')
        sales_order_type = options.get('sales_order_type')
        distributor_code = options.get('distributor_code')

        from_date = datetime.datetime.strptime(from_date_str, '%d-%b-%Y')
        to_date = datetime.datetime.strptime(to_date_str, '%d-%b-%Y')

        current_date = from_date
        while current_date <= to_date:
            # Format the current date as needed
            current_date_str = current_date.strftime('%d-%b-%Y')

            variables = {
                "variables": {
                    "from_date": {"value": current_date_str, "type": "String"},
                    "to_date": {"value": current_date_str, "type": "String"},
                    "sdms_task": {"value": sales_order_type, "type": "String"},
                    "distributor_code": {"value": distributor_code, "type": "String"}
                }
            }

            # Start the Camunda process for each day
            res = start_process_in_camunda_v2('Process_domestic_app', variables=variables)
            print(f'Response for {current_date_str}: {res}')

            # Move to the next day
            current_date += datetime.timedelta(days=1)
