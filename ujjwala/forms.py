import json
import logging

from django import forms
from django.contrib.auth.decorators import login_required
from django.forms import NumberInput
from django.http import HttpResponseRedirect, HttpResponseBadRequest
from django.shortcuts import render
from django.utils.decorators import method_decorator

from ujjwala.enums import UjjwalaV2ApplicationStatus
from ujjwala.models import UjjwalaApplicationDocumentsEnum
from formtools.wizard.views import SessionWizardView


logger = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler("/tmp/debug.log"),
    ]
)

class CustomerKitchenPreInspectionForm(forms.Form):
	# widget=forms.HiddenInput,
	application_id = forms.CharField( max_length=8)
	kitchen_photo = forms.CharField(
		widget=forms.TextInput, max_length=256, label='Kitchen Photo', required=True
	)
	customer_in_kitchen = forms.CharField(
		widget=forms.TextInput, max_length=256, label='Customer In Kitchen', required=True
	)

	def clean(self):
		data = self.cleaned_data
		return data


class WitnessPreInspectionForm(forms.Form):
	witness_name = forms.CharField(
		widget=forms.TextInput, max_length=256, label='Witness Name', required=True
	)
	witness_mobile_number = forms.CharField(
		widget=forms.TextInput, max_length=10, label='Witness Mobile', required=True
	)
	witness_photo = forms.CharField(
		widget=forms.TextInput, max_length=256, label='Witness Photo', required=True
	)
	witness_signature_photo = forms.CharField(
		widget=forms.TextInput, max_length=256, label='Witness Signature', required=True
	)

	def clean(self):
		data = self.cleaned_data
		return data


class PreviewPreInspectionForm(forms.Form):
	latitude = forms.CharField(widget=forms.TextInput, max_length=16, label='Latitude', required=True)
	longitude = forms.CharField(widget=forms.TextInput, max_length=16, label='Longitude', required=True)
	accuracy = forms.CharField(widget=forms.TextInput, max_length=24, label='Accuracy', required=True)
	main_gate = forms.CharField(
		widget=forms.TextInput, max_length=256, label='Main Gate Photo', required=True
	)
	otp = forms.CharField(
		widget=forms.TextInput, max_length=6, label='Otp', required=False
	)
	mechanic_photo = forms.CharField(
		widget=forms.TextInput, max_length=256, label='Mechanic Photo', required=True
	)

	def clean(self):
		data = self.cleaned_data
		return data


@method_decorator(login_required, 'dispatch')
class PreInspectionWizardForm(SessionWizardView):
	template_name = "ujjwala/pre-Inspection-form/index.html"
	form_list = [
		('customer_kitchen_form', CustomerKitchenPreInspectionForm),
		('witness_form', WitnessPreInspectionForm),
		('preview_pre_inspection_form', PreviewPreInspectionForm),
	]

	def dispatch(self, request, *args, **kwargs):
		from ujjwala.models import UjjwalaV2Application

		application_id = kwargs.get('pk')
		contact_mobile = request.GET.get('contact_mobile')

		obj = UjjwalaV2Application.objects.filter(id=application_id)

		if obj:
			obj = obj.filter(contact_mobile=contact_mobile).first()
			if obj:
				if obj.status in (
						UjjwalaV2ApplicationStatus.PRE_INSPECTION_SUBMITTED,
						UjjwalaV2ApplicationStatus.PRE_INSPECTION_ACCEPTED
				):
					return render(
						request,
						template_name="ujjwala/pre_inspection_search.html",
						context={"msg": "Pre-Inspection already done."}
					)
				elif obj.status not in (
						UjjwalaV2ApplicationStatus.NIC_CLEARED
				):
					return render(
						request,
						template_name="ujjwala/pre_inspection_search.html",
						context={"msg": "Application is not ready for Pre-Inspection stage."}
					)
				return super(PreInspectionWizardForm, self).dispatch(request, *args, **kwargs)
			else:
				return render(
					request,
					template_name="ujjwala/pre_inspection_search.html",
					context={"msg": "Contact Mobile: {} Not Found.".format(contact_mobile)}
				)
		else:
			return render(
				request,
				template_name="ujjwala/pre_inspection_search.html",
				context={"msg": "Application Id: {} Not Found".format(application_id)}
			)

	def render(self, form=None, **kwargs):
		if form and not form.is_valid():
			logger.warning(form.errors.as_text())
		return super().render(form=form, **kwargs)


	def get_form_initial(self, step):
		init_data = self.initial_dict.get(step, {})
		if step == 'customer_kitchen_form':
			init_data.update({'application_id': self.kwargs.get('pk')})
		return init_data

	def get_context_data(self, *args, **kwargs):
		con = super().get_context_data(*args, **kwargs)

		from ujjwala.models import UjjwalaV2Application
		application_obj = UjjwalaV2Application.objects.filter(id=self.kwargs.get('pk')).first()
		con.update({
			"obj": application_obj
		})
		return con

	def done(self, form_list, **kwargs):
		from ujjwala.models import UjjwalaV2Application

		data = self.get_all_cleaned_data()

		obj: UjjwalaV2Application = UjjwalaV2Application.objects.filter(id=data.get('application_id')).first()
		obj.transition_pre_inspection_submit(**data)
		obj.save()
		return HttpResponseRedirect('/ujjwala/frontend/')


class PreInspectionReviewForm(forms.Form):
	verified = forms.BooleanField(
		required=False,
		help_text="Pre Inspection Is Valid As Per Standards"
	)

	remarks = forms.CharField(
		widget=forms.Textarea,
		label='Remarks (Will be displayed to customer)',
		required=True
	)

	def clean(self):
		data = self.cleaned_data
		if not data.get('verified'):
			data['documents_required_for_reupload'] = json.dumps(
				[
					UjjwalaApplicationDocumentsEnum.KITCHEN_PHOTO
				]
			)
		else:
			data['documents_required_for_reupload'] = '[]'
		return data


class EkycAcceptedOrRejected(forms.Form):
	# ekyc_accepted = forms.ChoiceField(
	# 	label="Ekyc Status Update ?",
	# 	required=True,
	# 	help_text="",
	# 	choices=[
	# 		('', '-- Select If Ekyc Accepted Or Rejected --'),
	# 		('ACCEPTED', 'Accepted'),
	# 		('REJECTED', 'Rejected')
	# 	]
	# )

	description = forms.CharField(
		widget=forms.Textarea, label='Remarks', required=True
	)

	def clean(self):
		data = self.cleaned_data
		return data


class EkycAccepted(forms.Form):
	description = forms.CharField(
		widget=forms.Textarea, label='Remarks', required=True
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
	consumer_id = forms.CharField(
		widget=forms.TextInput, max_length=16, label='Consumer Id', required=True
	)
	description = forms.CharField(
		widget=forms.Textarea, label='Remarks', required=True
	)

	def clean(self):
		data = self.cleaned_data
		return data


class ConnectionStatusApproved(forms.Form):
	description = forms.CharField(
		widget=forms.Textarea, label='Remarks', required=True
	)

	def clean(self):
		data = self.cleaned_data
		return data


class ApplicationRejected(forms.Form):
	rejected_reason = forms.ChoiceField(
		label="Rejected Reason",
		required=True,
		help_text="Please select rejected reason",
		choices=[
			('', '-- Select Rejected Reason --'),
			('EKYC', 'Ekyc'),
			('CONNECTION_ALREADY_EXIST', 'Connection Already Exist'),
			('NIC_FAILED', 'NIC Failed'),
		]
	)
	description = forms.CharField(
		widget=forms.Textarea, label='Remarks', required=True
	)

	def clean(self):
		data = self.cleaned_data
		if data:
			data = {'description': '{}: {}'.format(
				data.get('rejected_reason'), data.get('description', '')
			)}
		return data


class ConnectionStatusRejected(forms.Form):
	connection_rejected_reason = forms.ChoiceField(
		label="Connection Rejected Reason ?",
		required=True,
		help_text="",
		choices=[
			('', '-- Select Connection Rejected Reason --'),
			('OMC_DEDUP_FAILED', 'OMC Dedup Failed'),
			('NIC_FAILED', 'NIC Failed'),
			('OTHER', 'Other')
		]
	)

	other_reason = forms.CharField(
		widget=forms.TextInput, max_length=50, label='Other Reason', required=False
	)

	def clean(self):
		data = self.cleaned_data
		if data:
			data = {'description': '{}: {}'.format(
				data.get('connection_rejected_reason'), data.get('other_reason', '')
			)}
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
	description = forms.CharField(
		widget=forms.Textarea, label='Remarks', required=True
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


class UjjwalaDocumentsReuploadForm(forms.Form):
	documents_required_for_reupload = forms.MultipleChoiceField(
		widget=forms.SelectMultiple,
		choices=UjjwalaApplicationDocumentsEnum.get_skipped_additional_choices(),
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
