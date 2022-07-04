import datetime
import json
import logging
import string
from datetime import timedelta
from time import timezone

import track
from django import forms
from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.forms import NumberInput
from django.http import HttpResponseRedirect, HttpResponseBadRequest
from django.shortcuts import render
from django.utils.decorators import method_decorator
from django_currentuser.middleware import get_current_user

from otp.models import Otp
from ujjwala.enums import UjjwalaV2ApplicationStatus, PreInspectionStatusEnum, ConnectionDisbursementStatusEnum, \
	RejectionTypeEnum
from ujjwala.models import UjjwalaApplicationDocumentsEnum
from formtools.wizard.views import SessionWizardView

from ujjwala.ujjwala_functions import __get_ref_no__, id_generator, valid_file_uploaded
from django.core import validators

logger = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler("/tmp/debug.log"),
    ]
)


class NicUpdateAddressForm(forms.Form):
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
		widget=forms.TextInput, label='Ward No.', required=True
	)
	post_office = forms.CharField(
		widget=forms.TextInput, label='Post Office', required=True
	)
	pincode = forms.CharField(
		widget=forms.TextInput, label='Pin Code', required=True
	)

	def __init__(self, *args, **kwargs):
		super().__init__(*args, **kwargs)

	def clean(self):
		data = self.cleaned_data
		data['address_json'] = {
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



##################################################
##################################################
# Will be renamed to Address Change Form
##################################################
##################################################


class ChangeAddressForm(forms.Form):
	update_address = forms.BooleanField(
		widget=forms.CheckboxInput, label='Click To Change Address', required=False
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
		widget=forms.TextInput, label='House No.', required=True
	)
	post_office = forms.CharField(
		widget=forms.TextInput, label='Post Office', required=True
	)
	pincode = forms.CharField(
		widget=forms.TextInput, label='Pin Code', required=True
	)

	def __init__(self, pre_inspection=None, *args, **kwargs):
		super().__init__(*args, **kwargs)
		self.pre_inspection = pre_inspection

	def save(self):
		data = self.cleaned_data
		
		# if not self.update_address:
		# 	return data

		obj = self.pre_inspection

		old_address_json = obj.parent.address_json

		obj.parent.address_json = {
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

		obj.parent.save()
		obj.pre_inspection_change_address(by=get_current_user(), description=old_address_json)
		obj.save()


class KitchenPreInspectionForm(forms.Form):
	kitchen_photo = forms.CharField(
		widget=forms.TextInput, label='Kitchen Photo', required=True
	)
	witness_name = forms.CharField(
		widget=forms.TextInput, label='Witness Name', required=True
	)
	witness_mobile_number = forms.CharField(
		widget=forms.TextInput, max_length=10, label='Witness Mobile', required=True
	)
	witness_signature_photo = forms.CharField(
		widget=forms.TextInput, label='Witness Signature', required=True
	)

	def __init__(self, pre_inspection=None, *args, **kwargs):
		super().__init__(*args, **kwargs)
		self.pre_inspection = pre_inspection

	def save(self):
		data = self.cleaned_data
		obj = self.pre_inspection

		obj.documents.create(
			type=UjjwalaApplicationDocumentsEnum.KITCHEN_PHOTO,
            link=data['kitchen_photo']
		)
		obj.documents.create(
			type=UjjwalaApplicationDocumentsEnum.WITNESS_SIGNATURE,
			link=data['witness_signature_photo']
		)

		obj.witness_name = data['witness_name']
		obj.witness_mobile_number = data['witness_mobile_number']
		obj.pre_inspection_kitchen_photo_uploaded(
			by=get_current_user(),
			description="Witness Name: {}, Mobile Number: {}".format(obj.witness_name, obj.witness_mobile_number)
		)
		obj.save()


class AudioOnSafetyForm(forms.Form):
	audio_file = forms.CharField(
		widget=forms.TextInput, label='Audio File', required=False
	)

	def __init__(self, pre_inspection=None, *args, **kwargs):
		super().__init__(*args, **kwargs)
		self.pre_inspection = pre_inspection

	def save(self):
		data = self.cleaned_data
		obj = self.pre_inspection

		doc = obj.documents.create(type=UjjwalaApplicationDocumentsEnum.SAFETY_AUDIO,
		                     link=data['audio_file'])
		obj.pre_inspection_safety_audio_uploaded(
			by=get_current_user(),
			description="Safety Audio: {}".format(doc.link)

		)
		obj.save()


class PreviewPreInspectionForm(forms.Form):
	latitude = forms.CharField(widget=forms.TextInput(attrs={'readonly': 1}), max_length=32, label='Latitude', required=True)
	longitude = forms.CharField(widget=forms.TextInput(attrs={'readonly': 1}), max_length=32, label='Longitude', required=True)
	accuracy = forms.CharField(widget=forms.TextInput(attrs={'readonly': 1}), max_length=24, label='Accuracy', required=True)
	main_gate = forms.CharField(
		widget=forms.HiddenInput, label='Main Gate Photo', required=True
	)

	def __init__(self, pre_inspection=None, *args, **kwargs):
		super().__init__(*args, **kwargs)
		self.pre_inspection = pre_inspection

	def clean(self):
		data = self.cleaned_data
		return data

	def save(self):
		data = self.cleaned_data
		obj = self.pre_inspection

		obj.documents.create(
			type=UjjwalaApplicationDocumentsEnum.MAIN_GATE,
            link=data['main_gate']
		)

		obj.latitude = data['latitude']
		obj.longitude = data['longitude']
		obj.accuracy = data['accuracy']

		obj.transition_pre_inspection_submit(
			by=get_current_user(),
			description="Latitude: {}, Longituder: {}, Accuracy: {}".format(
				data['latitude'], data['longitude'], data['accuracy'])
		)
		obj.save()

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

		# obj: UjjwalaV2Application = UjjwalaV2Application.objects.filter(id=data.get('application_id')).first()
		# obj.transition_pre_inspection_submit(**data)
		# obj.save()
		return HttpResponseRedirect('/ujjwala/frontend/')


class PreInspectionInitialForm(forms.Form):
	form_type = forms.CharField(widget=forms.HiddenInput, initial='initial_form')
	application_id = forms.IntegerField()

	def clean_application_id(self):
		from ujjwala.models import UjjwalaV2Application
		value = self.cleaned_data.get('application_id')

		application = UjjwalaV2Application.objects.filter(
			pk=value
		).first()
		if not application:
			raise forms.ValidationError("Invalid Application Id")
		elif not application.status == UjjwalaV2ApplicationStatus.NIC_CLEARED:
			raise forms.ValidationError("Application Status: {}".format(application.status))
		return value


class PreInspectionGenerateOtpForm(forms.Form):
	form_type = forms.CharField(widget=forms.HiddenInput, initial='generate_otp_form')
	application_id = forms.IntegerField(widget=forms.HiddenInput)
	mobile = forms.ChoiceField(
		widget=forms.RadioSelect,
	    label='Select Mobile Number for Sending OTP(ओटीपी भेजने के लिए मोबाइल नंबर चुनें)'
	)

	def __init__(self, mobile_nos=None, *args, **kwargs):
		super().__init__(*args, **kwargs)
		if mobile_nos:
			self.fields['mobile'].choices = [(i, i) for i in mobile_nos]

	def send_otp(self):

		ref_no = None

		while True:
			ref_no = __get_ref_no__()
			try:
				Otp.objects.get(reference_number=ref_no)
			except Otp.DoesNotExist:
				break

		otp = id_generator(4, chars=string.digits)
		valid_till = datetime.datetime.now() + timedelta(minutes=15)
		closed = False

		otp_obj = Otp.objects.create(
			reference_number=ref_no,
			mobile=self.data.get('mobile'),
			otp=otp,
			valid_till=valid_till,
			closed=closed,
			extra={
				"application_id": self.data.get('application_id')
			}
		)

		body_text = {
			"countryCode": "+91",
			"phoneNumber": otp_obj.mobile,
			"type": "Template",
			"traits": {
				"name": otp_obj.mobile,
			},
			# "callbackData": "some_callback_data",
			"template": {
				# "name": "ujjwala_application_submitted_",
				"name": "ujjwala_pre_inspection_otp",
				"languageCode": "hi",
				"headerValues": [
					# "Alert",  #
				],
				"bodyValues": [
					otp
				]
			}
		}

		data = track.client.post(
			api_key=settings.INTERAKT_API_KEY,
		 	path="/v1/public/message/",
		 	body=body_text
		).json()
		return otp_obj


class PreInspectionValidateOtpForm(forms.Form):
	form_type = forms.CharField(widget=forms.HiddenInput, initial='validate_otp_form')
	application_id = forms.IntegerField(widget=forms.HiddenInput)
	reference_number = forms.CharField()
	otp = forms.CharField(max_length=4)

	def clean(self):
		data = super().clean()
		otp_obj = Otp.objects.filter(reference_number=data['reference_number']).first()
		if otp_obj:
			status, message = otp_obj.verify_and_close(data.get('otp'))
			if not status:
				raise forms.ValidationError(message)
			return data
		else:
			raise forms.ValidationError("Invalid Reference Code")


######################################
# Allocated Pre Inspection OTP Forms #
######################################
class PreInspectionAllocatedGenerateOtpForm(forms.Form):
	form_type = forms.CharField(widget=forms.HiddenInput, initial='generate_otp_form')
	pre_inspection_id = forms.IntegerField(widget=forms.HiddenInput)
	application_id = forms.IntegerField(widget=forms.HiddenInput)
	mobile = forms.ChoiceField(
		widget=forms.RadioSelect,
		label='Select Mobile Number for Sending OTP(ओटीपी भेजने के लिए मोबाइल नंबर चुनें)'
	)

	def __init__(self, mobile_nos=None, *args, **kwargs):
		super().__init__(*args, **kwargs)
		if mobile_nos:
			self.fields['mobile'].choices = [(i, i) for i in mobile_nos]

	def send_otp(self):

		ref_no = None

		while True:
			ref_no = __get_ref_no__()
			try:
				Otp.objects.get(reference_number=ref_no)
			except Otp.DoesNotExist:
				break

		otp = id_generator(4, chars=string.digits)
		valid_till = datetime.datetime.now() + timedelta(minutes=15)
		closed = False

		otp_obj = Otp.objects.create(
			reference_number=ref_no,
			mobile=self.data.get('mobile'),
			otp=otp,
			valid_till=valid_till,
			closed=closed,
			extra={
				"pre_inspection_id": self.data.get('pre_inspection_id'),
				"ujjwala_application_id": self.data.get('application_id')
			}
		)

		body_text = {
			"countryCode": "+91",
			"phoneNumber": otp_obj.mobile,
			"type": "Template",
			"traits": {
				"name": otp_obj.mobile,
			},
			# "callbackData": "some_callback_data",
			"template": {
				# "name": "ujjwala_application_submitted_",
				"name": "ujjwala_pre_inspection_otp",
				"languageCode": "hi",
				"headerValues": [
					# "Alert",  #
				],
				"bodyValues": [
					otp
				]
			}
		}

		data = track.client.post(
		 	api_key=settings.INTERAKT_API_KEY,
		 	path="/v1/public/message/",
		 	body=body_text
		).json()
		return otp_obj


class PreInspectionAllocatedValidateOtpForm(forms.Form):
	form_type = forms.CharField(widget=forms.HiddenInput, initial='validate_otp_form')
	application_id = forms.IntegerField(widget=forms.HiddenInput)
	reference_number = forms.CharField()
	otp = forms.CharField(max_length=4)

	def clean(self):
		data = super().clean()
		otp_obj = Otp.objects.filter(reference_number=data['reference_number']).first()
		if otp_obj:
			status, message = otp_obj.verify_and_close(data.get('otp'))
			if not status:
				raise forms.ValidationError(message)
			return data
		else:
			raise forms.ValidationError("Invalid Reference Code")


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
			data['documents_required_for_reupload'] = json.dumps([
				UjjwalaApplicationDocumentsEnum.KITCHEN_PHOTO
			])
		else:
			data['documents_required_for_reupload'] = '[]'
		return data


class EkycAcceptedOrRejected(forms.Form):

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
	description = forms.CharField(
		widget=forms.TextInput, label='Description', required=True,
		help_text="Please mention issue faced while uploading the documents"
	)

	def clean(self):
		data = self.cleaned_data
		return data


class UjjwalaLegalDocumentsUpload(forms.Form):
	pre_inspection = forms.CharField(
		widget=forms.TextInput, label='Pre Inspection', required=True
	)
	family_occupancy = forms.CharField(
		widget=forms.TextInput, label='Family Occupancy', required=True
	)
	annexure_14_points = forms.CharField(
		widget=forms.TextInput, label='Annexure 14 Points', required=True
	)

	def clean_pre_inspection(self):
		value = self.cleaned_data.get('pre_inspection')

		if not valid_file_uploaded(value):
			raise forms.ValidationError("Invalid Pre inspection File Upload")
		return value

	def clean_family_occupancy(self):
		value = self.cleaned_data.get('family_occupancy')

		if not valid_file_uploaded(value):
			raise forms.ValidationError("Invalid family_occupancy File Upload")
		return value

	def clean_annexure_14_points(self):
		value = self.cleaned_data.get('annexure_14_points')

		if not valid_file_uploaded(value):
			raise forms.ValidationError("Invalid annexure_14_points File Upload")
		return value


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


class LegalDocumentsReview(forms.Form):
	review_status = forms.ChoiceField(
		label="Review Status",
		required=True,
		help_text="Please Select Review Status",
		choices=[
			('', '-- Select Review Status --'),
			('ACCEPTED', 'Accepted'),
			('REUPLOAD', 'Reupload'),
		]
	)

	description = forms.CharField(
		widget=forms.Textarea, label='Remarks', required=True
	)

	def clean(self):
		data = self.cleaned_data
		if data:
			data = {'description': '{}: {}'.format(
				data.get('review_status'), data.get('description', '')
			)}
		return data


class ApplicationRejected(forms.Form):
	rejected_reason = forms.ChoiceField(
		label="Rejected Reason",
		required=True,
		help_text="Please select rejected reason",
		choices=RejectionTypeEnum.choices
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


class PreInspectionReviewAdminForm(forms.Form):
	review_status = forms.ChoiceField(
		label="Select Review Status ?",
		required=True,
		help_text="",
		choices=[
			('', '-- Select Review Status --'),
			('ACCEPTED', 'Accepted'),
			('REJECTED', 'Rejected')
		]
	)
	rejected_reason = forms.CharField(
		widget=forms.TextInput, max_length=255, label='Rejected Reason', required=False
	)
	description = forms.CharField(
		widget=forms.Textarea, label='Remarks', required=False
	)

	def clean(self):
		data = self.cleaned_data
		if data:
			if data.get('review_status', '') == 'REJECTED' and not data['rejected_reason']:
				raise forms.ValidationError("Please enter a reason for rejection.")
			data.update({'description': '{} - {}: {}'.format(
					data.get('review_status'), data.get('rejected_reason'), data.get('description', '')
				)
			})
		return data


class LegalDocumentsReviewAdminForm(forms.Form):
	review_status = forms.ChoiceField(
		label="Select Review Status ?",
		required=True,
		help_text="",
		choices=[
			('', '-- Select Review Status --'),
			('ACCEPTED', 'Accepted'),
			('REJECTED', 'Rejected')
		]
	)
	rejected_reason = forms.CharField(
		widget=forms.TextInput, max_length=255, label='Rejected Reason', required=False
	)
	description = forms.CharField(
		widget=forms.Textarea, label='Remarks', required=False
	)

	def clean(self):
		data = self.cleaned_data
		if data:
			if data.get('review_status', '') == 'REJECTED' and not data['rejected_reason']:
				raise forms.ValidationError("Please enter a reason for rejection.")
			data.update({'description': '{} - {}: {}'.format(
					data.get('review_status'), data.get('rejected_reason'), data.get('description', '')
				)
			})
		return data


class ConnectionDisbursementLabelPrintForm(forms.Form):
	application_id = forms.IntegerField(widget=forms.HiddenInput)
	reference_number = forms.CharField()
	otp = forms.CharField(max_length=4)

	def clean(self):
		data = self.cleaned_data
		return data


class ConnectionDisbursementMaterialDeliveredForm(forms.Form):
	application_id = forms.IntegerField(widget=forms.HiddenInput)
	reference_number = forms.CharField()
	material_delivered_photo = forms.CharField(
		widget=forms.TextInput, label='Pre Inspection', required=True
	)
	otp = forms.CharField(max_length=4)

	def clean(self):
		data = self.cleaned_data
		return data


class ConnectionDisbursementSvLabelPrintForm(forms.Form):
	def __init__(self, connection_disbursement=None, *args, **kwargs):
		super().__init__(*args, **kwargs)
		self.connection_disbursement = connection_disbursement

	def save(self):
		data = self.cleaned_data
		obj = self.connection_disbursement
		obj.transition_sv_label_printed(
			by=get_current_user()
		)
		obj.save()


class ConnectionDisbursementSocialMediaUpdatesForm(forms.Form):
	social_media_photo = forms.URLField(
		widget=forms.HiddenInput, required=True
	)

	def __init__(self, connection_disbursement=None, *args, **kwargs):
		super().__init__(*args, **kwargs)
		self.connection_disbursement = connection_disbursement

	def save(self):
		data = self.cleaned_data
		obj = self.connection_disbursement

		obj.documents.create(
			type=UjjwalaApplicationDocumentsEnum.SOCIAL_MEDIA_PHOTO,
			link=data['social_media_photo']
		)

		obj.transition_social_media_updates_done(
			by=get_current_user()
		)
		obj.save()


class ConnectionDisbursementMaterialDeliveryForm(forms.Form):
	disbursement_photo = forms.CharField(
		widget=forms.HiddenInput, label='Connection Disbursement', required=True
	)

	def __init__(self, connection_disbursement=None, *args, **kwargs):
		super().__init__(*args, **kwargs)
		self.connection_disbursement = connection_disbursement

	def save(self):
		data = self.cleaned_data
		obj = self.connection_disbursement

		obj.documents.create(
			type=UjjwalaApplicationDocumentsEnum.DISBURSEMENT_PHOTO,
			link=data['disbursement_photo']
		)

		obj.transition_material_delivered(
			by=get_current_user()
		)
		obj.save()


class UjjwalaApplicationOtpInitialForm(forms.Form):
	form_type = forms.CharField(widget=forms.HiddenInput, initial='initial_form')
	otp_generated_for = forms.CharField(widget=forms.HiddenInput)
	application_id = forms.IntegerField()
	whatsapp_template_name = forms.CharField(widget=forms.HiddenInput)

	def clean_application_id(self):
		from ujjwala.models import UjjwalaV2Application
		value = self.cleaned_data.get('application_id')

		application = UjjwalaV2Application.objects.filter(
			pk=value
		).first()

		if not application:
			raise forms.ValidationError("Invalid Application Id")
		elif not application.status == ConnectionDisbursementStatusEnum.LEGAL_DOCUMENTS_ACCEPTED:
			raise forms.ValidationError("Application Status: {}".format(application.status))
		return value


class UjjwalaApplicationGenerateOtpForm(forms.Form):
	form_type = forms.CharField(widget=forms.HiddenInput, initial='generate_otp_form')
	otp_generated_for = forms.CharField(widget=forms.HiddenInput)
	whatsapp_template_name = forms.CharField(widget=forms.HiddenInput)
	application_id = forms.IntegerField(widget=forms.HiddenInput)

	mobile = forms.ChoiceField(
		widget=forms.RadioSelect,
	    label='Select Mobile Number for Sending OTP(ओटीपी भेजने के लिए मोबाइल नंबर चुनें)'
	)

	def __init__(self, mobile_nos=None, *args, **kwargs):
		super().__init__(*args, **kwargs)
		if mobile_nos:
			self.fields['mobile'].choices = [(i, i) for i in mobile_nos]


	def send_otp(self):
		ref_no = None
		while True:
			ref_no = __get_ref_no__()
			try:
				Otp.objects.get(reference_number=ref_no)
			except Otp.DoesNotExist:
				break
		otp = id_generator(4, chars=string.digits)
		valid_till = datetime.datetime.now() + timedelta(minutes=15)
		closed = False

		otp_obj = Otp.objects.create(
			reference_number=ref_no,
			mobile=self.data.get('mobile'),
			otp=otp,
			valid_till=valid_till,
			closed=closed,
			extra={
				"application_id": self.data.get('application_id')
			}
		)

		body_text = {
			"countryCode": "+91",
			"phoneNumber": otp_obj.mobile,
			"type": "Template",
			"traits": {
				"name": otp_obj.mobile,
			},
			# "callbackData": "some_callback_data",
			"template": {
				# "name": "ujjwala_application_submitted_",
				"name": self.data.get("whatsapp_template_name"),
				"languageCode": "hi",
				"headerValues": [
					# "Alert",  #
				],
				"bodyValues": [
					otp
				]
			}
		}

		data = track.client.post(
			api_key=settings.INTERAKT_API_KEY,
		 	path="/v1/public/message/",
		 	body=body_text
		).json()
		return otp_obj


class UjjwalaApplicationValidateOtpForm(forms.Form):
	form_type = forms.CharField(widget=forms.HiddenInput, initial='validate_otp_form')
	application_id = forms.IntegerField(widget=forms.HiddenInput)
	reference_number = forms.CharField()
	otp = forms.CharField(max_length=4)

	def clean(self):
		data = super().clean()
		otp_obj = Otp.objects.filter(reference_number=data['reference_number']).first()
		if otp_obj:
			status, message = otp_obj.verify_and_close(data.get('otp'))
			if not status:
				raise forms.ValidationError(message)
			return data
		else:
			raise forms.ValidationError("Invalid Reference Code")


class InstallationKitchenUploadForm(forms.Form):
	
	kitchen_photo = forms.CharField(
		widget=forms.HiddenInput, label='kitchen Photo', required=True
	)

	stove_photo = forms.CharField(
		widget=forms.HiddenInput, label='Stove Photo', required=True
	)

	def __init__(self, installation=None, *args, **kwargs):
		super().__init__(*args, **kwargs)
		self.installation = installation
	
	def clean(self):
		data = self.cleaned_data
		return data

	def save(self):
		data = self.cleaned_data
		obj = self.installation

		obj.documents.create(
			type=UjjwalaApplicationDocumentsEnum.INSTALLATION_KITCHEN_PHOTO,
			link=data['kitchen_photo']
		)

		obj.documents.create(
			type=UjjwalaApplicationDocumentsEnum.INSTALLATION_STOVE_WITH_STICKER,
			link=data['stove_photo']
		)

		obj.transition_installation_kitchen_upload(
			by=get_current_user()
		)
		obj.save()


class InstallationMainGateUploadForm(forms.Form):
	latitude = forms.CharField(widget=forms.TextInput(attrs={'readonly': 1}), max_length=32, label='Latitude', required=True)
	longitude = forms.CharField(widget=forms.TextInput(attrs={'readonly': 1}), max_length=32, label='Longitude', required=True)
	accuracy = forms.CharField(widget=forms.TextInput(attrs={'readonly': 1}), max_length=24, label='Accuracy', required=True)

	def __init__(self, installation=None, *args, **kwargs):
		super().__init__(*args, **kwargs)
		self.installation = installation
	
	def clean(self):
		data = self.cleaned_data
		return data

	def save(self):
		data = self.cleaned_data
		self.installation.location_data = {
			'latitude': data['latitude'],
			'longitude': data['longitude'],
			'accuracy': data['accuracy']
		                                   }
		self.installation.transition_main_gate(
			by=get_current_user()
		)
		self.installation.save()


class ConnectionDisbursementInvitationForm(forms.Form):
	invited_for = forms.DateTimeField(widget=forms.HiddenInput, label='Invited For', required=False)
	sv_link = forms.URLField(widget=forms.HiddenInput, label='SV Document', required=True)
	booking_id = forms.CharField(widget=forms.TextInput(), label='Booking Id', required=True, validators=[validators.RegexValidator(regex='^2-[0-9]{12}$')])
	sv_uploaded_on = forms.DateTimeField(widget=forms.HiddenInput, required=False)

	def clean(self):
		data = self.cleaned_data
		return data

	def save(self, obj):
		data = self.cleaned_data
		obj.invitation.create(
			sv_link=data['sv_link'],
			booking_id=data['booking_id'],
			sv_uploaded_on=datetime.datetime.now()
		)


class ConnectionDisbursementSearchForm(forms.Form):
	# from ujjwala.models import ConnectionDisbursement
	application_id = forms.IntegerField()
