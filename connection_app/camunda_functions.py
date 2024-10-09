import datetime

import django_rq
import requests

from connection_app.enums import SalesOrderStatusEnum
from connection_app.jobs import start_read_customer_profile
from connection_app.models import SalesOrder
from domestic_app.settings import CAMUNDA_BASE_URL
from reference_data.models import Distributor
from ujjwala.camunda_functions import start_process_in_camunda_v2, is_process_exist_in_camunda
from ujjwala.ujjwala_functions import evaluate_change_cylinder_type_requests


def get_customer_profile(consumer_id, name, address, distributor_code):
	from connection_app.models import CustomerProfile
	from connection_app.jobs import start_read_customer_profile

	distributor = Distributor.objects.filter(code=distributor_code).first()
	cp_obj: CustomerProfile = CustomerProfile.objects.filter(consumer_id=consumer_id).first()

	if not cp_obj:
		cp_obj = CustomerProfile.objects.create(
			consumer_id=consumer_id,
			name=name,
			address=address,
			distributor=distributor,
			distributor_code=distributor_code,
		)
		django_rq.enqueue(start_read_customer_profile, args=(cp_obj.id,))
	return cp_obj


def get_sdms_service_area(area_name, distributor_code):
	from teams.models import SDMSServiceArea

	distributor = Distributor.objects.filter(code=distributor_code).first()
	sdms_service_area_list = SDMSServiceArea.objects.filter(area_name=area_name, distributor=distributor)

	if sdms_service_area_list:
		return sdms_service_area_list.first()
	else:
		return SDMSServiceArea.objects.create(area_name=area_name, distributor=distributor)


def start_process_fetch_sales_order_details_from_sdms(so_id, distributor_code):
	from connection_app.models import SalesOrder

	so_obj: SalesOrder = SalesOrder.objects.get(pk=so_id)

	if not so_obj:
		raise Exception("Sales Order Id Not Found")

	result = is_process_exist_in_camunda('cb0cbe24-f241-11ee-b887-0242ac140002', 'sales_order_id', so_obj.id)
	# distributor_code = "0000110338" if "gas" in distributor_code else "0000305948"

	# if so_obj.parent.distributor_code != distributor_code:
	# 	so_obj.parent.distributor_code = distributor_code
	# 	so_obj.parent.save()

	if result == 0:
		variables = {
			"variables":
				{
					"sales_order_id": {"value": so_obj.id, "type": "Long"},
					"sales_order_number": {"value": so_obj.sales_order, "type": "String"},
					"order_status": {"value": so_obj.order_status, "type": "String"},
					"distributor_code": {"value": distributor_code, "type": "String"}
				}
			}
		res, pid = start_process_in_camunda_v2('process_fetch_sales_order_details_from_sdms', variables=variables)
		if res == 200:
			so_obj.camunda_process_instance_id = pid
			so_obj.save()
		print(res)


def start_process_return_sales_order(so_id, distributor_code):
	from connection_app.models import SalesOrder

	so_obj: SalesOrder = SalesOrder.objects.get(pk=so_id)

	if not so_obj:
		raise Exception("Sales Order Id Not Found")

	existing = requests.post(
		f'{CAMUNDA_BASE_URL}/process-instance',
		json={
			"variables": [
				{
					"name": "sales_order_id",
					"operator": "eq",
					"value": str(so_id)
				},
				{
					"name": "distributor_code",
					"operator": "eq",
					"value": str(distributor_code)
				}
			],
			"processDefinitionKey": "Process_book_sales_order"
		}).json()

	# distributor_code = "0000110338" if "gas" in distributor_code else "0000305948"

	# if so_obj.parent.distributor_code != distributor_code:
	# 	so_obj.parent.distributor_code = distributor_code
	# 	so_obj.parent.save()

	if len(existing) == 0:
		variables = {
			"variables":
				{
					"sales_order_id": {"value": so_obj.id, "type": "Long"},
					"sales_order": {"value": so_obj.sales_order, "type": "String"},
					"order_status": {"value": so_obj.order_status, "type": "String"},
					"distributor_code": {"value": distributor_code, "type": "String"},
					"sdms_task": {"value": "cancel_booked_sales_order", "type": "String"},
					"delivery_boy_login": {"value": so_obj.delivery_boy_login, "type": "String"},
				}
			}
		res, pid = start_process_in_camunda_v2('Process_book_sales_order', variables=variables)
		if res == 200:
			so_obj.cancellation_camunda_pid = pid
			so_obj.save()
		print(res)


def create_sales_order(so, distributor_code):
	"""
		Create Sales Order In Connection App For Given Sales Order Object From SDMS
	"""
	from connection_app.models import SalesOrder

	cp_obj = get_customer_profile(so["Relationship Id"], so["Consumer Name"], so["Consumer Address"], distributor_code)

	so_obj = SalesOrder.objects.create(
		parent=cp_obj,
		sales_order=so["Sales Order #"],
		order_date=datetime.datetime.strptime(so["Order Date"], '%d-%b-%Y %H:%M:%S %p'),
		relationship_id=so["Relationship Id"],
		invoice_number=so["Invoice Number"],
		consumer_name=so["Consumer Name"],
		consumer_address=so["Consumer Address"],
		channel=so['Channel'],
		order_type=so['Order Type'],
		order_sub_type=so['Order Sub Type'],
		order_status=so['Order Status'],
		delivery_date=datetime.datetime.strptime(so['Delivery Date'], '%d-%b-%Y %H:%M:%S %p') if so[
			'Delivery Date'] else None,
		consumed_quota=float(so['Consumed Quota']) if so['Consumed Quota'] else None,
		campaign_name=so['Campaign Name'],
		campaign_code=so['Campaign Code'],
		digital_payment=True if so['Digital Payment'] == 'Y' else False,
		account_name=so['Account Name'],
		consumer_type=so['Consumer Type'],
		cancellation_date=datetime.datetime.strptime(so['Cancellation Date'], '%d-%b-%Y %H:%M:%S %p') if so[
			'Cancellation Date'] else None,
		paid_flag=True if so['Paid'] == 'Y' else False,
		delivery_confirm_full_name=so['Delivery Confirm Full Name'],
		mobile_number=so['Mobile Number'],
		tatkal_order=so['Tatkal Order'],
		portability_flag=True if so['Portability Flag'] else False
	)
	print(so_obj)
	return so_obj


def process_update_sales_order_completed_today(sales_order_completed):
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
	from connection_app.models import SalesOrder

	for so_complete in sales_order_completed:
		so_obj: SalesOrder = SalesOrder.objects.filter(
			sales_order=so_complete['Sales Order #'],
			order_date=datetime.datetime.strptime(so_complete["Order Date"], '%d-%b-%Y %H:%M:%S %p')
		).first()

		if so_obj:
			if so_obj.order_status != so_complete['Order Status']:
				start_process_fetch_sales_order_details_from_sdms(so_obj.id)
		else:
			so_obj = create_sales_order(so_complete)
			start_process_fetch_sales_order_details_from_sdms(so_obj.id)


def process_update_sales_order_in_dca(sales_order_list, distributor_code):
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
	for so in sales_order_list:
		try:
			so_obj: SalesOrder = SalesOrder.objects.filter(
				sales_order=so['Sales Order #'],
				order_date=datetime.datetime.strptime(so["Order Date"], '%d-%b-%Y %H:%M:%S %p')
			).first()

			if so_obj:
				if so_obj.order_status != so['Order Status']:
					so_obj.order_status = so['Order Status']
					so_obj.save()
			else:
				so_obj = create_sales_order(so, distributor_code)

			if so_obj.order_status in [
				SalesOrderStatusEnum.COMPLETED, SalesOrderStatusEnum.CANCELLED
			] or so_obj.is_dirty:
				start_process_fetch_sales_order_details_from_sdms(so_obj.id, distributor_code)
		except Exception as e:
			continue

	# django_rq.enqueue(evaluate_change_cylinder_type_requests)


def update_sales_order_details_in_dca(sales_order_id, sales_order_details, existing_order_status):
	"""
	{
	  "sales_order": "2-003678554023",
	  "order_type": "Sales Order",
	  "order_sub_type": "Refill Order",
	  "order_status": "Invoiced",
	  "order_date": "01-Apr-2024 09:21:40 PM",
	  "channel": "MissedCall",
	  "channel_ref": "2284935308605915",
	  "price_list": "IOCL LPG Price List",
	  "total_due_amount": "Rs.830.00",
	  "order_total": "Rs.830.00",
	  "total_payment_amount": "Rs.0.00",
	  "attempted_during_pdt_daytime": "N",
	  "indenting_po_number": "04012024212140",
	  "zone_distributor_id": "",
	  "scheme_opted": "Default Opt In",
	  "delivery_type": "Home Delivery",
	  "delivery_date": "",
	  "dac_flag": "N",
	  "portability_flag": "N",
	  "sub_channel": "",
	  "booked_by": "",
	  "qc_due": "N",
	  "relationship_id": "7200000034018379",
	  "consumer_name": "Shallu .",
	  "account_name": "",
	  "consumer_address": "DcaId-13383 Room No 0 Floor No Ground Floor  House No 330/1 Street No 0 Salem Tabri,Neta Ji Near Shera Vali Mata Mandir  Ward No 25 Post Office Salem Tabri   Ludhiana LUDHIANA Punjab 141008",
	  "scheme_onboarding_status": "Onboarded With CTC",
	  "subsidy_status": "Start",
	  "consumed_quota": "14.2",
	  "smart_card_num": "",
	  "perferred_day": "",
	  "preferred_time_slot": "",
	  "preferred_flag": "N",
	  "isi_mark_ho_plate": "",
	  "burner_type": "",
	  "cancellation_reason": "",
	  "cancellation_date": "",
	  "dac_disable_reason": "",
	  "campaign_code": "",
	  "campaign_name": "",
	  "distributor_name": "ARUN INDANE PROP LUDHIANA ENT.",
	  "service_area": "SHIVPURI",
	  "delivery_boy_login": "0000305948_34",
	  "delivery_boy_full_name": "YOGESH GUPTA",
	  "otp": "",
	  "delivery_confirmation_type": "",
	  "delivery_confirmed_by": "",
	  "delivery_confirm_full_name": " ",
	  "error_message": "",
	  "paid_flag": "N",
	  "digital_payment": "N",
	  "subsidized": "N",
	  "subsidized_on_invoice_gen": "Y",
	  "cancel_source": "",
	  "dac_disable_by": "",
	  "tatkal_flag": "",
	  "ship_to_address": "DcaId-13383 Room No 0 Floor No Ground Floor  House No 330/1 Street No 0 Salem Tabri,Neta Ji Near Shera Vali Mata Mandir  Ward No 25 Post Office Salem Tabri   Ludhiana LUDHIANA Punjab 141008"
	}
	"""
	from connection_app.models import SalesOrder

	if sales_order_details.get('sales_order_status', '') == 'NOT_FOUND':
		so_obj = SalesOrder.objects.get(id=sales_order_id)
		so_obj.transition_sales_order_not_found()
		so_obj.save()
		return so_obj

	so = sales_order_details.pop('sales_order')

	so_new_details: dict = sales_order_details

	new_order_status = so_new_details.pop('order_status')

	so_new_details['order_date'] = datetime.datetime.strptime(
		so_new_details['order_date'], '%d-%b-%Y %H:%M:%S %p') if so_new_details[
		'order_date'] else None

	so_new_details['cancellation_date'] = datetime.datetime.strptime(
		so_new_details['cancellation_date'], '%d-%b-%Y %H:%M:%S %p') if so_new_details[
		'cancellation_date'] else None
	so_new_details['delivery_date'] = datetime.datetime.strptime(
		so_new_details['delivery_date'], '%d-%b-%Y %H:%M:%S %p') if so_new_details[
		'delivery_date'] else None

	total_due_amount = \
		so_new_details['total_due_amount'].replace('Rs.', '').replace(",", "").replace("(", "").replace(")", "")

	so_new_details['total_due_amount'] = float(total_due_amount if total_due_amount else 0)

	order_total = so_new_details['order_total'].replace('Rs.', '').replace(",", "").replace("(", "").replace(")", "")
	so_new_details['order_total'] = float(order_total if order_total else 0)

	total_payment_amount = \
		so_new_details['total_payment_amount'].replace('Rs.', '').replace(",", "").replace("(", "").replace(")", "")
	so_new_details['total_payment_amount'] = float(total_payment_amount if total_payment_amount else 0)

	so_new_details['consumed_quota'] = 0 if so_new_details['consumed_quota'] == "" else float(
		so_new_details['consumed_quota'])

	so_new_details['paid_flag'] = True if so_new_details['paid_flag'] == 'Y' else False
	so_new_details['digital_payment'] = True if so_new_details['digital_payment'] == 'Y' else False
	so_new_details['subsidized'] = True if so_new_details['subsidized'] == 'Y' else False
	so_new_details['subsidized_on_invoice_gen'] = True if so_new_details[
															  'subsidized_on_invoice_gen'] == 'Y' else False
	so_new_details['attempted_during_pdt_daytime'] = True if so_new_details[
																 'attempted_during_pdt_daytime'] == 'Y' else False
	so_new_details['preferred_flag'] = True if so_new_details['preferred_flag'] == 'Y' else False
	so_new_details['isi_mark_ho_plate'] = True if so_new_details['isi_mark_ho_plate'] == 'Y' else False
	so_new_details['dac_flag'] = True if so_new_details['dac_flag'] == 'Y' else False
	so_new_details['portability_flag'] = True if so_new_details['portability_flag'] == 'Y' else False
	so_new_details['tatkal_order'] = True if so_new_details.get('tatkal_flag') == 'Y' else False
	so_new_details['qc_due'] = True if so_new_details.get('qc_due') == 'Y' else False

	SalesOrder.objects.filter(pk=sales_order_id).update(**so_new_details)
	so_obj = SalesOrder.objects.get(pk=sales_order_id)
	if not new_order_status == existing_order_status:
		if new_order_status == 'Cancelled':
			so_obj.transition_sales_order_cancelled(
				description="{} - {}".format(so_obj.cancellation_date, so_obj.cancellation_reason))
		elif new_order_status == 'Completed':
			so_obj.transition_sales_order_completed()
		elif new_order_status == 'Invoiced':
			so_obj.transition_sales_order_invoiced()
		so_obj.last_synced_on = datetime.datetime.now()
		so_obj.save()
	return so_obj


def update_customer_profile_in_dca(relationship_details, customer_profile_id):
	"""
		{
		  "relationship_type": "LPG",
		  "consumer_no": "7225434466",
		  "dob": "10-Mar-1989",
		  "kyc_level": "6",
		  "contact_status": "Active",
		  "ucm_id": "1-85NWJMTD",
		  "relationship_channel": "SDMS",
		  "relationship_start_date": "10-Aug-2022",
		  "ekyc_flag": "Y",
		  "ekyc_date": "02-Jul-2022 02:24:17 PM",
		  "auth_type": "",
		  "customer_segment": "",
		  "kyc_approval_date": "",
		  "fleet_marketing": "N",
		  "kyc_approval_flag": "N",
		  "otp_verification": "",
		  "first_name": "Kiranjeet",
		  "last_name": "Kaur",
		  "gender": "Female",
		  "account_name": "",
		  "primary_account_address": "Room No 1 Floor No Ground Floor House No 12358 Street No 2 Tibba Road Kabir Nagar Near Beas Satsang Ghar Ward No 8 Post Office Basti Jodawal   Ludhiana LUDHIANA Punjab 141007",
		  "dealer_code": "",
		  "distributor_code": "0000305948",
		  "distributor_name": "ARUN INDANE PROP LUDHIANA ENT.",
		  "mobile_number": "7837521390",
		  "email_addresss": "",
		  "employee_code": "",
		  "vip_flag": "N",
		  "vip_description": "",
		  "old_vip_description": "",
		  "cancel_reason": "",
		  "cancel_remarks": "",
		  "delivery_type": "Home Delivery",
		  "service_area": "TIBBA ROAD",
		  "relationship_status": "ACTIVE",
		  "relationship_sub_status": "ACTIVE",
		  "waitlist_status": "SV Issued",
		  "kyc_date": "16-Jul-2022 08:20:21 AM",
		  "kyc_status": "Registered",
		  "application_id": "76-0000023022154",
		  "subsidy_status": "Start",
		  "nic_status": "Cleared",
		  "omc_status": "OMC Clear",
		  "revalidated": "N",
		  "ftl_reseller_flag": "N",
		  "tcs_flag": "N",
		  "pan_number": "",
		  "multiple_connection_blocking_reason": "",
		  "release_date": "",
		  "intimation_release_date": "",
		  "mandatory_inspection_due_date": "10-Aug-2027",
		  "last_inspection_date": "",
		  "mi_refusal_flag": "N",
		  "mi_refusal_date": "",
		  "tube_change_date": "10-Aug-2022",
		  "tube_change_due_date": "01-Jun-2027",
		  "suspend_deact_date": "",
		  "suspend_reason": "",
		  "tight_joint_replacement_flag": "N",
		  "tight_joint_replacement_date": "",
		  "approval_rejection_comments": "",
		  "group_member_status": "",
		  "consumer_category": "Domestic",
		  "scheme": "Central Govt Scheme",
		  "scheme_type": "Ujjwala - Extended",
		  "scheme_sub_type": "UJJWALA2",
		  "ujjwala_category": "14 point declaration -Others",
		  "priority": "N",
		  "consumer_type": "Double Bottle Connection",
		  "products": "Ujjwala - 5 Kg DBC Package",
		  "no_of_flats": "0",
		  "parent_consumer_id": "",
		  "scheme_opted": "Default Opt In",
		  "asset_count": "2",
		  "migrant": "Yes",
		  "scheme_onbaording_status": "Onboarded With CTC",
		  "contact_identities": [
			{
			  "": "",
			  "Identity Type": "INTERNAL-UJJWALA",
			  "Identity Method": "ANNEXURE 1",
			  "Identity Num": "4379",
			  "Comments": "",
			  "Identity Status": "Active",
			  "Aadhar Status": "",
			  "Issue Date": "",
			  "State of Issue": "",
			  "NPCI Batch Date": "",
			  "NPCI Batch Id": "",
			  "Verif Flag": "",
			  "Mode of Verification": "",
			  "Verification Date": "",
			  "Verification/Issuing Authority": "",
			  "Seeding Date": "11-Jul-2022",
			  "CTC Date": "",
			  "NPCIL Verif Status": "",
			  "Identity Source": "",
			  "NPCI Resp Date Time": "",
			  "ContactFileSrcPath": "",
			  "ContactFileSrcType": "",
			  "Profile Image Active": "N"
			},
			{
			  "": "",
			  "Identity Type": "INTERNAL-UJJWALA",
			  "Identity Method": "14 Point Exclusion Declaration",
			  "Identity Num": "4379",
			  "Comments": "",
			  "Identity Status": "Active",
			  "Aadhar Status": "",
			  "Issue Date": "",
			  "State of Issue": "",
			  "NPCI Batch Date": "",
			  "NPCI Batch Id": "",
			  "Verif Flag": "",
			  "Mode of Verification": "",
			  "Verification Date": "",
			  "Verification/Issuing Authority": "",
			  "Seeding Date": "11-Jul-2022",
			  "CTC Date": "",
			  "NPCIL Verif Status": "",
			  "Identity Source": "",
			  "NPCI Resp Date Time": "",
			  "ContactFileSrcPath": "",
			  "ContactFileSrcType": "",
			  "Profile Image Active": "N"
			},
			{
			  "": "",
			  "Identity Type": "POA-POI",
			  "Identity Method": "Aadhaar(UID)",
			  "Identity Num": "xxxxxxxx6884",
			  "Comments": "",
			  "Identity Status": "Active",
			  "Aadhar Status": "CTC",
			  "Issue Date": "",
			  "State of Issue": "",
			  "NPCI Batch Date": "",
			  "NPCI Batch Id": "",
			  "Verif Flag": "Y",
			  "Mode of Verification": "",
			  "Verification Date": "17-Jun-2023",
			  "Verification/Issuing Authority": "",
			  "Seeding Date": "",
			  "CTC Date": "17-Jun-2023",
			  "NPCIL Verif Status": "CTC",
			  "Identity Source": "",
			  "NPCI Resp Date Time": "17-Jun-2023 12:00:00 AM",
			  "ContactFileSrcPath": "1-630064071306",
			  "ContactFileSrcType": "URL",
			  "Profile Image Active": "N"
			},
			{
			  "": "",
			  "Identity Type": "PROFILE IMAGE",
			  "Identity Method": "PROFILE IMAGE",
			  "Identity Num": "xxxxxxxxx4379",
			  "Comments": "",
			  "Identity Status": "Active",
			  "Aadhar Status": "",
			  "Issue Date": "",
			  "State of Issue": "",
			  "NPCI Batch Date": "",
			  "NPCI Batch Id": "",
			  "Verif Flag": "Y",
			  "Mode of Verification": "",
			  "Verification Date": "",
			  "Verification/Issuing Authority": "",
			  "Seeding Date": "",
			  "CTC Date": "",
			  "NPCIL Verif Status": "",
			  "Identity Source": "",
			  "NPCI Resp Date Time": "",
			  "ContactFileSrcPath": "",
			  "ContactFileSrcType": "",
			  "Profile Image Active": "N"
			}
		  ],
		  "phones": [
			{
			  "": "",
			  "Primary": "Y",
			  "Active Flag": "",
			  "Phone #": "7837521390",
			  "Use Type": "",
			  "Phone Type": "Mobile",
			  "Description": "1-81G3VOUH",
			  "Consumer Id": "",
			  "Verify OTP": "",
			  "Verified Flag": "Y",
			  "Contact Phone Status": "Active"
			},
			{
			  "": "",
			  "Primary": "N",
			  "Active Flag": "",
			  "Phone #": "7889283509",
			  "Use Type": "",
			  "Phone Type": "Mobile",
			  "Description": "1-9OF5DP2R",
			  "Consumer Id": "",
			  "Verify OTP": "",
			  "Verified Flag": "Y",
			  "Contact Phone Status": "New"
			},
			{
			  "": "",
			  "Primary": "N",
			  "Active Flag": "",
			  "Phone #": "9815938017",
			  "Use Type": "",
			  "Phone Type": "Mobile",
			  "Description": "1-9OFG48I9",
			  "Consumer Id": "",
			  "Verify OTP": "",
			  "Verified Flag": "Y",
			  "Contact Phone Status": "Active"
			}
		  ],
		  "ekyc_details": [
			{
			  "": "",
			  "eKYC Num": "1-630064071322",
			  "Created On": "02-Jul-2022 02:24:18 PM",
			  "eKYC Type": "KYC",
			  "eKYC Sub Type": "Fresh KYC",
			  "eKYC Status": "Closed",
			  "Aadhar Number": "xxxxxxxx6884",
			  "Organization": "ARUN INDANE PROP LUDHIANA ENT.",
			  "First Name": "Kiranjeet",
			  "Last Name": "Kaur",
			  "Aadhar Seeding": "N",
			  "Channel": "Mobility",
			  "Authentication Type": "",
			  "Created By": ""
			}
		  ]
		}
	"""
	from connection_app.models import CustomerProfile

	if not relationship_details['consumer_category']:
		return True
	elif relationship_details['consumer_category'] in ['Commercial/Industrial', "Exempted"]:
		CustomerProfile.objects.filter(pk=customer_profile_id).update(**relationship_details)
	else:
		relationship_details['dob'] = datetime.datetime.strptime(relationship_details.get('dob'), "%d-%b-%Y") if \
			relationship_details.get('dob') else None

		relationship_details['relationship_start_date'] = datetime.datetime.strptime(
			relationship_details['relationship_start_date'], "%d-%b-%Y") if \
			relationship_details['relationship_start_date'] else None
		relationship_details['ekyc_date'] = datetime.datetime.strptime(relationship_details['ekyc_date'],
																	   '%d-%b-%Y %H:%M:%S %p') if \
			relationship_details['ekyc_date'] else None
		relationship_details['kyc_approval_date'] = datetime.datetime.strptime(relationship_details['kyc_approval_date'],
																	   '%d-%b-%Y %H:%M:%S %p') if \
			relationship_details['kyc_approval_date'] else None

		relationship_details['kyc_date'] = datetime.datetime.strptime(relationship_details['kyc_date'],
																	   '%d-%b-%Y %H:%M:%S %p') if \
			relationship_details['kyc_date'] else None
		relationship_details['release_date'] = datetime.datetime.strptime(relationship_details['release_date'],
																	   '%d-%b-%Y %H:%M:%S %p') if \
			relationship_details['release_date'] else None
		relationship_details['intimation_release_date'] = datetime.datetime.strptime(
			relationship_details['intimation_release_date'],
			'%d-%b-%Y %H:%M:%S %p') if \
			relationship_details['intimation_release_date'] else None
		relationship_details['mandatory_inspection_due_date'] = datetime.datetime.strptime(
			relationship_details['mandatory_inspection_due_date'], "%d-%b-%Y") if \
			relationship_details['mandatory_inspection_due_date'] else None
		relationship_details['last_inspection_date'] = datetime.datetime.strptime(
			relationship_details['last_inspection_date'], "%d-%b-%Y") if \
			relationship_details['last_inspection_date'] else None
		relationship_details['mi_refusal_date'] = datetime.datetime.strptime(
			relationship_details['mi_refusal_date'], "%d-%b-%Y") if \
			relationship_details['mi_refusal_date'] else None
		relationship_details['tube_change_date'] = datetime.datetime.strptime(
			relationship_details['tube_change_date'], "%d-%b-%Y") if \
			relationship_details['tube_change_date'] else None
		relationship_details['tube_change_due_date'] = datetime.datetime.strptime(
			relationship_details['tube_change_due_date'], "%d-%b-%Y") if \
			relationship_details['tube_change_due_date'] else None
		relationship_details['suspend_deact_date'] = datetime.datetime.strptime(
			relationship_details['suspend_deact_date'], "%d-%b-%Y") if \
			relationship_details['suspend_deact_date'] else None
		relationship_details['tight_joint_replacement_date'] = datetime.datetime.strptime(
			relationship_details['tight_joint_replacement_date'], "%d-%b-%Y") if \
			relationship_details['tight_joint_replacement_date'] else None

		relationship_details['ekyc_flag'] = True if relationship_details['ekyc_flag'] == 'Y' else False
		relationship_details['fleet_marketing'] = True if relationship_details['fleet_marketing'] == 'Y' else False
		relationship_details['kyc_approval_flag'] = True if relationship_details['kyc_approval_flag'] == 'Y' else False
		relationship_details['vip_flag'] = True if relationship_details['vip_flag'] == 'Y' else False
		relationship_details['revalidated'] = True if relationship_details['revalidated'] == 'Y' else False
		relationship_details['ftl_reseller_flag'] = True if relationship_details['ftl_reseller_flag'] == 'Y' else False
		relationship_details['tcs_flag'] = True if relationship_details['tcs_flag'] == 'Y' else False
		relationship_details['mi_refusal_flag'] = True if relationship_details['mi_refusal_flag'] == 'Y' else False
		relationship_details['tight_joint_replacement_flag'] = True if relationship_details[
																		   'tight_joint_replacement_flag'] == 'Y' else False
		relationship_details['priority'] = True if relationship_details['priority'] == 'Y' else False
		relationship_details['migrant'] = True if relationship_details['migrant'] == 'Yes' else False

		relationship_details['no_of_flats'] = int(relationship_details['no_of_flats']) if relationship_details[
			'no_of_flats'] else 0

		distributor = Distributor.objects.filter(code=relationship_details['distributor_code']).first()

		if not distributor:
			distributor = Distributor.objects.create(code=relationship_details['distributor_code'],
									   name=relationship_details['distributor_name'])
		relationship_details['distributor'] = distributor


		relationship_details['sdms_service_area'] = get_sdms_service_area(relationship_details['service_area'],
																		  distributor.code)
		CustomerProfile.objects.filter(pk=customer_profile_id).update(**relationship_details)


def update_booked_order_details_in_dca(sales_order_details, consumer_id, process_instance_id):
	"""
	order_status, sales_order_id, sales_order_number
	"""
	from connection_app.models import BookSalesOrder, SalesOrder

	bso_obj: BookSalesOrder = BookSalesOrder.objects.filter(camunda_process_id=process_instance_id).first()

	if sales_order_details.get('relationship_sub_status'):
		bso_obj.error_log = "Relationship Sub Status {} Processed To Update Customer Profile".format(
			sales_order_details.get('relationship_sub_status'))
		bso_obj.save()
		bso_obj.customer_profile.relationship_sub_status = sales_order_details.get('relationship_sub_status')
		bso_obj.customer_profile.save()
		django_rq.enqueue(start_read_customer_profile, args=(bso_obj.customer_profile.id,))
		return True

	bso_obj = BookSalesOrder.objects.filter(camunda_process_id=process_instance_id).first()

	if not bso_obj:
		raise Exception("Book Sales Order Object Not Found.")

	order_date = datetime.datetime.strptime(
		sales_order_details['order_date'], '%d-%b-%Y %H:%M:%S %p') if sales_order_details[
		'order_date'] else None

	so_obj = SalesOrder.objects.create(
		parent=bso_obj.customer_profile,
		sales_order=sales_order_details['sales_order'],
		relationship_id=sales_order_details['relationship_id'],
		order_status=sales_order_details['order_status'],
		order_date=order_date
	)

	so = sales_order_details.pop('sales_order')

	so_new_details: dict = sales_order_details

	# new_order_status = so_new_details.pop('order_status')

	so_new_details['order_date'] = datetime.datetime.strptime(
		so_new_details['order_date'], '%d-%b-%Y %H:%M:%S %p') if so_new_details[
		'order_date'] else None

	so_new_details['cancellation_date'] = datetime.datetime.strptime(
		so_new_details['cancellation_date'], '%d-%b-%Y %H:%M:%S %p') if so_new_details[
		'cancellation_date'] else None
	so_new_details['delivery_date'] = datetime.datetime.strptime(
		so_new_details['delivery_date'], '%d-%b-%Y %H:%M:%S %p') if so_new_details[
		'delivery_date'] else None

	so_new_details['total_due_amount'] = float(
		so_new_details['total_due_amount'].replace('Rs.', '').replace(",", ""))
	so_new_details['order_total'] = float(
		so_new_details['order_total'].replace('Rs.', '').replace(",", ""))
	so_new_details['total_payment_amount'] = float(
		so_new_details['total_payment_amount'].replace('Rs.', '').replace(",", ""))

	so_new_details['consumed_quota'] = 0 if so_new_details['consumed_quota'] == "" else float(
		so_new_details['consumed_quota'])

	so_new_details['paid_flag'] = True if so_new_details['paid_flag'] == 'Y' else False
	so_new_details['digital_payment'] = True if so_new_details['digital_payment'] == 'Y' else False
	so_new_details['subsidized'] = True if so_new_details['subsidized'] == 'Y' else False
	so_new_details['subsidized_on_invoice_gen'] = True if so_new_details[
															  'subsidized_on_invoice_gen'] == 'Y' else False
	so_new_details['attempted_during_pdt_daytime'] = True if so_new_details[
																 'attempted_during_pdt_daytime'] == 'Y' else False
	so_new_details['preferred_flag'] = True if so_new_details['preferred_flag'] == 'Y' else False
	so_new_details['isi_mark_ho_plate'] = True if so_new_details['isi_mark_ho_plate'] == 'Y' else False
	so_new_details['dac_flag'] = True if so_new_details['dac_flag'] == 'Y' else False
	so_new_details['portability_flag'] = True if so_new_details['portability_flag'] == 'Y' else False
	so_new_details['tatkal_order'] = True if so_new_details.get('tatkal_flag') == 'Y' else False
	so_new_details['qc_due'] = True if so_new_details.get('qc_due') == 'Y' else False
	so_new_details['auto_generated'] = True


	SalesOrder.objects.filter(pk=so_obj.id).update(**so_new_details)
	# so_obj = SalesOrder.objects.get(pk=sales_order_id)
	# if not new_order_status == existing_order_status:
	# 	if new_order_status == 'Cancelled':
	# 		so_obj.transition_sales_order_cancelled(
	# 			description="{} - {}".format(so_obj.cancellation_date, so_obj.cancellation_reason))
	# 	elif new_order_status == 'Completed':
	# 		so_obj.transition_sales_order_completed()
	# 	elif new_order_status == 'Invoiced':
	# 		so_obj.transition_sales_order_invoiced()
	# 	so_obj.save()
	print(so_obj)
	bso_obj.delete()


def update_service_area_in_customer_profile(consumer_id, service_area):
	from connection_app.models import CustomerProfile

	cp_obj: CustomerProfile = CustomerProfile.objects.filter(consumer_id=consumer_id).first()

	if cp_obj:
		cp_obj.sdms_service_area = get_sdms_service_area(service_area, cp_obj.distributor.code)
		cp_obj.service_area = service_area
		cp_obj.save()
	else:
		raise Exception("Customer Profile Not Found.")


def get_next_next_nine_oclock():
	now = datetime.datetime.now()
	# today_nine_am = now.replace(hour=9, minute=0, second=0, microsecond=0)
	#
	# if now < today_nine_am:
	# 	# First 9:00 AM is today
	# 	next_nine_am = today_nine_am
	# else:
	# 	# First 9:00 AM is tomorrow
	# 	next_nine_am = today_nine_am + datetime.timedelta(days=1)
	#
	# # Second 9:00 AM after now
	# next_next_nine_am = next_nine_am + datetime.timedelta(days=1)
	#
	# return next_next_nine_am
	return now


def update_returned_booked_order(sales_order_id, status):
	from connection_app.models import SalesOrder

	so_obj = SalesOrder.objects.get(pk=sales_order_id)

	variables = {}
	if status == 'RETURNED':
		so_obj.transition_sales_order_returned()
		variables['next_order_return_date_time'] = {"value": get_next_next_nine_oclock().isoformat()}
		variables['order_canceled'] = {"value": False}
	elif status == 'CANCELLED':
		so_obj.transition_sales_order_cancelled()
		variables['order_canceled'] = {"value": True}
	elif status == 'NOT_FOUND':
		so_obj.transition_sales_order_not_found()
		variables['order_canceled'] = {"value": True}

	so_obj.save()
	return variables
