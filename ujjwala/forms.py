import json

from django import forms
from django.forms import NumberInput

from ujjwala.models import UjjwalaApplicationDocumentsEnum


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


class LegalDocumentsUpload(forms.Form):
	# legal_documents_uploaded = forms.ChoiceField(
	# 	label="Legal Documents Uploaded ?",
	# 	required=True,
	# 	help_text="",
	# 	choices=[
	# 		('', '-- Select If Legal Documents Uploaded --'),
	# 		('VERIFIED', 'Verified'),
	# 		('NOT VERIFIED', 'Not Verified')
	# 	]
	# )

	def clean(self):
		data = self.cleaned_data
		return data


class ConnectionStatusUpdate(forms.Form):
	connection_approved = forms.ChoiceField(
		label="Connection Approved ?",
		required=True,
		help_text="",
		choices=[
			('', '-- Select If Connection Approved --'),
			('APPROVED', 'Approved'),
			('REJECTED', 'Rejected')
		]
	)

	def clean(self):
		data = self.cleaned_data
		return data


class LegalDocumentsCollected(forms.Form):
	legal_documents_verified = forms.ChoiceField(
		label="Legal Documents Collected ?",
		required=True,
		help_text="",
		choices=[
			('', '-- Select If Legal Documents Collected --'),
			('COLLECTED', 'Collected'),
			('NOT COLLECTED', 'Not Collected')
		]
	)

	def clean(self):
		data = self.cleaned_data
		return data


class ConnectionRelease(forms.Form):
	sv = forms.CharField(
		widget=forms.TextInput, max_length=15, required=True, help_text="Enter SV Document No. "
	)
	sv_doc_url = forms.URLField(widget=forms.HiddenInput)

	def clean(self):
		data = self.cleaned_data
		return data


class PostInstallationUpload(forms.Form):

	def clean(self):
		data = self.cleaned_data
		return data


class PreInspectionReviewForm(forms.Form):
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
			data['documents_required_for_reupload'] = json.dumps([UjjwalaApplicationDocumentsEnum.KITCHEN_PHOTO])
		else:
			data['documents_required_for_reupload'] = '[]'
		return data
