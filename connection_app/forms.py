import json

from django import forms
from django.forms import NumberInput
from django_currentuser.middleware import get_current_user

from connection_app.enums import ConnectionApplicationProcessType, ConnectionApplicationLeadStatus, \
	ConnectionApplicationDocumentsEnum, HouseTypeEnum, PostInspectionActivityTypeEnum, PostInspectionStatusEnum, \
	TemplateEnum, ProofTypeEnum
from inactive_customers.models import InactiveCustomer
from reference_data.models import ServiceType, Product, SDMSServiceRequest
from teams.models import SDMSServiceArea, UserProfile


class SubmitLead(forms.Form):
	description = forms.CharField(widget=forms.Textarea, label='Remarks', required=False)

	def clean(self):
		data = self.cleaned_data
		return data


class ConnectionVerificationResult(forms.Form):
	required = forms.ChoiceField(
		label="Required ?",
		required=True,
		help_text="Check If Required",
		choices=[
			('', '-- Select If Required Or Not --'),
			('Y', 'Yes'), 
			('N', 'No')
		]
	)
	required_by = forms.DateTimeField(
		label="Select Required Date :", required=False, widget=NumberInput(attrs={'type': 'date'}),
		help_text="Choose required date"
	)
	applicant_remarks = forms.CharField(
		widget=forms.Textarea, required=False, help_text="Enter any remarks"
	)

	def clean(self):
		data = self.cleaned_data
		return data


class BackOfficeForm(forms.Form):
	consumer_id = forms.CharField(required=False, help_text="Enter 'Consumer Id'")
	process_type = forms.ChoiceField(
		choices=ConnectionApplicationProcessType.choices,
		help_text="Select Process Type New Connection, Regularisation, Re-activation"
	)
	description = forms.CharField(
		widget=forms.Textarea, label='Remarks', required=False, help_text="Enter description"
	)

	def clean_consumer_id(self):
		value = self.cleaned_data['consumer_id']
		if not value:
			return value

		from connection_app.models import ConnectionApplication
		if ConnectionApplication.objects.filter(consumer_id=value).exclude(
				status=ConnectionApplicationLeadStatus.NOT_INTERESTED
		).exists():
			raise forms.ValidationError("Consumer Id is already booked against another application")

		try:
			InactiveCustomer.objects.get(consumer_id=value)
		except InactiveCustomer.DoesNotExist:
			raise forms.ValidationError("Invalid Consumer Id")

		return value

	def clean(self):
		data = self.cleaned_data
		if data.get('process_type', '') in (
				ConnectionApplicationProcessType.REGULARISATION,
				ConnectionApplicationProcessType.REACTIVATION
		):
			if not data.get('consumer_id', ''):
				raise forms.ValidationError("Consumer Id is mandatory for Regularisation & Reactivation")
		else:
			data.pop('consumer_id', '')
		return data


class BackOfficeNewConnection(forms.Form):
	consumer_id = forms.CharField(required=True, help_text="Enter Consumer Id")
	sv_doc_url = forms.URLField(widget=forms.HiddenInput)
	description = forms.CharField(
		widget=forms.Textarea, label='Remarks', required=False
	)

	def clean(self):
		data = super().clean()
		if not data.get("sv_doc_url") or not data.get("consumer_id"):
			raise forms.ValidationError("Consumer Id & SV Document are required")
		return data


class BackOfficeRegularisation(forms.Form):
	# consumer_id = forms.CharField(required=True, help_text="Enter 'Consumer Id'")
	sv_doc_url = forms.URLField(widget=forms.HiddenInput)
	description = forms.CharField(
		widget=forms.Textarea, label='Remarks', required=False
	)

	def clean(self):
		data = super().clean()
		if not data.get("sv_doc_url"):
			raise forms.ValidationError("Upload SV Document")
		return data


class BackOfficeReactivation(forms.Form):
	description = forms.CharField(
		widget=forms.Textarea, label='Remarks', required=False
	)

	def clean(self):
		data = self.cleaned_data
		return data


class FrontOfficeCompleted(forms.Form):
	verified = forms.BooleanField(
		required=False, help_text="Check If Verified Uncheck To Send Back Office For Recheck"
	)
	phone_updated = forms.BooleanField(
		required=False, help_text="Check If Phone Number Updated"
	)
	description = forms.CharField(
		widget=forms.Textarea, label='Remarks', required=False
	)

	def clean(self):
		data = self.cleaned_data
		return data


class DocumentsReupload(forms.Form):
	documents_required_for_reupload = forms.MultipleChoiceField(
		widget=forms.SelectMultiple,
		choices=ConnectionApplicationDocumentsEnum.get_skipped_additional_choices(),
		help_text="Documents to prompt for reupload"
	)

	remarks = forms.CharField(
		widget=forms.Textarea,
		label='Remarks For Customer',
		required=True
	)

	def clean(self):
		data = self.cleaned_data
		if data.get('documents_required_for_reupload', []):
			data['documents_required_for_reupload'] = json.dumps(data['documents_required_for_reupload'])
		return data


class InstallationReviewForm(forms.Form):
	verified = forms.BooleanField(
		required=False,
		help_text="Check If Installation is safe as per standards"
	)

	remarks = forms.CharField(
		widget=forms.Textarea,
		label='Remarks (Will be displayed to customer)',
		required=True
	)


class CustomerProfileSearchForm(forms.Form):
	consumer_id = forms.CharField(required=False)
	mobile_number = forms.CharField(required=False)
	# profile_id = forms.CharField(required=False, widget=forms.NumberInput)

	def clean(self):
		data = self.cleaned_data
		if not data.get('consumer_id') and not data.get('mobile_number'):
			raise forms.ValidationError("Please enter one of 'Consumer Id' or 'Mobile Number'")


class PromotionalSaleSearchForm(forms.Form):
	phone_number = forms.CharField(required=True)


class UpdateAddressForm(forms.Form):
	house_type = forms.ChoiceField(
		widget=forms.Select,
		choices=HouseTypeEnum.choices,
		required=False
	)
	house_no = forms.CharField(
		widget=forms.TextInput, label='House No.', required=True
	)
	room_no = forms.CharField(
		widget=forms.TextInput, label='Room No', required=True
	)
	floor = forms.CharField(
		widget=forms.TextInput, label='Floor', required=True
	)
	street_no = forms.CharField(
		widget=forms.TextInput, label='Street No', required=True
	)
	landmark = forms.CharField(
		widget=forms.TextInput, label='Landmark', required=True
	)
	village = forms.CharField(
		widget=forms.TextInput, label='Village', required=True
	)
	# ward_no = forms.CharField(
	# 	widget=forms.TextInput, label='Ward No', required=True
	# )
	# post_office = forms.CharField(
	# 	widget=forms.TextInput, label='Post Office', required=True
	# )
	pincode = forms.CharField(
		widget=forms.TextInput, label='Pin Code', required=True
	)
	mobile_number = forms.CharField(
		widget=forms.TextInput, label='Mobile Number', required=True
	)

	def __init__(self, post_inspection=None, *args, **kwargs):
		super().__init__(*args, **kwargs)
		self.post_inspection = post_inspection

	def save(self):
		data = self.cleaned_data
		obj = self.post_inspection
		obj.address_json = {
			"house_type": data.get('house_type', ''),
			"house_no": data.get('house_no', ''),
			"room_no": data.get('room_no', ''),
			"floor": data.get('floor', ''),
			"street_no": data.get('street_no', ''),
			"landmark": data.get('landmark', ''),
			"village": data.get('village', ''),
			# "ward_no": data.get('ward_no', ''),
			# "post_office": data.get('post_office', ''),
			"pincode": data.get('pincode', '')
		}
		obj.mobile_number = data['mobile_number']
		obj.save()

		post_inspection_activity_obj = self.post_inspection.activities.get(
			activity_type=PostInspectionActivityTypeEnum.ADDRESS_UPDATE)
		post_inspection_activity_obj.completed = True
		post_inspection_activity_obj.completed_by = get_current_user()
		post_inspection_activity_obj.data = data
		post_inspection_activity_obj.save()


class PostInspectionForm(forms.Form):
	def __init__(self, post_inspection, *args, **kwargs):
		super().__init__(*args, **kwargs)
		self.post_inspection = post_inspection

	def clean(self):
		data = self.cleaned_data

		for activity in self.post_inspection.activities.all():
			if not activity.completed:
				raise forms.ValidationError(f"Activity: {activity.activity_type} is not completed.")

		# self.post_inspection.mechanic = get_current_user()
		self.post_inspection.transition_post_inspection_submitted(mechanic=get_current_user())
		self.post_inspection.save()
		return data


class KitchenPostInspectionForm(forms.Form):
	kitchen_photo = forms.CharField(
		widget=forms.TextInput, label='Kitchen Photo', required=True
	)

	def __init__(self, post_inspection=None, *args, **kwargs):
		super().__init__(*args, **kwargs)
		self.post_inspection = post_inspection

	def save(self):
		data = self.cleaned_data

		self.post_inspection.documents.filter(
			type=ConnectionApplicationDocumentsEnum.KITCHEN_PHOTO
		).delete()

		self.post_inspection.documents.create(
			type=ConnectionApplicationDocumentsEnum.KITCHEN_PHOTO,
			link=data.get('link')
		)
		self.post_inspection.save()

		post_inspection_activity_obj = self.post_inspection.activities.get(
			activity_type=PostInspectionActivityTypeEnum.KITCHEN_PHOTO_UPDATE)
		post_inspection_activity_obj.completed = True
		post_inspection_activity_obj.completed_by = get_current_user()
		post_inspection_activity_obj.data = data
		post_inspection_activity_obj.save()


class PreviewPostInspectionForm(forms.Form):
	latitude = forms.CharField(
		widget=forms.TextInput(attrs={'readonly': 1}), max_length=32, label='Latitude', required=True
	)
	longitude = forms.CharField(
		widget=forms.TextInput(attrs={'readonly': 1}), max_length=32, label='Longitude', required=True
	)
	accuracy = forms.CharField(
		widget=forms.TextInput(attrs={'readonly': 1}), max_length=24, label='Accuracy', required=True
	)
	main_gate = forms.CharField(
		widget=forms.HiddenInput, label='Main Gate Photo', required=True
	)

	def __init__(self, post_inspection=None, *args, **kwargs):
		super().__init__(*args, **kwargs)
		self.post_inspection = post_inspection

	def clean(self):
		data = self.cleaned_data
		return data

	def save(self):
		data = self.cleaned_data

		self.post_inspection.latitude = data['latitude']
		self.post_inspection.longitude = data['longitude']
		self.post_inspection.accuracy = data['accuracy']

		data = self.cleaned_data

		self.post_inspection.documents.filter(
			type=ConnectionApplicationDocumentsEnum.MAIN_GATE
		).delete()

		self.post_inspection.documents.create(
			type=ConnectionApplicationDocumentsEnum.MAIN_GATE,
			link=data.get('link')
		)
		self.post_inspection.save()

		post_inspection_activity_obj = self.post_inspection.activities.get(
			activity_type=PostInspectionActivityTypeEnum.MAIN_GATE_PHOTO_UPDATE)
		post_inspection_activity_obj.completed = True
		post_inspection_activity_obj.completed_by = get_current_user()
		post_inspection_activity_obj.data = data
		post_inspection_activity_obj.save()


class PostInspectionStartForm(forms.Form):
	form_type = forms.CharField(widget=forms.HiddenInput, initial='initial_form')
	consumer_id = forms.CharField(required=False)
	mobile_number = forms.CharField(required=False)


class UIDPostInspectionForm(forms.Form):
	uid_front_photo = forms.CharField(
		widget=forms.TextInput, label='Front Photo', required=True
	)

	uid_back_photo = forms.CharField(
		widget=forms.TextInput, label='Front Photo', required=True
	)

	def __init__(self, post_inspection=None, *args, **kwargs):
		super().__init__(*args, **kwargs)
		self.post_inspection = post_inspection

	def save(self):
		data = self.cleaned_data

		from connection_app.models import CustomerProfile, CustomerProfileDocuments

		customer_profile: CustomerProfile = self.post_inspection.parent

		cpd_obj = CustomerProfileDocuments.objects.filter(parent=customer_profile,
														  type=ConnectionApplicationDocumentsEnum.UID_FRONT).first()
		if not cpd_obj:
			CustomerProfileDocuments.objects.create(
				parent=self.post_inspection.parent,
				type=ConnectionApplicationDocumentsEnum.UID_FRONT,
				link=data['uid_front_photo']
			)

		cpd_obj = CustomerProfileDocuments.objects.filter(parent=customer_profile,
													  type=ConnectionApplicationDocumentsEnum.UID_BACK).first()

		if not cpd_obj:
			CustomerProfileDocuments.objects.create(
				parent=self.post_inspection.parent,
				type=ConnectionApplicationDocumentsEnum.UID_BACK,
				link=data['uid_back_photo']
			)

		post_inspection_activity_obj = self.post_inspection.activities.get(
			activity_type=PostInspectionActivityTypeEnum.UID_PHOTO_UPDATE)
		post_inspection_activity_obj.completed = True
		post_inspection_activity_obj.completed_by = get_current_user()
		post_inspection_activity_obj.data = data
		post_inspection_activity_obj.save()


class ProfilePhotoPostInspectionForm(forms.Form):
	profile_photo = forms.CharField(
		widget=forms.TextInput, label='Profile Photo', required=True
	)

	def __init__(self, post_inspection=None, *args, **kwargs):
		super().__init__(*args, **kwargs)
		self.post_inspection = post_inspection

	def save(self):
		data = self.cleaned_data

		from connection_app.models import CustomerProfile, CustomerProfileDocuments

		customer_profile: CustomerProfile = self.post_inspection.parent

		cpd_obj = CustomerProfileDocuments.objects.filter(parent=customer_profile,
														  type=ConnectionApplicationDocumentsEnum.CUSTOMER_PHOTO).first()
		if not cpd_obj:
			CustomerProfileDocuments.objects.create(
				parent=self.post_inspection.parent,
				type=ConnectionApplicationDocumentsEnum.CUSTOMER_PHOTO,
				link=data['profile_photo']
			)

		post_inspection_activity_obj = self.post_inspection.activities.get(
			activity_type=PostInspectionActivityTypeEnum.PROFILE_PHOTO_UPDATE)
		post_inspection_activity_obj.completed = True
		post_inspection_activity_obj.completed_by = get_current_user()
		post_inspection_activity_obj.data = data
		post_inspection_activity_obj.save()


class SurakshaPipePostInspectionForm(forms.Form):
	to_be_billed = forms.ChoiceField(
		label="To Be Billed ?",
		required=True,
		help_text="",
		choices=[
			('', '-- Select To Be Billed --'),
			('YES', 'Yes'),
			('NO', 'No')
		]
	)
	suraksha_pipe_photo = forms.CharField(
		widget=forms.TextInput, label='Suraksha Pipe Photo', required=True
	)

	def __init__(self, post_inspection=None, *args, **kwargs):
		super().__init__(*args, **kwargs)
		self.post_inspection = post_inspection

	def save(self):
		data = self.cleaned_data

		from connection_app.models import CustomerProfile, CustomerProfileDocuments

		customer_profile: CustomerProfile = self.post_inspection.parent

		cpd_obj = CustomerProfileDocuments.objects.filter(parent=customer_profile,
														  type=ConnectionApplicationDocumentsEnum.SURAKSHA_PIPE_PHOTO).first()
		if not cpd_obj:
			CustomerProfileDocuments.objects.create(
				parent=self.post_inspection.parent,
				type=ConnectionApplicationDocumentsEnum.SURAKSHA_PIPE_PHOTO,
				link=data['suraksha_pipe_photo']
			)

		post_inspection_activity_obj = self.post_inspection.activities.get(
			activity_type=PostInspectionActivityTypeEnum.SURAKSHA_PIPE_UPDATE)
		post_inspection_activity_obj.completed = True
		post_inspection_activity_obj.completed_by = get_current_user()
		post_inspection_activity_obj.data = data
		post_inspection_activity_obj.save()


class GenerateNonCustomerLeadForm(forms.Form):
	name = forms.CharField(max_length=128)
	mobile_number = forms.CharField(max_length=10)
	service_list = forms.MultipleChoiceField(
		widget=forms.CheckboxSelectMultiple(attrs={'class': 'choice_block'}),
		required=True,
		label="",
		help_text="",
		choices=[
			('', '-- Select Services --'),
		]
	)

	def __init__(self, service_type_choices=None, *args, **kwargs):
		super().__init__(*args, **kwargs)
		self.fields['service_list'].choices = service_type_choices


class CustomerProfileDocumentUploadForm(forms.Form):
	document_type = forms.ChoiceField(
		choices=ConnectionApplicationDocumentsEnum.choices,
		required=False,
		disabled=True
	)
	document_link = forms.CharField(
		widget=forms.HiddenInput, label='Document', required=True
	)


class SalesOrderDetailViewForm(forms.Form):
	cancel_sales_order = forms.ChoiceField(
		label="Cancel Sales Order ?",
		required=True,
		help_text="",
		choices=[
			('', '-- Select To be cancel sales order --'),
			('YES', 'Yes'),
			('NO', 'No')
		]
	)
	cancel_auto_booking = forms.BooleanField(
		widget=forms.CheckboxInput,
		label="Cancel Auto Book",
		help_text="Cancel Auto Book Sales Order"
	)


class SalesOrderPortabilityForm(forms.Form):
	sales_order_number = forms.CharField(
		max_length=52, required=True
	)
	distributor = forms.ChoiceField(
		label="Distributor",
		required=True,
		help_text="",
		choices=[
			('', '-- Select Distributor --'),
		]
	)

	def __init__(self, distributor_list=None, *args, **kwargs):
		super().__init__(*args, **kwargs)
		self.fields['distributor'].choices = distributor_list


class SDMSServiceAreaForm(forms.Form):
	distributor = forms.MultipleChoiceField(
		widget=forms.CheckboxSelectMultiple,
		label="Distributor",
		required=False,
		help_text="",
		choices=[]
	)
	sdms_service_area = forms.MultipleChoiceField(
		widget=forms.CheckboxSelectMultiple,
		label="SDMS Service Area",
		required=False,
		help_text="",
		choices=[]
	)

	def __init__(self, user_profile: UserProfile=None, *args, **kwargs):
		super().__init__(*args, **kwargs)
		self.fields['sdms_service_area'].choices = [
			(i.area_name, i.area_name) for i in user_profile.sdms_service_areas.all()
		]
		self.fields['distributor'].choices = [
			(i.distributor.code, "{} - {}".format(i.distributor.code, i.distributor.name)) for i in user_profile.sdmsuser_set.all().distinct('distributor')
		]


class UploadDataForm(forms.Form):
	template = forms.ChoiceField(
		widget=forms.Select,
		choices=TemplateEnum.choices,
		required=True
	)
	file = forms.FileField(label='Select a CSV file')

	def clean(self):
		form_data = self.cleaned_data

		if not form_data.get('file').name.endswith('.csv'):
			raise forms.ValidationError("Invalid CSV File.")
		return form_data


class ImportDataForm(forms.Form):
	template = forms.ChoiceField(
		widget=forms.Select,
		choices=TemplateEnum.choices,
		required=True
	)
	file = forms.FileField(label='Select a CSV file')

	def clean(self):
		form_data = self.cleaned_data

		if not form_data.get('file').name.endswith('.csv'):
			raise forms.ValidationError("Invalid CSV File.")
		return form_data


class CancelAutoGeneratedSalesOrderForm(forms.Form):
	cancel = forms.BooleanField(
		widget=forms.CheckboxInput,
		required=True
	)


class BookSalesOrderForm(forms.Form):
	schedule = forms.BooleanField(
		widget=forms.CheckboxInput,
		required=True
	)


class CustomerProfileSettingsForm(forms.Form):
	do_not_auto_generate_sales_order = forms.BooleanField(
		widget=forms.CheckboxInput,
		required=False,
		label="Do Not Auto Generate Sales Order"
	)
	is_dirty = forms.BooleanField(widget=forms.CheckboxInput,
		required=False,
		label="Is Dirty"
	)


class GenerateLeadFormCustomerProfileForm(forms.Form):
	name = forms.CharField(max_length=128)
	mobile_number = forms.CharField(max_length=10)
	address = forms.CharField(
		widget=forms.Textarea(attrs={'rows': 3})
	)


class GenerateLeadForm(GenerateLeadFormCustomerProfileForm):
	customer_profile_id = forms.CharField(
		widget=forms.HiddenInput,
		required=False
	)
	service_types = forms.ModelMultipleChoiceField(
		queryset=ServiceType.objects.filter(enabled=True),
		widget=forms.CheckboxSelectMultiple,
		required=False
	)
	# products = forms.ModelMultipleChoiceField(
	# 	queryset=Product.objects.filter(enabled=True),
	# 	widget=forms.CheckboxSelectMultiple,  # Change this in the template to render in a grid
	# 	required=False
	# )
	sdms_service_requests = forms.ModelChoiceField(
		queryset=SDMSServiceRequest.objects.filter(enabled=True),
		widget=forms.Select,  # This will be dynamically handled in the template
		required=False
	)


class OverrideSalesForm(forms.Form):
	customer_photo = forms.CharField(
		widget=forms.HiddenInput, label='Customer Photo', required=True
	)
	phone_no = forms.CharField(
		widget=forms.TextInput, label='Phone No', required=True
	)

	def __init__(self, *args, **kwargs):
		super().__init__(*args, **kwargs)


class PromotionalSaleForm(forms.Form):
	CYLINDER_TYPE_CHOICES = [
		('14.2Kg', '14.2Kg'),
		('5Kg', '5Kg'),
	]
	AGENCY_NAME_CHOICES = [
		('Arun Indane', 'Arun Indane'),
		('Arun Gas Service', 'Arun Gas Service'),
		('Other', 'Other'),
	]
	agency_name = forms.ChoiceField(choices=AGENCY_NAME_CHOICES, label='Agency Name', required=True)
	other_agency_name = forms.CharField(widget=forms.HiddenInput(), required=False)
	consumer_id = forms.CharField(widget=forms.TextInput, label='Consumer Id', required=False)
	customer_name = forms.CharField(widget=forms.TextInput, label='Customer Name', required=True)
	customer_address = forms.CharField(widget=forms.Textarea, label='Address', required=False)
	sale_order_no = forms.CharField(widget=forms.TextInput, label='Sales Order No', required=True)
	phone_no = forms.CharField(widget=forms.TextInput, label='Phone No', required=True)
	cylinder_type = forms.ChoiceField(choices=CYLINDER_TYPE_CHOICES, label='Cylinder Type', required=True)
	customer_photo = forms.CharField(widget=forms.HiddenInput, label='Customer Photo', required=True)


	def clean(self):
		from connection_app.models import PromotionalSale
		data = self.cleaned_data

		# Replace 'Other' with the entered agency name if applicable
		if data.get('agency_name') == 'Other':
			if not data.get('other_agency_name'):
				raise forms.ValidationError("Please enter the agency name if 'Other' is selected.")
			data['agency_name'] = data.get('other_agency_name')

		# Validate sales order uniqueness
		if PromotionalSale.objects.filter(sale_order_no=data['sale_order_no']).exists():
			raise forms.ValidationError("Sales Order No already exists.")

		return data


class PromotionalSalePrizeAllocationForm(forms.Form):
	proof_type = forms.ChoiceField(
		choices=ProofTypeEnum.choices,
		help_text="Select Process Type New Connection, Regularisation, Re-activation"
	)
	proof_id_no = forms.CharField(widget=forms.TextInput, required=True)
	proof_photo_1 = forms.CharField(
		widget=forms.HiddenInput, label='Proof Photo 1', required=True
	)
	proof_photo_2 = forms.CharField(
		widget=forms.HiddenInput, label='Proof Photo 2', required=False
	)
	prize_given_photo = forms.CharField(
		widget=forms.HiddenInput, label='Prize Photo', required=True
	)
	cylinder_type = forms.CharField(widget=forms.TextInput, label='Cylinder Type', required=True)

	def __init__(self, promotional_sale_customer=None, cylinder_type=None, promotional_sales=None, *args, **kwargs):
		super().__init__(*args, **kwargs)
		self.promotional_sales = promotional_sales
		self.cylinder_type = cylinder_type
		self.promotional_sale_customer = promotional_sale_customer
		self.fields['cylinder_type'].initial = cylinder_type
		self.fields['cylinder_type'].widget.attrs['readonly'] = True


	def clean(self):
		data = self.cleaned_data
		# Check if proof id already exists
		if data.get('proof_type') == 'AADHAR' and not data.get('proof_photo_2'):
			raise forms.ValidationError("Aadhar Front and Back Both Photos are required.")
		return data
