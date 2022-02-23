from django import forms
from django.forms import NumberInput
from django.utils import timezone
from django_currentuser.middleware import get_current_user
from django.contrib.admin.widgets import AdminDateWidget

from connection_app.enums import ConnectionApplicationProcessType, ConnectionApplicationLeadStatus
from inactive_customers.models import InactiveCustomer


class SubmitLead(forms.Form):
	description = forms.CharField(widget=forms.Textarea, label='Remarks', required=False)

	def clean(self):
		data = self.cleaned_data
		return data


class ConnectionVerificationResult(forms.Form):
	required = forms.BooleanField(
		label="Required ?", required=False, help_text="Check If Required For Not Interested Uncheck"
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
