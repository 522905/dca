import json

from django import forms
from django.forms import NumberInput


class EkycInitiated(forms.Form):
	reupload_documents = forms.ChoiceField(
		label="Reupload Documents ?",
		required=True,
		help_text="",
		choices=[
			('', '-- Select If Documents To Be Re-uploaded --'),
			('YES', 'Yes'),
			('NO', 'No')
		]
	)
	description = forms.CharField(widget=forms.Textarea, label='Remarks', required=False)

	def clean(self):
		data = self.cleaned_data
		return data


class EkycAcceptedOrRejected(forms.Form):
	ekyc_accepted = forms.ChoiceField(
		label="Ekyc Status Update ?",
		required=True,
		help_text="",
		choices=[
			('', '-- Select If Ekyc Accepted Or Rejected --'),
			('ACCEPTED', 'Accepted'),
			('REJECTED', 'Rejected')
		]
	)

	def clean(self):
		data = self.cleaned_data
		return data


class NewConnectionAcceptedOrRejected(forms.Form):
	new_connection_accepted = forms.ChoiceField(
		label="New Connection Accepted Or Rejected ?",
		required=True,
		help_text="",
		choices=[
			('', '-- Select If New Connection Accepted Or Rejected --'),
			('ACCEPTED', 'Accepted'),
			('REJECTED', 'Rejected')
		]
	)

	def clean(self):
		data = self.cleaned_data
		return data


class LegalDocumentsCollected(forms.Form):
	legal_documents_verified = forms.ChoiceField(
		label="Legal Documents Verified ?",
		required=True,
		help_text="",
		choices=[
			('', '-- Select If Legal Documents Verified --'),
			('VERIFIED', 'Verified'),
			('NOT VERIFIED', 'Not Verified')
		]
	)

	def clean(self):
		data = self.cleaned_data
		return data


class SvReleased(forms.Form):
	sv_released = forms.ChoiceField(
		label="SV Released Or Not ?",
		required=True,
		help_text="",
		choices=[
			('', '-- Select If SV Released Or Not --'),
			('Y', 'Yes'),
			('N', 'No')
		]
	)
	sv = forms.CharField(
		widget=forms.Textarea, required=False, help_text="Enter SV Document No. "
	)

	def clean(self):
		data = self.cleaned_data
		return data