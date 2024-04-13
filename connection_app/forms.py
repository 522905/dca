import datetime
import json
import string

import track
from django import forms
from django.contrib.contenttypes.models import ContentType
from django.forms import NumberInput
from django.utils import timezone
from django_currentuser.middleware import get_current_user
from django.contrib.admin.widgets import AdminDateWidget

from communication_log.models import CommunicationLog
from connection_app.enums import ConnectionApplicationProcessType, ConnectionApplicationLeadStatus, \
	ConnectionApplicationDocumentsEnum, HouseTypeEnum, PostInspectionStatusEnum
from domestic_app import settings
from inactive_customers.models import InactiveCustomer
from otp.models import Otp
from otp.serializer import __get_ref_no__, id_generator
from ujjwala.communication_functions import send_whatsapp_message, send_sms


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

	def clean(self):
		data = self.cleaned_data
		if not data.get('verified'):
			data['documents_required_for_reupload'] = json.dumps([ConnectionApplicationDocumentsEnum.KITCHEN_PHOTO])
		else:
			data['documents_required_for_reupload'] = '[]'
		return data


class ChangeAddressForm(forms.Form):
	update_address = forms.BooleanField(
		widget=forms.CheckboxInput, label='Click To Change Address', required=False
	)
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
	ward_no = forms.CharField(
		widget=forms.TextInput, label='Ward No', required=True
	)
	post_office = forms.CharField(
		widget=forms.TextInput, label='Post Office', required=True
	)
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
		data['address_json'] = {
			"house_type": data.get('house_type', ''),
			"house_no": data.get('house_no', ''),
			"room_no": data.get('room_no', ''),
			"floor": data.get('floor', ''),
			"street_no": data.get('street_no', ''),
			"landmark": data.get('landmark', ''),
			"village": data.get('village', ''),
			"ward_no": data.get('ward_no', ''),
			"post_office": data.get('post_office', ''),
			"pincode": data.get('pincode', '')
		}
		obj.address_json = data['address_json']
		obj.mobile_number = data['mobile_number']
		obj.transition_post_inspection_changed_address(by=get_current_user(), description=data['address_json'])
		obj.save()


class KitchenPostInspectionForm(forms.Form):
	kitchen_photo = forms.CharField(
		widget=forms.TextInput, label='Kitchen Photo', required=True
	)

	def __init__(self, post_inspection=None, *args, **kwargs):
		super().__init__(*args, **kwargs)
		self.post_inspection = post_inspection

	def save(self):
		data = self.cleaned_data
		self.post_inspection.transition_post_inspection_kitchen_photo_uploaded(
			link=data['kitchen_photo'],
			by=get_current_user(),
		)
		self.post_inspection.save()


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


		self.post_inspection.transition_post_inspection_submitted(
			link=data['main_gate'],
			by=get_current_user(),
			description="Latitude: {}, Longitude: {}, Accuracy: {}".format(
				data['latitude'], data['longitude'], data['accuracy'])
		)
		self.post_inspection.save()

	def get_form_initial(self, step):
		init_data = self.initial_dict.get(step, {})
		if step == 'customer_kitchen_form':
			init_data.update({'customer_profile_id': self.kwargs.get('pk')})
		return init_data

	def get_context_data(self, *args, **kwargs):
		con = super().get_context_data(*args, **kwargs)

		from connection_app.models import CustomerProfile
		cp_obj = CustomerProfile.objects.filter(id=self.kwargs.get('pk')).first()
		con.update({
			"obj": cp_obj
		})
		return con


class PostInspectionStartForm(forms.Form):
	form_type = forms.CharField(widget=forms.HiddenInput, initial='initial_form')
	consumer_id = forms.CharField(required=False)
	mobile_number = forms.CharField(required=False)
