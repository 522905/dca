import textwrap
import datetime

from django.http import JsonResponse
from django.views.generic import FormView

from connection_app.models import ConnectionApplication, CustomerProfile
from ujjwala.forms import BarcodeForm


def format_consumer_id(consumer_id: str) -> str:
	"""Formats the consumer ID to ensure it has the correct length and format."""
	if len(consumer_id) < 11:
		return consumer_id[:2] + "000000" + consumer_id[8:]
	return consumer_id


def proces_address(add):
	if isinstance(add,dict):
		return (f"HNo-{add.get('house_no',' ')} {add.get('street_no','')} {add.get('landmark','')}"
						  f"{add.get('village','')} {add.get('city','')} {add.get('pincode',' ')}")


class NewBarCodeLabelPrintView(FormView):
	template_name = "ujjwala/barcode_print/label_print.html"
	form_class = BarcodeForm

	def form_valid(self, form):
		"""Handles form submission and processes barcode label generation."""
		user_id = format_consumer_id(form.cleaned_data["user_id"])
		print(f"the user_id we get is {user_id}")
		try:
			application = CustomerProfile.objects.get(consumer_id=user_id)
		except ConnectionApplication.DoesNotExist:
			print("the application not exist")
			return JsonResponse({"status": "error", "message": "Application not found."}, status=400)

		# Generate context data for the PRN file
		context = self.create_context_data(application)

		# Read and replace PRN template placeholders
		try:
			with open("ujjwala/templates/ujjwala/general_blue_book.prn", "rb") as _file:
				file_data = _file.read()
				for key, value in context.items():
					file_data = file_data.replace(b'{{' + key.encode() + b'}}', str(value).encode())
		except FileNotFoundError:
			return JsonResponse({"status": "error", "message": "PRN template file not found."}, status=500)
		except Exception as e:
			return JsonResponse({"status": "error", "message": f"Error processing PRN file: {str(e)}"}, status=500)

		return JsonResponse({"status": "success", "prn_data": file_data.decode()})

	def create_context_data(self, obj: CustomerProfile) -> dict:
		"""Generates the context dictionary with consumer and address details."""
		consumer_no = obj.consumer_id
		context_dict = {"consumer_no": consumer_no}

		# Format address
		address = obj.address if obj.address is not None else obj.primary_account_address
		address_lines = textwrap.wrap(address.replace(".", ""), 40)  # Wrapping address lines
		address_lines = address_lines[:3] + ['', '', '']  # Ensure there are exactly 3 lines
		context_dict.update({f'address{index + 1}': val for index, val in enumerate(address_lines)})

		profile = ConnectionApplication.objects.filter(consumer_id=obj.consumer_id).first()
		dca_id = profile.id if profile else " "
		print(f"the refreal code is {profile.referral_code}")
		# Additional user details
		context_dict.update({
			"name": obj.name,
			"id": dca_id,
			"date": datetime.datetime.today().strftime("%d/%m/%Y, %H:%M"),
			"operator_name": self.request.user.username,
			"referral_code": profile.referral_code,
		})

		return context_dict
