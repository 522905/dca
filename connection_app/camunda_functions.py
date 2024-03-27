import datetime
import json

from camunda.external_task.external_task import ExternalTask

def get_customer_profile(consumer_id):
	from connection_app.models import CustomerProfile

	cp_obj = CustomerProfile.objects.filter(consumer_id=consumer_id).first()

	if not cp_obj:
		cp_obj = CustomerProfile.objects.create(consumer_id=consumer_id)

	return cp_obj


def process_update_sales_order_invoice_in_dca(task: ExternalTask):
	"""
		{
		  "": "",
		  "Invoice Number": "5-103991627817",
		  "Sales Order #": "2-003653125558",
		  "Invoice date": "21-Mar-2024 01:24:31 PM",
		  "Invoice Status": "Open",
		  "Consumer Name": "Sham Lal",
		  "Consumer Type": "Double Bottle Connection",
		  "Consumer Address": "H.NO.6441/2 ST.NO.8 HARGOBIND NAGAR LDH. PROOF OK /10/2/2010 LUDHIANA Punjab 141008",
		  "Subsidy Status": "Start",
		  "Scheme Onboarding Status": "Onboarded With CTC",
		  "Delivery Type": "Home Delivery",
		  "Service Area": "KIDWAI NGR RANJIT NGR AMAR PUR",
		  "Delivery Boy": "ARUN YADAV",
		  "Paid Flag": "N",
		  "Preferred Flag": "N",
		  "Preferred Day": "",
		  "Preferrred Time Slot": "",
		  "Print Flag": "N",
		  "Order Sub Type": "Refill Order",
		  "Equipment Type": "14.2",
		  "Relationship Id": "7500000068250924",
		  "Consumer Number": "7568250924",
		  "Distributor Local Cash Memo#": "305948243100193364",
		  "Digital Payment": "N",
		  "Scheme Type": "General",
		  "Tatkal Order": "",
		  "EPIC Invoice IRN Calc": "N",
		  "IRN Number": "",
		  "Site Id": ""
		}
		"""
	from connection_app.models import SalesOrderInvoice, CustomerProfile

	data = json.loads(task.get_variable('result'))['data']

	for r in data:
		invoice_date = datetime.datetime.strptime(r["Invoice date"],
		                                          '%d-%b-%Y %H:%M:%S %p')  # "21-Mar-2024 01:24:31 PM"
		soi_obj: SalesOrderInvoice = SalesOrderInvoice.objects.filter(invoice_number=r['Invoice Number'],
		                                           invoice_date=invoice_date).first()
		if soi_obj and (
				soi_obj.invoice_status != r['Invoice Status'] or soi_obj.subsidy_status != r["Subsidy Status"]
		):
				soi_obj.order_status = r['Order Status']
				soi_obj.subsidy_status = r["Subsidy Status"]
				soi_obj.save(update_fields=['order_status', 'subsidy_status'])
		else:
			cp_obj = get_customer_profile(r["Consumer Number"])

			soi_obj = SalesOrderInvoice.objects.create(
				parent=cp_obj,
				invoice_number=r["Invoice Number"],
				sales_order=r["Sales Order #"],
				invoice_date=invoice_date,
				invoice_status=r["Invoice Status"],
				consumer_name=r["Consumer Name"],
				consumer_type=r["Consumer Type"],
				consumer_address=r["Consumer Address"],
				subsidy_status=r["Subsidy Status"],
				scheme_onboarding_status=r["Scheme Onboarding Status"],
				delivery_type=r["Delivery Type"],
				service_area=r["Service Area"],
				delivery_boy=r["Delivery Boy"],
				paid_flag=True if r["Paid Flag"] == "Y" else False,
				preferred_flag=True if r["Preferred Flag"] == "Y" else False,
				preferred_day=r["Preferred Day"],
				preferred_time_slot=r["Preferrred Time Slot"],
				print_flag=True if r["Print Flag"] == "Y" else False,
				order_sub_type=r["Order Sub Type"],
				equipment_type=r['Equipment Type'],
				relationship_id=r["Relationship Id"],
				consumer_number=r["Consumer Number"],
				distributor_local_cash_memo=r["Distributor Local Cash Memo#"],
				digital_payment=True if r["Digital Payment"] == "Y" else False,
				scheme_type=r["Scheme Type"],
				tatkal_order=r["Tatkal Order"],
				epic_invoice_irn_calc=True if r["EPIC Invoice IRN Calc"] == "Y" else False,
				irn_number=r["IRN Number"],
				site_id=r["Site Id"]
			)
			print(soi_obj)


def process_update_sales_order_in_dca(task: ExternalTask):
	"""
		{
			"": "",
			"Sales Order #": "2-003664888925",
			"Order Date": "26-Mar-2024 09:13:44 PM",
			"Relationship Id": "7200000033203814",
			"Invoice Number": "5-104004535514",
			"Consumer Name": "Arfa Parveen",
			"Consumer Address": "hNo 1815/87 StNo 1 Industrial area a  millerganjVijay nagar   Ludhiana LUDHIANA Punjab 141003",
			"Channel": "MissedCall",
			"Order Type": "Sales Order",
			"Order Sub Type": "Refill Order",
			"Order Status": "Completed",
			"Delivery Date": "27-Mar-2024 07:35:30 AM",
			"Consumed Quota": "28.4",
			"Campaign Name": "",
			"Campaign Code": "",
			"Digital Payment": "Y",
			"Account Name": "",
			"Consumer Type": "Single Bottle Connection",
			"Cancellation Date": "",
			"Paid": "Y",
			"Delivery Confirm Full Name": "ANAND RAY",
			"Mobile Number": "8969102423",
			"Tatkal Order": "",
			"Portability Flag": "N"
		 }
	"""
	from connection_app.models import SalesOrder, CustomerProfile

	data = json.loads(task.get_variable('result'))['data']

	for r in data:
		order_date = datetime.datetime.strptime(r["Order Date"],
		                                          '%d-%b-%Y %H:%M:%S %p')  # "21-Mar-2024 01:24:31 PM"
		so_obj: SalesOrder = SalesOrder.objects.filter(sales_order=r['Sales Order #'], order_date=order_date).first()

		if so_obj and so_obj.order_status != r['Order Status']:
				so_obj.order_status = r['Order Status']
				so_obj.save(update_fields=['order_status'])
		else:
			cp_obj = get_customer_profile(r["Relationship Id"])

			so_obj = SalesOrder.objects.create(
				parent=cp_obj,
				sales_order=r["Sales Order #"],
				order_date=order_date,
				relationship_id=r["Relationship Id"],
				invoice_number=r["Invoice Number"],
				consumer_name=r["Consumer Name"],
				consumer_address=r["Consumer Address"],
				channel=r['Channel'],
				order_type=r['Order Type'],
				order_sub_type=r['Order Sub Type'],
				order_status=r['Order Status'],
				delivery_date=datetime.datetime.strptime(r['Delivery Date'], '%d-%b-%Y %H:%M:%S %p') if r[
					'Delivery Date'] else None,
				consumed_quota=float(r['Consumed Quota']) if r['Consumed Quota'] else None,
				campaign_name=r['Campaign Name'],
				campaign_code=r['Campaign Code'],
				digital_payment=True if r['Digital Payment'] == 'Y' else False,
				account_name=r['Account Name'],
				consumer_type=r['Consumer Type'],
				cancellation_date=datetime.datetime.strptime(r['Cancellation Date'], '%d-%b-%Y %H:%M:%S %p') if r[
					'Cancellation Date'] else None,
				paid=True if r['Paid'] == 'Y' else False,
				delivery_confirm_full_name=r['Delivery Confirm Full Name'],
				mobile_number=r['Mobile Number'],
				tatkal_order=r['Tatkal Order'],
				portability_flag=True if r['Portability Flag'] else False
			)
			print(so_obj)
