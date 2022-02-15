from django import forms
from django.forms import NumberInput
from django.utils import timezone
from django_currentuser.middleware import get_current_user
from django.contrib.admin.widgets import AdminDateWidget

from connection_app.enums import ConnectionApplicationProcessType


class SubmitLead(forms.Form):
	description = forms.CharField(widget=forms.Textarea, label='Remarks', required=False)

	def clean(self):
		data = self.cleaned_data
		data['by'] = get_current_user()
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
		data['by'] = get_current_user()
		return data


class BackOfficeForm(forms.Form):
	consumer_id = forms.CharField(required=True, help_text="Enter 'Consumer Id'")
	process_type = forms.ChoiceField(
		choices=ConnectionApplicationProcessType.choices,
		help_text="Select Process Type New Connection, Regularisation, Re-activation"
	)
	description = forms.CharField(
		widget=forms.Textarea, label='Remarks', required=False, help_text="Enter description"
	)

	def clean(self):
		data = self.cleaned_data
		data['by'] = get_current_user()
		return data


class FrontOfficeForm(forms.Form):
	verified = forms.BooleanField(
		required=False, help_text="Check If Verified Uncheck To Send Back Office For Recheck"
	)
	description = forms.CharField(
		widget=forms.Textarea, label='Remarks', required=False, help_text="Enter description"
	)

	def clean(self):
		data = self.cleaned_data
		data['by'] = get_current_user()
		return data


class FrontOfficeSVForm(FrontOfficeForm):
	sv_doc_url = forms.URLField(required=False, help_text="Upload SV Document")

	def clean(self):
		data = super().clean()
		if data.get("verified") and not data.get("sv_doc_url"):
			raise forms.ValidationError("Upload SV Document")




