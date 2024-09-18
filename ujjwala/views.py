import base64
import datetime
import json
import textwrap
from functools import partial

import django_filters
import django_rq
import requests
from django import forms
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.contrib.contenttypes.models import ContentType
from django.core.paginator import Paginator, PageNotAnInteger, EmptyPage
from django.core.signing import Signer
from django.db import transaction
from django.db.models import Q
from django.forms import inlineformset_factory
from django.http import HttpResponse, Http404, HttpResponseRedirect, JsonResponse
from django.shortcuts import render, redirect
from django.urls import reverse
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.clickjacking import xframe_options_exempt
from django.views.decorators.csrf import csrf_exempt
from django.views.generic import DetailView, FormView, ListView, TemplateView, UpdateView
from django_currentuser.middleware import get_current_user
from django_filters import FilterSet
from django_filters.views import FilterView
from django_fsm_log.models import StateLog
from otp.models import Otp
from service_request.enums import ServiceRequestTypeEnum, ServiceRequestTypeStatusEnum
from service_request.models import ServiceRequest
from ujjwala.camunda_functions import start_process_in_camunda, \
	evaluate_and_start_ujjwala_sv_process_in_camunda, start_process_in_camunda_v2, is_process_exist_in_camunda
from ujjwala.enums import UjjwalaV2ApplicationStatus, PreInspectionStatusEnum, ConnectionDisbursementStatusEnum, \
	PreInspectionTypeEnum, DisbursementDriveStatusEnum, UjjwalaApplicationDocumentsEnum, \
	UjjwalaV2ApplicationAvailabilityChannel, ConnectionDisbursementInvitationEnum, FilledByFilterEnum, \
	UjjwalaSearchLogEnum, BankDetailsUpdateRequestEnum, ChangeCylinderTypeRequestStatusEnum
from ujjwala.forms import UjjwalaDocumentsReuploadForm, PreInspectionInitialForm, \
	UpdateBankDetailsForm, CancelInvitationForm, NewRelationCreated, ChangePhoneNumberForm, UpdateAddressForm, \
	PreInspectionGenerateOtpForm, PreInspectionValidateOtpForm, \
	KitchenPreInspectionForm, AudioOnSafetyForm, PreviewPreInspectionForm, PreInspectionAllocatedGenerateOtpForm, \
	PreInspectionAllocatedValidateOtpForm, UjjwalaLegalDocumentsUpload, ChangeAddressForm, \
	ConnectionDisbursementSvLabelPrintForm, InstallationMainGateUploadForm, InstallationKitchenUploadForm, \
	UjjwalaApplicationGenerateOtpForm, UjjwalaApplicationValidateOtpForm, \
	ConnectionDisbursementMaterialDeliveryForm, ConnectionDisbursementInvitationForm, \
	ConnectionDisbursementSocialMediaUpdatesForm, NicUpdateAddressForm, \
	PreInspectionConvertForm, LegalDocumentsReviewAdminForm, SetPrimaryPhoneNumberForm, \
	UpdateBankDetailsForm, NicClearedCustomerRemarksForm, PrintDocumentsForm, \
	InstallationReviewAdminForm, PreInspectionReviewAdminForm, CancelInvitationForm, UpdateAddressForm, \
	NewRelationCreated, ChangePhoneNumberForm, UploadUIDForEKYCForm, UjjwalaApplicationServiceRequestForm, \
	ReviewUpdatedAddressForm, UpdateBankDetailsNewForm, ChangeCylinderTypeForm, \
	ChangeCylinderTypeForm, ChangeCylinderTypeRequestForm, ChangeCylinderTypeRequestOverrideForm, \
	BankDetailsUpdateRequestForm
from ujjwala.global_functions import login_required_if_mech_inspection
from ujjwala.models import UjjwalaV2Application, PreInspection, ConnectionDisbursement, \
	FamilyMembers, DisbursementDrive, UjjwalaSearchLog, ConnectionDisbursementInvitation, BankDetailsUpdateRequest, \
	ChangeCylinderTypeRequest
from ujjwala.sv_functions import create_installation_document
from ujjwala.ujjwala_functions import ujjwala_application_reject_reason_log, is_pre_inspection_applicable, \
	send_ujjwala_application_whatsapp_link_v2, download_audit_documents_for_ids, is_member_of_disbursement_drive, \
	get_current_user_disbursement_drive, send_ujjwala_self_pre_inspection_share_link, is_member_of_reviewer_group, \
	send_ujjwala_share_on_social_media_link, \
	can_resolve_service_request, ujjwala_application_state_logs, is_front_end_staff, \
	get_data_for_new_relation, re_create_legal_docs, download_change_cylinder_type_form, \
	download_ujjwala_physical_legal_docs, upload_form_e_document_and_whatsapp, can_process_change_cylinder_request, \
	can_review_disbursement_form_abc_permission
from utils.global_functions import unsign_data_base64, sign_data_base64, upload_file_to_minio_bucket


### Form to avoid circular import ###
class BackendDriveSelectionForm(forms.Form):
	drive = forms.ModelChoiceField(queryset=DisbursementDrive.objects.filter(
		status=DisbursementDriveStatusEnum.ACTIVE
	))


### END ###


def index(request):
	return redirect('ujjwala:web_form')


def legal_documents(request):
	return render(request, 'ujjwala/legal-document-upload-form.html')


class ChangeCylinderTypeRequestFilter(FilterSet):
	parent_id = django_filters.NumberFilter(field_name='parent_id', label="Search Ujjwala Application:")

	class Meta:
		model = ChangeCylinderTypeRequest
		fields = ['parent_id']

	@property
	def qs(self):
		parent = super().qs

		return parent.order_by('-id')


@method_decorator(login_required, 'dispatch')
class WebFormOldView(View):
	def dispatch(self, request, *args, **kwargs):
		user = get_current_user()
		if user.has_perm('can_fill_old_ujjwala_form', 'ujjwala'):
			return render(request, 'ujjwala/web_form_old.html')
		else:
			return HttpResponse("You do not have permission to fill this form. Contact Admin")


# I Frame Web Form View To Display Form In Website
# With
@method_decorator(xframe_options_exempt, 'dispatch')
@method_decorator(login_required, 'dispatch')
class UjjwalaApplicationIframeWebFormView(TemplateView):
	template_name = "ujjwala/i_web_form.html"

	def dispatch(self, request, *args, **kwargs):
		response = super().dispatch(request, *args, **kwargs)
		response['Content-Security-Policy'] = "frame-ancestors 'self'"
		return response


# Whatsapp Nic Error Update Addres View
class WhatsappNicErrorUpdateAddress(View):
	def get(self, request, *args, **kwargs):
		obj = UjjwalaV2Application.objects.filter(pk=kwargs.get('pk')).first()
		if obj:
			obj.event_whatsapp_nic_error_update_address()
			return HttpResponse("Application Id {}: Message Sent".format(kwargs.get('pk')))
		return HttpResponse("Application Id {} does not exist".format(kwargs.get('pk')))


# Pre Inspection Type Self
class WhatsappPreInspectionTypeSelf(View):
	def get(self, request, *args, **kwargs):
		application = UjjwalaV2Application.objects.filter(id=kwargs.get('pk')).first()

		if not application:
			return render(
				self.request, "ujjwala/response.html",
				{"heading": "Pre-Inspection", "message": "Application Id {} does not exist".format(kwargs.get('pk'))}
			)

		if not is_pre_inspection_applicable(application.id):
			return render(
				self.request, "ujjwala/response.html",
				{"heading": "Pre-Inspection",
				 "message": "Application Id {} not valid for Pre-Inspection".format(kwargs.get('pk'))}
			)

		pi_obj = PreInspection.objects.filter(parent_id=kwargs.get('pk')).first()
		if not pi_obj:
			pi_obj = PreInspection.objects.create(
				parent_id=application.id,
				# status=PreInspectionStatusEnum.KITCHEN_PHOTO,
				status=PreInspectionStatusEnum.CHANGE_ADDRESS,
				type=PreInspectionTypeEnum.SELF
			)

		if pi_obj.status not in (PreInspectionStatusEnum.SUBMITTED, PreInspectionStatusEnum.ACCEPTED):
			pi_obj.parent.event_whatsapp_pre_inspection_type_self_admin(pi_obj.id)
			message = "Application Id {} Whatsapp Message Sent.".format(kwargs.get('pk'))
		else:
			message = "Application Id {} not authorised for self inspection.".format(kwargs.get('pk'))

		return render(
			self.request, "ujjwala/response.html", {"heading": "Pre-Inspection", "message": message}
		)



# def WhatsappPreInspection(Inspection_data, unique_id, intent):
# 	conn = django_rq.get_connection("default")
# 	if not unique_id:
# 		return
# 	# Fetch the application using the unique ID
# 	application = UjjwalaV2Application.objects.filter(contact_mobile=unique_id).first()
# 	if not application:
# 		return f"इस फोन नंबर {unique_id} के साथ कोई आवेदन मौजूद नहीं है।"
#
# 	# Check if pre-inspection is applicable
# 	if not is_pre_inspection_applicable(application.id):
# 		return "आप प्री-निरीक्षण के लिए पात्र नहीं हैं। कृपया अपने आवेदन की स्थिति जांचें।"
#
# 	# Fetch the PreInspection object
# 	pi_obj = PreInspection.objects.filter(parent_id=application.id).first()
#
# 	# Handle kitchen-photo intent
# 	if intent == "kitchen-photo":
# 		link = conn.get(Inspection_data)
# 		if not link:
# 			return "Kitchen photo link not found in Inspection data."
#
# 		# Process and save the kitchen photo form
# 		form = KitchenPreInspectionForm(data={'pre_inspection': pi_obj, 'kitchen_photo': link})
# 		if form.is_valid():
# 			form.save()
# 			return "आपकी रसोई की फोटो अपडेट हो गई है, कृपया पता अपडेट के लिए नीचे दिया गया फॉर्म भरें।"
# 		else:
# 			return "रसोई की फोटो अपडेट करने में विफल।"
# 	# Handle address details
# 	if intent == "address_details":
# 		form = ChangeAddressForm(pre_inspection=pi_obj, data=Inspection_data)
# 		if form.is_valid():
# 			form.save()
# 			return "आपके पते का विवरण अपडेट हो गया है।"
# 		else:
# 			return "पते का विवरण अपडेट करने में विफल।"
# 	# Handle pin-location or main-gate intent
# 	if intent in ["pin-location", "main-gate"]:
# 		link = conn.get(Inspection_data)
# 		longitude = latitude = None
#
# 		if not link:
# 			try:
# 				location_data = json.loads(Inspection_data)
# 				latitude = location_data.get('latitude')
# 				longitude = location_data.get('longitude')
# 			except (json.JSONDecodeError, TypeError, KeyError) as e:
# 				return "Invalid location data."
#
# 		# Process and save the preview inspection form
# 		form = PreviewPreInspectionForm(data={
# 			'pre_inspection': pi_obj,
# 			'main_gate': link,
# 			'longitude': longitude,
# 			'latitude': latitude
# 		})
# 		if form.is_valid():
# 			form.save()
# 			if not link:
# 				return "आपकी पिन लोकेशन का डेटा अपडेट हो गया है, अब कृपया Verification के लिए अपनी रसोई वाली  फोटो साझा करें।"
# 			return "आपके मुख्य द्वार की फोटो अपडेट हो गई है, अब कृपया ऊपर दिए गए वीडियो को देखकर अपनी पिन लोकेशन साझा करें।"
# 		else:
# 			return "लोकेशन या फोटो अपडेट करने में विफल।"
#
# 	return "Invalid intent provided."


def WhatsappPreInspection(Inspection_data, unique_id, intent):
	conn = django_rq.get_connection("default")
	if not unique_id and Inspection_data is None:
		return
	# Fetch the application using the unique ID
	application = UjjwalaV2Application.objects.filter(contact_mobile=unique_id).first()
	if not application:
		return f"इस फोन नंबर {unique_id} के साथ कोई आवेदन मौजूद नहीं है।"

	# Check if pre-inspection is applicable
	if not is_pre_inspection_applicable(application.id):
		return "आप प्री-निरीक्षण के लिए पात्र नहीं हैं। कृपया अपने आवेदन की स्थिति जांचें।"

	# Fetch the PreInspection object
	pi_obj = PreInspection.objects.filter(parent_id=application.id).first()

	# Handle kitchen-photo intent
	if intent == "kitchen-photo":
		link = conn.get(Inspection_data)
		if not link:
			return "Kitchen photo link not found in Inspection data."

		# Process and save the kitchen photo form
		form = KitchenPreInspectionForm( pre_inspection= pi_obj ,data={'kitchen_photo': link})
		if form.is_valid():
			form.save()
			return "आपकी रसोई की फोटो अपडेट हो गई है, कृपया पता अपडेट के लिए नीचे दिया गया फॉर्म भरें।"
		else:
			return "रसोई की फोटो अपडेट करने में विफल।"
	# Handle address details
	if intent == "address_details":
		form = ChangeAddressForm(pre_inspection=pi_obj, data=Inspection_data)
		if form.is_valid():
			form.save()
			return "आपके पते का विवरण अपडेट हो गया है।"
		else:
			return "पते का विवरण अपडेट करने में विफल।"
	# Handle pin-location or main-gate intent
	if intent in ["pin-location", "main-gate"]:
		link = conn.get(Inspection_data)
		longitude = latitude = None

		if not link:
			try:
				location_data = json.loads(Inspection_data)
				latitude = location_data.get('latitude')
				longitude = location_data.get('longitude')
			except (json.JSONDecodeError, TypeError, KeyError) as e:
				return "Invalid location data."

		# Process and save the preview inspection form
		form = PreviewPreInspectionForm(pre_inspection=pi_obj  ,data={
			'pre_inspection': pi_obj,
			'main_gate': link,
			'longitude': longitude,
			'latitude': latitude
		})
		if form.is_valid():
			form.save()
			if not link:
				return "आपकी पिन लोकेशन का डेटा अपडेट हो गया है, अब कृपया Verification के लिए अपनी रसोई वाली  फोटो साझा करें।"
			return "आपके मुख्य द्वार की फोटो अपडेट हो गई है, अब कृपया ऊपर दिए गए वीडियो को देखकर अपनी पिन लोकेशन साझा करें।"
		else:
			print(form.errors)
			return "लोकेशन या फोटो अपडेट करने में विफल।"

	return "Invalid intent provided."


def check_ujjwala_status(contact_mobile):
	if not contact_mobile:
		return JsonResponse({"error": "Phone number is required."}, status=400)

	# Retrieve the application based on the provided contact mobile number
	application = UjjwalaV2Application.objects.filter(
		Q(contact_mobile=contact_mobile) | Q(sdms_mobile_number=contact_mobile)
	).first()
	print(f"the object application is {application}")
	if not application:
		return 'No application found for the provided phone number'

	# Fetch the rejection reason if applicable
	if 'reject' in application.status.lower():
		reject_reason = ujjwala_application_reject_reason_log(application.id)
		if reject_reason is not None:
			return f"Application rejected: {reject_reason}"

	# Check for PreInspection object
	pi_obj = PreInspection.objects.filter(parent_id=application.id).first()
	from ujjwala.enums import PreInspectionRejectionReasonsEnum
	# check for rejected status of pi
	if pi_obj.status == "REJECTED":
		inspection_app_content_type = ContentType.objects.get(model=PreInspection.__name__.lower() ,app_label= "ujjwala" )

		description = StateLog.objects.filter(
			object_id=pi_obj.id, content_type=inspection_app_content_type,
			state__icontains='reject'
		).order_by('-id').first()
		if description:
			json_text = json.loads(description.description).get("reason")[0]
			print(json_text[0] ,json_text )

			status_dict = dict(PreInspectionRejectionReasonsEnum.choices)
			print(f"the dict value we get {status_dict.get(json_text, 'not able to access')} and {status_dict}")
		return f"your application has been rejected due to { status_dict.get(json_text) or 'wrong details'}"

	# Handle different statuses for PreInspection
	if pi_obj.status in ["ALLOCATED", "OTP_VERIFIED", "CHANGE_ADDRESS", "KITCHEN_PHOTO", "PREVIEW_INSPECTION"]:
		return "Your pre-suraksha is incomplete. Please visit this link and complete it."

	if pi_obj.status == "SUBMITTED":
		return "Your pre-suraksha is under verification."

	# Fetch ConnectionDisbursement object
	connection = ConnectionDisbursement.objects.filter(parent=application.id).first()
	if connection is None:
		return 'No connection disbursement data found'

	if pi_obj.status == "ACCEPTED" and connection.status == "LEGAL_DOCUMENTS_PENDING":
		return "Please upload the signed ABC form to this link to complete your pre-suraksha."

	if connection.status == "LEGAL_DOCUMENTS_ACCEPTED" and not application.ekyc_cleared:
		return "Please visit Arun Gas with the ABC form and complete your eKYC verification."

	# # Handle application-level statuses
	# if application.status == "OMC_REJECTED":
	#     return "Your family member has a linked connection with another distributor. Please resolve this issue first."

	if application.status == "READY_FOR_DISBURSEMENT":
		return "You can call us to know when to come for receiving your connection cylinder."

	return "Status not recognized. Please contact support for further assistance."


# This View Shares Web Form Link To The Given Contact Number
@method_decorator(login_required, 'dispatch')
class ShareWebFormLink(TemplateView):
	template_name = "ujjwala/share_web_form_link.html"

	def post(self, request, *args, **kwargs):
		contact_mobile = request.POST.get('contact_mobile', '')

		if contact_mobile:
			application = UjjwalaV2Application.objects.filter(
				contact_mobile=contact_mobile
			).exclude(
				status=UjjwalaV2ApplicationStatus.DOCUMENTS_REUPLOAD
			).first()

			if application:
				messages.add_message(
					request, messages.ERROR, "Application already exist."
				)
			else:
				user = get_current_user()
				res = send_ujjwala_application_whatsapp_link_v2(contact_mobile, user.id, share_link=True)
				if res:
					messages.add_message(
						request, messages.INFO,
						"Ujjwala Application Link Shared To Contact Mobile: {}".format(
							contact_mobile
						)
					)
		return super().get(request, *args, **kwargs)


class UjjwalaApplicationSharedLinkView(View):

	def get(self, request, *args, **kwargs):
		data = kwargs.get('data', '')
		signer = Signer()
		data = base64.urlsafe_b64decode(data)
		data = eval(signer.unsign(data.decode('ascii')))
		application = UjjwalaV2Application.objects.filter(contact_mobile=data['contact_mobile']).first()
		if application:
			if not application.status == UjjwalaV2ApplicationStatus.DOCUMENTS_REUPLOAD:
				return render(
					self.request, "ujjwala/response.html",
					{"heading": "Ujjwala Application",
					 "message": "An application already exist with id: {}".format(application.id)}
				)
		user = User.objects.filter(id=data['user']).first()
		data.update({
			"source": "link_share",
			"signed_contact_mobile": signer.sign(data['contact_mobile']),
			"referral_code": "{} ({} {})".format(user.username, user.first_name, user.last_name),
			"referred_by": user,
		})
		return render(request, template_name='ujjwala/web_form.html', context=data)


class ApplicationView(View):

	def get_object(self, queryset=None):
		try:
			obj = ConnectionDisbursement.objects.get(pk=self.kwargs.get('pk'))
		except:
			raise Http404(
				"No Application Exist For Given Application Id"
			)
		return obj


# This View Shares Web Form Link To The Given Contact Number
@method_decorator(login_required, 'dispatch')
class ShareSelfPreInspectionLink(View):

	def get(self, request, *args, **kwargs):
		id = kwargs.get('pk')

		application = UjjwalaV2Application.objects.get(id=id)

		pi = PreInspection.objects.filter(parent_id=application.id)

		if not pi:
			PreInspection.objects.create(
				parent_id=application.id,
				# status=PreInspectionStatusEnum.KITCHEN_PHOTO,
				status=PreInspectionStatusEnum.CHANGE_ADDRESS,
				type=PreInspectionTypeEnum.SELF
			)

		if application.pre_inspection.status in (
				PreInspectionStatusEnum.SUBMITTED, PreInspectionStatusEnum.ACCEPTED
		):
			return render(
				self.request, "ujjwala/response.html",
				{"heading": "Pre Inspection",
				 "message": "Pre-Inspection Status: {}".format(application.pre_inspection.status)}
			)
		else:
			user = get_current_user()
			res = send_ujjwala_self_pre_inspection_share_link(
				application.contact_mobile, user.id, user.username, application
			)
			if res:
				message = "Self Pre-Inspection Link Shared For Application Id: {}".format(id)
			else:
				message = "Self Pre-Inspection Link Could Not Be Shared For Application Id: {}".format(id)
		return render(self.request, "ujjwala/response.html", {"heading": "Pre Inspection", "message": message})


@method_decorator(login_required, 'dispatch')
class UserDashboardView(TemplateView):
	template_name = "ujjwala/user_dashboard.html"

	def get_context_data(self, **kwargs):
		context = super().get_context_data(**kwargs)
		user = get_current_user()

		context.update({
			"user": user,
			"ujjwala_queryset": UjjwalaV2Application.objects.filter(filled_by=user),
			"ujjwala_rejected": UjjwalaV2Application.objects.filter(filled_by=user,
																	status=UjjwalaV2ApplicationStatus.APPLICATION_REJECTED),
			"ujjwala_material_delivered": UjjwalaV2Application.objects.filter(filled_by=user, status__in=[
				UjjwalaV2ApplicationStatus.MATERIAL_DELIVERED, UjjwalaV2ApplicationStatus.INSTALLED
			]),
			"preinspection_queryset": PreInspection.objects.filter(mechanic=user),
			"preinspection_accepted": PreInspection.objects.filter(mechanic=user,
																   status=PreInspectionStatusEnum.ACCEPTED),
			"preinspection_rejected": PreInspection.objects.filter(mechanic=user,
																   status=PreInspectionStatusEnum.REJECTED),
		})
		return context


class SharedSelfPreInspectionLinkView(View):

	def get(self, request, *args, **kwargs):
		data = kwargs.get('data', '')

		if data:
			data = unsign_data_base64(data)
			user_id = data.get('user_id', '')
			if user_id:
				user_id = sign_data_base64(data['user_id'])

			response = redirect(
				reverse('ujjwala:pre_inspection_form_view',
						args=('self', data['pre_inspection_id'])) + '?referral_user_id={}'.format(user_id)
			)
		else:
			response = redirect(
				reverse('ujjwala:pre_inspection_form_view',
						args=('self', data['pre_inspection_id']))
			)
		return response


class WhatsappUploadLegalForms(View):
	def get(self, request, *args, **kwargs):
		application = UjjwalaV2Application.objects.filter(id=kwargs.get('pk')).first()
		if not application:
			return HttpResponse("Application Id {} does not exist".format(kwargs.get('pk')))

		connection_disbursement = ConnectionDisbursement.objects.filter(parent_id=kwargs.get('pk')).first()

		if connection_disbursement:
			if connection_disbursement.status == ConnectionDisbursementStatusEnum.LEGAL_DOCUMENTS_PENDING:
				application.event_legal_documents_upload_channel_whatsapp()
				return render(
					self.request,
					"ujjwala/response.html",
					{
						"heading": "Legal Documents",
						"message": "Application Id {} Form A B C sent.".format(kwargs.get('pk'))
					}
				)
			else:
				return render(
					self.request,
					"ujjwala/response.html",
					{
						"heading": "Legal Documents",
						"message": "Application Id {} Form A B C Uploaded.".format(kwargs.get('pk'))
					}
				)
		else:
			return render(
				self.request,
				"ujjwala/response.html",
				{
					"heading": "Legal Documents",
					"message": "Application Id {} not valid state. Connection Disbursement not created.".format(kwargs.get('pk'))
				}
			)


class RecreateLegalDocumentView(View):
	def get(self, request, *args, **kwargs):
		application = UjjwalaV2Application.objects.filter(id=kwargs.get('pk')).first()
		if not application:
			return HttpResponse("Application Id {} does not exist".format(kwargs.get('pk')))

		document = re_create_legal_docs(application)
		resp = HttpResponse(document, content_type="application/pdf")
		resp['Content-Disposition'] = 'attachment; filename=%s' % 'ujjwala_physical_{}_legal_docs.pdf'.format(
			application.id)

		return resp


class ResetRoboFailedCount(View):
	def get(self, request, *args, **kwargs):
		application = UjjwalaV2Application.objects.filter(id=kwargs.get('pk')).first()
		if not application:
			return HttpResponse("Application Id {} does not exist".format(kwargs.get('pk')))
		application.robo_execution_failed_count = 0
		application.save()
		return HttpResponse(
			"Application Id {} Robo Execution Failed Count Set To Zero".format(kwargs.get('pk'))
		)


class WhatsappUpdateBankDetailsView(View):
	def get(self, request, *args, **kwargs):
		application = UjjwalaV2Application.objects.filter(id=kwargs.get('pk')).first()
		if not application:
			return HttpResponse("Application Id {} does not exist".format(kwargs.get('pk')))

		if not application.ifsc_code:
			application.event_whatsapp_update_bank_details()
			return HttpResponse(
				"Update Bank Details Message Sent For Application Id: {}".format(kwargs.get('pk'))
			)
		else:
			return HttpResponse(
				"Bank Details Already Uploaded For Application Id: {}".format(kwargs.get('pk'))
			)


class ApplicationStatusView(DetailView):
	model = UjjwalaV2Application

	def get_template_names(self):
		return 'ujjwala/status.html'


@method_decorator(login_required, 'dispatch')
class UjjwalaApplicationWebFormView(TemplateView):
	template_name = "ujjwala/web_form.html"

# def get_context_data(self, **kwargs):
#     context_data = super().get(**kwargs)
#     form_fill_area_list = FormFillArea.objects.all()
#     context_data = context_data.update({
#         "form_fill_area_list": form_fill_area_list
#     })
#     return context_data


@method_decorator(login_required, 'dispatch')
class UjjwalaAddressReviewListView(ListView):
	model = UjjwalaV2Application
	template_name = 'ujjwala/review/address_review_listview.html'
	paginate_by = 20

	permission = 'has_view_permission'

	def get_queryset(self):
		return UjjwalaV2Application.objects.filter(status=UjjwalaV2ApplicationStatus.REVIEW_ADDRESS).order_by(
			'updated_on')

	def get_context_data(self, **kwargs):
		context = super(UjjwalaAddressReviewListView, self).get_context_data(**kwargs)
		address_reviews = self.get_queryset()
		paginator = Paginator(address_reviews, self.paginate_by)

		page = self.request.GET.get('page')

		try:
			address_reviews = paginator.page(page)
		except PageNotAnInteger:
			address_reviews = paginator.page(1)
		except EmptyPage:
			address_reviews = paginator.page(paginator.num_pages)

		context['address_review_list'] = address_reviews
		return context


@method_decorator(login_required, 'dispatch')
class UjjwalaAddressReviewView(FormView, ApplicationView):
	model = UjjwalaV2Application
	template_name = 'ujjwala/review/address_review.html'
	form_class = ReviewUpdatedAddressForm

	def get_success_url(self):
		return reverse('ujjwala:address_review_list')

	def dispatch(self, request, *args, **kwargs):
		user = get_current_user()
		if not user.has_perm('can_review_address', 'ujjwala'):
			return render(request, 'ujjwala/no_permissions.html')

		application_id = kwargs.get('pk', '')
		if application_id:
			obj = self.get_object()
			if obj.status != UjjwalaV2ApplicationStatus.REVIEW_ADDRESS:
				messages.add_message(
					request, messages.ERROR, "Application Id: {} Not In Update Address Status".format(obj.id)
				)
				return redirect('ujjwala:address_review_list')
		return super().dispatch(request, *args, **kwargs)

	def get_object(self, queryset=None):
		try:
			obj = UjjwalaV2Application.objects.get(pk=self.kwargs.get('pk'))
		except:
			raise Http404(
				"No Application Exist For Given Application Id"
			)
		return obj

	def form_valid(self, form):
		obj = self.get_object()
		data = form.cleaned_data
		address_json = {
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

		if data['review_status'] == 'ACCEPTED':
			obj.transition_review_address_updated(
				review_status=data['review_status'],
				by=get_current_user(),
				description='{} - {}'.format(data.get('review_status'), data.get('rejected_reason' '')),
				address_json=address_json
			)
		else:
			obj.transition_address_change()

		obj.save()
		return redirect(self.get_success_url())

	def get_form_kwargs(self):
		kwargs = super().get_form_kwargs()
		obj = self.get_object()
		kwargs['initial'] = obj.address_json
		return kwargs

	def get_context_data(self, **kwargs):
		context = super().get_context_data(**kwargs)
		obj = self.get_object()
		# address_form = UpdateAddressForm(initial=obj.address_json)
		state_log = StateLog.objects.filter(
			object_id=obj.id,
			content_type=ContentType.objects.get(app_label='ujjwala', model='ujjwalav2application'),
			state=UjjwalaV2ApplicationStatus.REVIEW_ADDRESS
		).order_by('-id').first()
		context.update({
			"obj": obj,
			"old_address": state_log.description
		})
		return context


@method_decorator(login_required, 'dispatch')
class UjjwalaPreInspectionListView(ListView):
	model = PreInspection

	paginate_by = 20
	permission = 'has_view_permission'

	def get_queryset(self):
		return PreInspection.objects.filter(
			mechanic=get_current_user()
		).order_by('-submitted_on')

	def get_template_names(self):
		return 'ujjwala/pre-inspection/pre_inspection_listview.html'


@method_decorator(login_required, 'dispatch')
class PreInspectionReviewListView(ListView):
	model = PreInspection

	paginate_by = 20
	permission = 'has_view_permission'

	def get_queryset(self):
		return PreInspection.objects.filter(
			status=PreInspectionStatusEnum.SUBMITTED
		).exclude(parent__status='APPLICATION_REJECTED').order_by('submitted_on')

	def get_template_names(self):
		return 'ujjwala/review/pre_inspection_review_listview.html'


@method_decorator(login_required, 'dispatch')
class PreInspectionReviewView(FormView, ApplicationView):
	model = PreInspection
	template_name = 'ujjwala/review/pre_inspection_review.html'
	form_class = PreInspectionReviewAdminForm

	def get_success_url(self):
		return reverse('ujjwala:pre_inspection_review_list')

	def dispatch(self, request, *args, **kwargs):
		return HttpResponse(content="Not Allowed")

	# user = get_current_user()
	# if not is_member_of_reviewer_group(user):
	# 	return render(request, 'ujjwala/no_permissions.html')
	# application_id = request.GET.get('application_id', '')
	# if application_id:
	# 	pre_inspection = self.get_object()
	# 	if pre_inspection.status != PreInspectionStatusEnum.SUBMITTED:
	# 		messages.add_message(
	# 			request, messages.ERROR, "Application Id: {} - {}".format(
	# 				pre_inspection.parent_id, pre_inspection.get_status_display()
	# 			)
	# 		)
	# 		return redirect('ujjwala:installation_review')
	# return super().dispatch(request, *args, **kwargs)

	def get_object(self, queryset=None):
		try:
			obj = PreInspection.objects.get(pk=self.kwargs.get('pk'))
		except:
			raise Http404(
				"No Application Exist For Given Application Id"
			)
		return obj

	def form_valid(self, form):
		obj = self.get_object()
		data = form.cleaned_data
		obj.pre_inspection_review(
			review_status=data['review_status'],
			by=get_current_user(),
			description=data['description'],
			rejected_reasons=data['rejected_reasons']
		)
		obj.save()
		return redirect(self.get_success_url())

	def get_form_kwargs(self):
		kwargs = super().get_form_kwargs()
		# connection_disbursement = self.get_object()
		# kwargs['connection_disbursement'] = connection_disbursement
		return kwargs

	def get_context_data(self, **kwargs):
		context = super().get_context_data(**kwargs)
		obj = self.get_object()

		kitchen_photo = obj.documents.filter(
			type=UjjwalaApplicationDocumentsEnum.KITCHEN_PHOTO
		).first().link

		main_gate = obj.documents.filter(
			type=UjjwalaApplicationDocumentsEnum.MAIN_GATE
		).first().link

		change_address_url = reverse(
			'ujjwala:change_address_view',
			kwargs={
				'pk': obj.id,
			}
		)

		context.update({
			"change_address_url": self.request.build_absolute_uri(change_address_url)
		})

		context.update({
			"obj": obj,
			"kitchen_photo": kitchen_photo,
			"main_gate": main_gate,
			"location": f"https://maps.googleapis.com/maps/api/staticmap?center={obj.latitude},{obj.longitude}&zoom=16&size=600x300&maptype=roadmap&markers=color:red|label:C|{obj.latitude},{obj.longitude}&key=AIzaSyCsnS5l8LDnJGdgEBlcnG3_DnwJW_2sEvg"
		})

		if obj.type == PreInspectionTypeEnum.MECHANIC:
			context.update({
				"audio_file": obj.documents.get(
					type=UjjwalaApplicationDocumentsEnum.SAFETY_AUDIO
				).link
			})
		return context


class UjjwalaApplicationDisplayOtp(View):
	model = Otp

	def get(self, request, *args, **kwargs):
		obj = Otp.objects.filter(reference_number=kwargs.get('ref_no')).first()

		if obj:
			return render(self.request, "ujjwala/otp/ujjwala_application_display_otp.html", {
				"obj": obj
			})
		else:
			return HttpResponse(content="Invalid Reference Number")


@method_decorator(login_required, 'dispatch')
class UjjwalaApplicationReuploadFormView(FormView):
	form_class = UjjwalaDocumentsReuploadForm

	def get_initial(self):
		"""
		Returns the initial data to use for forms on this view.
		"""
		initial = super().get_initial()
		initial['application_id'] = self.kwargs.get('pk')

		return initial


@method_decorator(login_required_if_mech_inspection, 'dispatch')
@method_decorator(csrf_exempt, 'dispatch')
class PreInspectionView(FormView):
	model = PreInspection
	pre_inspection_step0_template = 'ujjwala/pre-inspection/steps/step0.html'
	pre_inspection_step1_template = 'ujjwala/pre-inspection/steps/step1.html'
	pre_inspection_step2_template = 'ujjwala/pre-inspection/steps/step2.html'
	pre_inspection_step3_template = 'ujjwala/pre-inspection/steps/step3.html'
	success_url = '.'

	stage_1_generate_otp = 'ujjwala/pre-inspection/pre_inspection_generate_otp_form.html'
	stage_2_validate_otp = 'ujjwala/pre-inspection/pre_inspection_validate_otp_form.html'

	def dispatch(self, request, *args, **kwargs):
		pre_inspection = self.get_object()
		if pre_inspection.status in (
				PreInspectionStatusEnum.SUBMITTED,
				PreInspectionStatusEnum.ACCEPTED,
		):
			return render(self.request, 'ujjwala/pre-inspection/pre_inspection_status.html', context={
				'pre_inspection': pre_inspection
			})

		if self.kwargs.get('type') == 'mech':
			if pre_inspection.status == PreInspectionStatusEnum.ALLOCATED \
					or (pre_inspection.status in (PreInspectionStatusEnum.REJECTED, PreInspectionStatusEnum.REDO)
						and pre_inspection.type == PreInspectionTypeEnum.MECHANIC
			):
				return self.otp_verification(pre_inspection)

		return super().dispatch(request, *args, **kwargs)

	def otp_verification(self, pre_inspection):
		context = {'pre_inspection': pre_inspection, 'application': pre_inspection.parent}
		if self.request.method.lower() == 'get':
			app = pre_inspection.parent
			context.update({
				'form': PreInspectionAllocatedGenerateOtpForm(
					mobile_nos=app.all_contacts,
					initial={
						'pre_inspection_id': pre_inspection.id,
						'application_id': pre_inspection.parent_id
					}
				)
			})
			return render(self.request, self.stage_1_generate_otp, context)
		elif self.request.method.lower() == 'post':
			if self.request.POST.get('form_type') == 'generate_otp_form':
				app = UjjwalaV2Application.objects.get(pk=pre_inspection.parent_id)
				form = PreInspectionAllocatedGenerateOtpForm(
					mobile_nos=app.all_contacts,
					data=self.request.POST,
				)
				if not form.is_valid():
					context.update({
						'form': form
					})
					return render(self.request, self.stage_1_generate_otp, context)
				otp_obj = form.send_otp()
				app_id = form.data.get('application_id')
				context.update({
					'form': PreInspectionAllocatedValidateOtpForm(
						initial={
							'application_id': app_id,
							'reference_number': otp_obj.reference_number,
							'mobile': otp_obj.mobile
						}
					)
				})
				return render(self.request, self.stage_2_validate_otp, context)
			elif self.request.POST.get('form_type') == 'validate_otp_form':
				form = PreInspectionAllocatedValidateOtpForm(data=self.request.POST)
				otp_obj = Otp.objects.get(reference_number=self.request.POST['reference_number'])
				if not form.is_valid():
					context.update({
						'form': PreInspectionAllocatedValidateOtpForm(
							initial={
								'application_id': pre_inspection.parent_id,
								'reference_number': otp_obj.reference_number,
								'mobile': otp_obj.mobile
							}
						)
					})
					return render(self.request, self.stage_2_validate_otp, context)
				if pre_inspection.type == PreInspectionTypeEnum.SELF:
					pre_inspection.pre_inspection_otp_verified(
						description="Allocated Inspection Otp Verified, Customer Phone {}".format(otp_obj.mobile)
					)
					pre_inspection.save()

					# pre_inspection.pre_inspection_change_address(
					# 	description="Skipped By Admin, Change Address"
					# )
					pre_inspection.save()
					return redirect('ujjwala:pre_inspection_form_view', type='self', pk=pre_inspection.id)
				else:
					pre_inspection.pre_inspection_otp_verified(
						by=get_current_user(),
						description="Allocated Inspection Otp Verified, Customer Phone {}".format(otp_obj.mobile)
					)
					pre_inspection.save()

					# pre_inspection.pre_inspection_change_address(
					# 	by=get_current_user(),
					# 	description="Skipped By Admin, Change Address"
					# )
					# pre_inspection.save()
					return redirect('ujjwala:pre_inspection_form_view', type='mech', pk=pre_inspection.id)

	def get_object(self, queryset=None):
		try:
			obj = PreInspection.objects.get(pk=self.kwargs.get('pk'))
		except:
			raise Http404(
				"No %(verbose_name)s found matching the query" %
				{'verbose_name': queryset.model._meta.verbose_name}
			)
		return obj

	def get_form_class(self):
		application = self.get_object()
		if application.status in (
		PreInspectionStatusEnum.CHANGE_ADDRESS, PreInspectionStatusEnum.REJECTED, PreInspectionStatusEnum.REDO):
			return ChangeAddressForm
		elif application.status == PreInspectionStatusEnum.KITCHEN_PHOTO:
			return KitchenPreInspectionForm
		elif application.status == PreInspectionStatusEnum.SAFETY_AUDIO:
			return AudioOnSafetyForm
		elif application.status == PreInspectionStatusEnum.PREVIEW_INSPECTION:
			return PreviewPreInspectionForm

	def form_valid(self, form):
		form.save()
		if form.__class__ == PreviewPreInspectionForm:
			obj = self.get_object()
			if obj.type == PreInspectionTypeEnum.SELF:
				referral_user_id = self.request.GET.get('referral_user_id', '')
				if referral_user_id:
					referral_user_id = unsign_data_base64(referral_user_id)
					obj.referral_user_id = referral_user_id
				else:
					obj.referral_user_id = None
				obj.save()

				response = HttpResponse(
					content="<h1>Pre-Inspection Submitted For Review</h1>"
				)
				return response

		return HttpResponseRedirect(
			self.get_success_url() + '?referral_user_id={}'.format(self.request.GET.get('referral_user_id', ''))
		)

	# def form_invalid(self, form):
	# 	print(form)

	def get_template_names(self):
		pre_inspection_obj = self.get_object()
		if pre_inspection_obj.status in (
				PreInspectionStatusEnum.CHANGE_ADDRESS,
				PreInspectionStatusEnum.REJECTED,
				PreInspectionStatusEnum.REDO,

		):
			return self.pre_inspection_step0_template
		elif pre_inspection_obj.status == PreInspectionStatusEnum.KITCHEN_PHOTO:
			return self.pre_inspection_step1_template
		elif pre_inspection_obj.status == PreInspectionStatusEnum.SAFETY_AUDIO:
			return self.pre_inspection_step2_template
		elif pre_inspection_obj.status == PreInspectionStatusEnum.PREVIEW_INSPECTION:
			return self.pre_inspection_step3_template

	# def get_form(self, form_class=None):
	# 	form = super().get_form(form_class=form_class)
	# 	# if form.__class__ == ChangeAddressForm:
	# 	# 	form = ChangeAddressForm(initial=form.pre_inspection.parent.address_json)
	# 	return form

	def get_form_kwargs(self):
		kwargs = super().get_form_kwargs()
		pre_inspection = self.get_object()
		kwargs['pre_inspection'] = pre_inspection
		if pre_inspection.status in (
				PreInspectionStatusEnum.CHANGE_ADDRESS,
				PreInspectionStatusEnum.REJECTED,
				PreInspectionStatusEnum.REDO
		):
			kwargs['initial'] = pre_inspection.parent.address_json
		return kwargs

	def get_context_data(self, **kwargs):
		context = super().get_context_data(**kwargs)

		referral_user_id = self.request.GET.get('referral_user_id', '')

		if referral_user_id:
			referral_user_id = unsign_data_base64(referral_user_id)
			user = User.objects.filter(id=referral_user_id).first()
		else:
			user = None

		context.update({
			"obj": self.get_object(),
			"referral_user": user
		})

		return context


@method_decorator(login_required, 'dispatch')
class PreInspectionCreateView(View):
	model = PreInspection
	stage_1_template = 'ujjwala/pre-inspection/pre_inspection_initial_form.html'
	stage_2_template = 'ujjwala/pre-inspection/pre_inspection_generate_otp_form.html'
	stage_3_template = 'ujjwala/pre-inspection/pre_inspection_validate_otp_form.html'

	def get(self, request, *args, **kwargs):
		return render(self.request, self.stage_1_template, {
			'form': PreInspectionInitialForm()
		})

	def post(self, request, *args, **kwargs):
		if self.request.POST.get('form_type') == 'initial_form':
			form = PreInspectionInitialForm(data=request.POST)

			if not form.is_valid():
				return render(self.request, self.stage_1_template, {
					'form': form
				})
			app_id = form.data.get('application_id')

			# pre_inspection_obj = PreInspection.objects.filter(
			#     parent_id=app_id
			# ).exclude(
			#     status__in=[
			#         PreInspectionStatusEnum.REJECTED
			#     ]
			# ).first()

			pre_inspection_obj = PreInspection.objects.filter(
				parent_id=app_id
			).first()

			if pre_inspection_obj:
				if pre_inspection_obj.status != PreInspectionStatusEnum.REJECTED:
					if pre_inspection_obj.type == PreInspectionTypeEnum.SELF:
						return redirect(
							'ujjwala:pre_inspection_form_view', type='self', pk=pre_inspection_obj.pk
						)
					elif pre_inspection_obj.type == PreInspectionTypeEnum.MECHANIC:
						return redirect(
							'ujjwala:pre_inspection_form_view', type='mech',
							pk=pre_inspection_obj.pk
						)

			app = UjjwalaV2Application.objects.filter(pk=app_id).first()
			return render(self.request, self.stage_2_template, {
				'form': PreInspectionGenerateOtpForm(
					mobile_nos=app.all_contacts,
					initial={
						'application_id': app_id
					}
				),
				'application': UjjwalaV2Application.objects.get(pk=app_id)
			})
		elif self.request.POST.get('form_type') == 'generate_otp_form':
			app_id = self.request.POST.get('application_id')
			app = UjjwalaV2Application.objects.filter(pk=app_id).first()
			form = PreInspectionGenerateOtpForm(
				mobile_nos=app.all_contacts,
				data=request.POST
			)
			if not form.is_valid():
				return render(self.request, self.stage_2_template, {
					'form': form,
					'application': app,
				})
			otp_obj = form.send_otp()
			app_id = form.data.get('application_id')
			return render(self.request, self.stage_3_template, {
				'form': PreInspectionValidateOtpForm(
					initial={
						'application_id': app_id,
						'reference_number': otp_obj.reference_number,
						'mobile': otp_obj.mobile
					}),
			})
		elif self.request.POST.get('form_type') == 'validate_otp_form':
			form = PreInspectionAllocatedValidateOtpForm(data=request.POST)
			otp_obj = Otp.objects.filter(reference_number=request.POST['reference_number']).first()
			if not form.is_valid():
				return render(self.request, self.stage_3_template, {
					'form': form,
					'reference_number': otp_obj.reference_number,
					'mobile': otp_obj.mobile
				})

			app_id = form.data.get('application_id')
			obj = PreInspection.objects.filter(
				parent_id=app_id
			).first()

			if obj:
				obj.type = PreInspectionTypeEnum.MECHANIC
			else:
				obj = PreInspection.objects.create(
					parent_id=app_id,
					status=PreInspectionStatusEnum.ALLOCATED,
					type=PreInspectionTypeEnum.MECHANIC,
					mechanic=get_current_user()
				)

			obj.pre_inspection_otp_verified(
				by=get_current_user(),
				description="Instant Inspection Created, Customer Phone {}".format(otp_obj.mobile)
			)
			obj.save()

			# obj.pre_inspection_change_address(
			# 	by=get_current_user(),
			# 	description="Skipped By Admin, Customer Address"
			# )
			# obj.save()

			return redirect('ujjwala:pre_inspection_form_view', type='mech', pk=obj.pk)


class ReviewForm(forms.ModelForm):
	action = forms.ChoiceField(
		widget=forms.Select,
		choices=(
			("A", "Accept"),
			("R", "Reject")
		),
		required=False
	)
	remarks = forms.CharField(widget=forms.TextInput)

	class Meta:
		from ujjwala.models import PreInspection
		model = PreInspection
		fields = ('id', 'action', 'remarks')


class UjjwalaApplicationLegalDocumentsUpload(FormView):
	form_class = UjjwalaLegalDocumentsUpload
	template_name = "ujjwala/legal-document-upload-form.html"

	def get_object(self, queryset=None):
		try:
			obj = PreInspection.objects.get(pk=self.kwargs.get('pk'))
		except:
			raise Http404(
				"No %(verbose_name)s found matching the query" %
				{'verbose_name': queryset.model._meta.verbose_name}
			)
		return obj


	def dispatch(self, request, *args, **kwargs):

		connection_disbursement = ConnectionDisbursement.objects.get(pk=self.kwargs.get('pk'))

		if connection_disbursement.status not in (
				ConnectionDisbursementStatusEnum.LEGAL_DOCUMENTS_PENDING,
		):
			return HttpResponse(content='Status: {}'.format(connection_disbursement.status))

		return super().dispatch(request, *args, **kwargs)

	# return redirect('ujjwala:legal_documents_upload', pk=self.kwargs.get('pk'))

		if current_user.is_staff or DisbursementDrive.objects.filter(status='ACTIVE',
																	 team_members=current_user).exists() or front_end_staff:
			qs = UjjwalaV2Application.objects.all()
		else:
			qs = UjjwalaV2Application.objects.filter(Q(filled_by__isnull=True) | Q(filled_by=current_user))

		contact_mobile = request.GET.get('contact_mobile', '')
		uid = request.GET.get('uid', '')
		application_id = request.GET.get('application_id', '')
		application = None

		if contact_mobile:
			application = qs.filter(Q(contact_mobile=contact_mobile) | Q(sdms_mobile_number=contact_mobile)) .first()
		elif uid:
			family_member = FamilyMembers.objects.filter(uid_no=uid).first()
			if family_member:
				application = family_member.parent
		elif application_id:
			application: UjjwalaV2Application = qs.filter(id=application_id).first()

		if application:
			reject_reason = ujjwala_application_reject_reason_log(application.id)
			UjjwalaSearchLog.objects.create(
				parent=application, requested_by=get_current_user(), source=UjjwalaSearchLogEnum.WEB,
				activity_datetime=datetime.datetime.now()
			)
			invitation = None

			cd_obj: ConnectionDisbursement = ConnectionDisbursement.objects.filter(parent=application).first()

			if cd_obj:
				invitation = cd_obj.invitation.first()
			return render(
				request, self.template_name, context={
					'obj': application, 'rejected_reason': reject_reason, "invitation": invitation
				}
			)
		else:
			messages.add_message(
				request, messages.ERROR, "Please Enter Contact Mobile Or Aadhaar Or Application Id To Search"
			)
		return super().get(request, *args, **kwargs)

	def get_context_data(self, **kwargs):
		context = super().get_context_data(**kwargs)
		user = get_current_user()
		# if not is_member_of_disbursement_drive(user):
		# 	return render(self.request, 'ujjwala/no_permissions.html')

		context.update({
			"disbursement_user": True,
			"obj": self.get_object()
		})
		return context


@method_decorator(login_required, 'dispatch')
class UjjwalaApplicationStatusView(TemplateView):
	template_name = "ujjwala/application_status/application_search_status.html"

	def get(self, request, *args, **kwargs):
		current_user: User = get_current_user()

		front_end_staff = is_front_end_staff(current_user)

		if current_user.is_staff or DisbursementDrive.objects.filter(status='ACTIVE',
																	 team_members=current_user).exists() or front_end_staff:
			qs = UjjwalaV2Application.objects.all()
		else:
			qs = UjjwalaV2Application.objects.filter(Q(filled_by__isnull=True) | Q(filled_by=current_user))

		contact_mobile = request.GET.get('contact_mobile', '')
		uid = request.GET.get('uid', '')
		application_id = request.GET.get('application_id', '')
		application = None

		if contact_mobile:
			application = qs.filter(Q(contact_mobile=contact_mobile) | Q(sdms_mobile_number=contact_mobile)).first()
		elif uid:
			family_member = FamilyMembers.objects.filter(uid_no=uid).first()
			if family_member:
				application = family_member.parent
		elif application_id:
			application: UjjwalaV2Application = qs.filter(id=application_id).first()

		if application:
			reject_reason = ujjwala_application_reject_reason_log(application.id)
			UjjwalaSearchLog.objects.create(
				parent=application, requested_by=get_current_user(), source=UjjwalaSearchLogEnum.WEB,
				activity_datetime=datetime.datetime.now()
			)
			invitation = None

			cd_obj: ConnectionDisbursement = ConnectionDisbursement.objects.filter(parent=application).first()

			if cd_obj:
				invitation = cd_obj.invitation.first()
			return render(
				request, self.template_name, context={
					'obj': application, 'rejected_reason': reject_reason, "invitation": invitation
				}
			)
		else:
			messages.add_message(
				request, messages.ERROR, "Please Enter Contact Mobile Or Aadhaar Or Application Id To Search"
			)
		return super().get(request, *args, **kwargs)

	def get_context_data(self, **kwargs):
		context = super().get_context_data(**kwargs)
		user = get_current_user()
		# if not is_member_of_disbursement_drive(user):
		# 	return render(self.request, 'ujjwala/no_permissions.html')

		context.update({
			"disbursement_user": True
		})
		return context


@method_decorator(login_required, 'dispatch')
class UjjwalaConnectionDisbursementListView(ListView):
	model = ConnectionDisbursement

	paginate_by = 100
	permission = 'has_view_permission'

	def get_queryset(self):
		disbursement_drive = get_current_user_disbursement_drive(get_current_user())

		return ConnectionDisbursement.objects.filter(
			status__in=[
				ConnectionDisbursementStatusEnum.LEGAL_DOCUMENTS_PENDING,
				ConnectionDisbursementStatusEnum.LEGAL_DOCUMENTS_REVIEW,
				ConnectionDisbursementStatusEnum.LEGAL_DOCUMENTS_ACCEPTED,
				ConnectionDisbursementStatusEnum.SV_LABEL_PRINT,
				# ConnectionDisbursementStatusEnum.SOCIAL_MEDIA_UPDATES,
				ConnectionDisbursementStatusEnum.MATERIAL_DELIVERY_OTP_VERIFIED,
			],
			disbursement_drive=disbursement_drive
		).order_by('updated_on')

	def get_template_names(self):
		return 'ujjwala/disbursement/connection_disbursement_listview.html'

	def get_context_data(self, *, object_list=None, **kwargs):
		context = super().get_context_data(object_list=object_list, **kwargs)
		user = get_current_user()
		if not is_member_of_disbursement_drive(user):
			return render(self.request, 'ujjwala/no_permissions.html')

		disbursement_drive = DisbursementDrive.objects.filter(
			team_members=user, status=DisbursementDriveStatusEnum.ACTIVE
		).first()

		cd_grouped_status_list = []

		qs = ConnectionDisbursement.objects.filter(
			disbursement_drive=disbursement_drive,
			status=ConnectionDisbursementStatusEnum.LEGAL_DOCUMENTS_PENDING).order_by('walk_in_date')

		cd_grouped_status_list.append({
			"status": 'Legal Documents Not Uploaded (Upload Pending)',
			"id": 'legal_documents_not_uploaded_upload_pending',
			"object_list": qs,
			"total_records": qs.count(),
			"background_color": 'lightpink'
		})

		qs = ConnectionDisbursement.objects.filter(
			disbursement_drive=disbursement_drive,
			social_media_update_done=False).order_by('walk_in_date')
		cd_grouped_status_list.append({
			"status": "Social Media Photo Pending",
			"id": 'social_media_photo_pending',
			"object_list": qs,
			"total_records": qs.count(),
			"background_color": "lightsalmon"
		})

		qs = ConnectionDisbursement.objects.filter(
			disbursement_drive=disbursement_drive,
			status__in=[
				ConnectionDisbursementStatusEnum.SV_LABEL_PRINT,
				ConnectionDisbursementStatusEnum.MATERIAL_DELIVERY_OTP_VERIFIED
			]).order_by('walk_in_date')

		cd_grouped_status_list.append({
			"status": 'Material Delivery Pending',
			"id": 'material_delivery_pending',
			"object_list": qs,
			"total_records": qs.count(),
			"background_color": 'lightblue'
		})

		qs = ConnectionDisbursement.objects.filter(
			disbursement_drive=disbursement_drive,
			status=ConnectionDisbursementStatusEnum.MATERIAL_DELIVERED).order_by('-updated_on')
		cd_grouped_status_list.append({
			"status": 'Material Delivered',
			"id": 'material_delivered',
			"object_list": qs,
			"total_records": qs.count(),
			"background_color": 'lightgreen'
		})

		connection_disbursement_count = ConnectionDisbursement.objects.filter(
			disbursement_drive=disbursement_drive
		).exclude(walk_in_date=None).count()

		context.update({
			"disbursement_user": True,
			"current_disbursement_index": connection_disbursement_count,
			"max_walkins": disbursement_drive.max_walk_ins,
			"disbursement_drive": disbursement_drive,
			"cd_grouped_status_list": cd_grouped_status_list
		})
		return context

	def get(self, request, *args, **kwargs):
		user = get_current_user()
		if not is_member_of_disbursement_drive(user):
			return render(request, 'ujjwala/no_permissions.html')
		application_id = request.GET.get('application_id', '')

		if application_id:
			disbursement_drive: DisbursementDrive = DisbursementDrive.objects.filter(
				date__lte=datetime.datetime.now().date(), status=DisbursementDriveStatusEnum.ACTIVE
			).first()
			if not disbursement_drive:
				messages.add_message(
					request, messages.INFO, "No Active Disbursement Drive Exist"
				)
			else:
				obj: ConnectionDisbursement = ConnectionDisbursement.objects.filter(parent_id=application_id).first()
				if obj:
					allowed = True
					if obj.status not in disbursement_drive.legal_documents_conditions:
						messages.add_message(
							request, messages.ERROR, "Application Id: {} - {}".format(
								application_id, obj.status
							)
						)
						allowed = False

					if allowed and obj.parent.filled_by and not disbursement_drive.filled_by_filter == FilledByFilterEnum.DISABLED:
						filter_allowed = disbursement_drive.filled_by_filter == FilledByFilterEnum.ALLOWED
						in_list = disbursement_drive.filled_by.filter(username=obj.parent.filled_by.username).exists()
						if filter_allowed and not in_list:
							allowed = False
						if not filter_allowed and in_list:
							allowed = False
						if not allowed:
							messages.add_message(
								request, messages.ERROR,
								"Not Allowed In This Disbursement Drive. Application Id: {} - {}".format(
									application_id, obj.status
								)
							)

					if allowed and disbursement_drive.allow_only_sv_generated:
						if not obj.invitation.exists():
							messages.add_message(
								request, messages.ERROR,
								"Application Id: {} No SV Generated.".format(application_id)
							)
					if allowed:
						return redirect('ujjwala:connection_disbursement_form_view', pk=obj.pk)
				else:
					messages.add_message(
						request, messages.ERROR,
						"Application Id: {} Connection Disbursement not found".format(application_id)
					)
		return super().get(request, *args, **kwargs)


@method_decorator(login_required, 'dispatch')
class ConnectionDisbursementView(TemplateView, ApplicationView):
	model = ConnectionDisbursement
	walk_in_template = 'ujjwala/disbursement/forms/walk_in_confirmation.html'
	ujjwala_form_a_b_c_template = "ujjwala/disbursement/print_ujjwala_form_a_b_c.html"
	success_url = '.'

	stage_1_generate_otp = 'ujjwala/disbursement/otp/generate_otp_form.html'
	# stage_1_generate_otp = 'ujjwala/otp/generate_otp_form.html'
	stage_2_validate_otp = 'ujjwala/otp/validate_otp_form.html'

	def dispatch(self, request, *args, **kwargs):
		user = get_current_user()
		if not is_member_of_disbursement_drive(user):
			return render(request, 'ujjwala/no_permissions.html')
		disbursement_drive = DisbursementDrive.objects.filter(
			status=DisbursementDriveStatusEnum.ACTIVE, team_members=user
		).first()

		if not disbursement_drive:
			messages.add_message(
				request, messages.INFO,
				f"No Active Disbursement Drive. For Help Contact Manager - {disbursement_drive.manager.first_name} {disbursement_drive.manager.last_name}."
			)
			return redirect('ujjwala:connection_disbursement_list')
		#if not datetime.datetime.today().date() == disbursement_drive.date:
		#	messages.add_message(
		#		request, messages.INFO,
		#		f"Please Close Existing Disbursement Drive. For Help Contact Manager - {disbursement_drive.manager.first_name} {disbursement_drive.manager.last_name}."
		#	)
		#	return redirect('ujjwala:connection_disbursement_list')

		connection_disbursement_count = ConnectionDisbursement.objects.filter(
			disbursement_drive=disbursement_drive
		).exclude(walk_in_date=None).count()

		if connection_disbursement_count == disbursement_drive.max_walk_ins:
			messages.add_message(
				request, messages.INFO,
				"Max Walk-ins for Disbursement Drive achieved."
			)
			return redirect('ujjwala:connection_disbursement_list')
		connection_disbursement = self.get_object()

		if connection_disbursement:
			cd_invitation = ConnectionDisbursementInvitation.objects.filter(
				parent_id=connection_disbursement.id).first()

			if not cd_invitation:
				messages.add_message(
					request, messages.ERROR,
					"Approval Awaited, Expected After Election"
				)
			elif not connection_disbursement.parent.ekyc_cleared:
				messages.add_message(
					request, messages.ERROR,
					"Application Id : {} Status: {} Pre-Inspection Status: {} Ekyc Cleared: {}".format(
						connection_disbursement.parent_id, connection_disbursement.parent.get_status_display(),
						connection_disbursement.parent.pre_inspection.get_status_display(),
						connection_disbursement.parent.ekyc_cleared
					)
				)
			elif connection_disbursement.parent.status in (
					UjjwalaV2ApplicationStatus.NIC_CLEARED,
					UjjwalaV2ApplicationStatus.READY_FOR_DISBURSEMENT,
					UjjwalaV2ApplicationStatus.NIC_CLEARED_SDMS_RELATION_CANCELLED
			):
				if not connection_disbursement.walk_in_date or \
						(connection_disbursement.walk_in_date.date() != datetime.datetime.today().date()):
					return self.otp_verification(connection_disbursement)
			else:
				messages.add_message(
					request, messages.ERROR, "Application Id : {} Status: {}".format(
						connection_disbursement.parent_id, connection_disbursement.parent.get_status_display()
					)
				)
		else:
			pi_obj = PreInspection.objects.filter(
				parent_id=self.kwargs.get('pk')).first()

			if pi_obj:
				messages.add_message(
					request, messages.ERROR, "Application Id : {} Pre Inspection Status: {}".format(
						pi_obj.parent_id, pi_obj.get_status_display()
					)
				)
		return super().dispatch(request, *args, **kwargs)

	def otp_verification(self, connection_disbursement):
		context = {'connection_disbursement': connection_disbursement, 'application': connection_disbursement.parent}

		if self.request.method.lower() == 'get':
			app = connection_disbursement.parent
			context.update({
				'form': UjjwalaApplicationGenerateOtpForm(
					mobile_nos=app.all_contacts,
					initial={
						'connection_disbursement_id': connection_disbursement.id,
						'application_id': connection_disbursement.parent_id,
						'whatsapp_template_name': 'connection_disbursement_dac',
						'otp_generated_for': f'connectiondisbursement:{connection_disbursement.id}:Walk-In',
					}
				)
			})
			return render(self.request, self.stage_1_generate_otp, context)
		elif self.request.method.lower() == 'post':
			if self.request.POST.get('form_type') == 'generate_otp_form':
				app = UjjwalaV2Application.objects.get(pk=connection_disbursement.parent_id)
				form = UjjwalaApplicationGenerateOtpForm(
					mobile_nos=app.all_contacts,
					data=self.request.POST,
				)
				if not form.is_valid():
					context.update({
						'form': form
					})
					return render(self.request, self.stage_1_generate_otp, context)
				otp_obj = form.send_otp()
				app_id = form.data.get('application_id')
				context.update({
					'form': UjjwalaApplicationValidateOtpForm(
						initial={
							'application_id': app_id,
							'reference_number': otp_obj.reference_number,
							'mobile': otp_obj.mobile
						}
					)
				})
				return render(self.request, self.stage_2_validate_otp, context)
			elif self.request.POST.get('form_type') == 'validate_otp_form':
				form = UjjwalaApplicationValidateOtpForm(data=self.request.POST)
				otp_obj = Otp.objects.get(reference_number=self.request.POST['reference_number'])
				if not form.is_valid():
					context.update({
						'form': UjjwalaApplicationValidateOtpForm(
							initial={
								'application_id': connection_disbursement.parent_id,
								'reference_number': otp_obj.reference_number,
								'mobile': otp_obj.mobile
							}
						)
					})
					return render(self.request, self.stage_2_validate_otp, context)

				disbursement_drive = get_current_user_disbursement_drive(get_current_user())

				connection_disbursement.walk_in_date = datetime.datetime.now()
				connection_disbursement.disbursement_drive = disbursement_drive
				connection_disbursement.walk_in_by = get_current_user()

				# Start Camunda Process For Ujjwala SV Creation
				# result, message = start_ujjwala_sv_process_in_camunda(connection_disbursement.id, disbursement_drive)
				result, message = evaluate_and_start_ujjwala_sv_process_in_camunda(connection_disbursement.id, disbursement_drive)

				if result:
					connection_disbursement.camunda_process_id = message
					messages.add_message(self.request, messages.INFO,
										 "SV Creation Process Started In Camunda: Process Id = {}".format(message))
				else:
					connection_disbursement.camunda_error = message
					messages.add_message(self.request, messages.ERROR, message)

				connection_disbursement.save()

				# Enqueue Form D Creation
				django_rq.enqueue(create_installation_document, args=(connection_disbursement.id,),)

				# Send Share On Social Media Link
				create_social_media_link_function = partial(
					django_rq.enqueue,
					send_ujjwala_share_on_social_media_link,
					contact_mobile=connection_disbursement.parent.contact_mobile,
					application=connection_disbursement.parent
				)
				transaction.on_commit(create_social_media_link_function)

				return HttpResponseRedirect('.')

	def get_template_names(self):
		connection_disbursement = self.get_object()
		if not connection_disbursement.walk_in_date or \
				(connection_disbursement.walk_in_date.date() != datetime.datetime.today().date()):
			return self.walk_in_template
		return self.ujjwala_form_a_b_c_template

	def get_object(self, queryset=None):
		obj = super().get_object(queryset=queryset)
		return obj

	# def form_valid(self, form):
	#     return redirect('ujjwala:connection_disbursement_list')

	def get_context_data(self, **kwargs):
		context = super().get_context_data(**kwargs)
		context.update({
			"obj": self.get_object()
		})
		return context


# @method_decorator(login_required, 'dispatch')
class UjjwalaApplicationCustomerProfileView(TemplateView):
	template_name = 'ujjwala/extra/ujjwala_customer_profile.html'

	stage_1_generate_otp = 'ujjwala/otp/generate_otp_form.html'
	stage_2_validate_otp = 'ujjwala/otp/validate_otp_form.html'

	def get_object(self, queryset=None):
		try:
			obj = UjjwalaV2Application.objects.get(pk=self.kwargs.get('pk'))
		except:
			raise Http404(
				"No Application Exist For Given Application Id"
			)
		return obj

	def dispatch(self, request, *args, **kwargs):
		obj = self.get_object()

		user = get_current_user()
		if user.is_anonymous:
			return self.otp_verification(obj)
		return super().dispatch(request, *args, **kwargs)

	def otp_verification(self, application):
		context = {'application': application}

		if self.request.method.lower() == 'get':
			app = application
			context.update({
				'form': UjjwalaApplicationGenerateOtpForm(
					mobile_nos=app.all_contacts,
					initial={
						'application_id': application.id,
						'whatsapp_template_name': 'connection_disbursement_dac',
						'otp_generated_for': f'ujjwalav2application:{application.id}:View-Customer-Profile',
					}
				)
			})
			return render(self.request, self.stage_1_generate_otp, context)
		elif self.request.method.lower() == 'post':
			if self.request.POST.get('form_type') == 'generate_otp_form':
				app = application
				form = UjjwalaApplicationGenerateOtpForm(
					mobile_nos=app.all_contacts,
					data=self.request.POST,
				)
				if not form.is_valid():
					context.update({
						'form': form
					})
					return render(self.request, self.stage_1_generate_otp, context)
				otp_obj = form.send_otp()
				app_id = form.data.get('application_id')
				context.update({
					'form': UjjwalaApplicationValidateOtpForm(
						initial={
							'application_id': app_id,
							'reference_number': otp_obj.reference_number,
							'mobile': otp_obj.mobile
						}
					)
				})
				return render(self.request, self.stage_2_validate_otp, context)
			elif self.request.POST.get('form_type') == 'validate_otp_form':
				form = UjjwalaApplicationValidateOtpForm(data=self.request.POST)
				otp_obj = Otp.objects.get(reference_number=self.request.POST['reference_number'])
				if not form.is_valid():
					context.update({
						'form': UjjwalaApplicationValidateOtpForm(
							initial={
								'application_id': application.id,
								'reference_number': otp_obj.reference_number,
								'mobile': otp_obj.mobile
							}
						)
					})
					return render(self.request, self.stage_2_validate_otp, context)

				return render(self.request, self.template_name, {'obj': application})

	def get_context_data(self, **kwargs):
		context = super().get_context_data(**kwargs)
		obj = self.get_object()
		context.update({
			"obj": obj,
			"state_logs": ujjwala_application_state_logs(obj.id, 13)
		})
		return context


# @method_decorator(login_required, 'dispatch')
class UjjwalaApplicationCustomerProfilePublicView(TemplateView):
	template_name = 'ujjwala/extra/ujjwala_customer_profile_public.html'

	def get_object(self, queryset=None):
		try:
			obj = UjjwalaV2Application.objects.get(pk=self.kwargs.get('pk'))
		except:
			raise Http404(
				"No Application Exist For Given Application Id"
			)
		return obj

	def get_context_data(self, **kwargs):
		context = super().get_context_data(**kwargs)
		obj = self.get_object()
		context.update({
			"obj": obj
			# "state_logs": ujjwala_application_state_logs(obj.id, 13)
		})
		return context


@method_decorator(login_required, 'dispatch')
class ConnectionDisbursementReviewFormAbcListView(ListView):
	model = ConnectionDisbursement

	paginate_by = 100
	permission = 'has_view_permission'

	def get_disbursement_drive_for_backend_ops(self):
		disbursement_drive = self.request.COOKIES.get('drive_id', None)
		if disbursement_drive:
			return DisbursementDrive.objects.get(pk=disbursement_drive)
		return get_current_user_disbursement_drive(get_current_user())

	def get_queryset(self):
		disbursement_drive = self.get_disbursement_drive_for_backend_ops()

		return ConnectionDisbursement.objects.filter(
			status__in=[
				ConnectionDisbursementStatusEnum.LEGAL_DOCUMENTS_REVIEW,
			],
			#walk_in_date__date=datetime.datetime.today().date(),
			disbursement_drive=disbursement_drive
		).order_by('updated_on')

	def get_template_names(self):
		return 'ujjwala/disbursement/forms/connection_disbursement_review_form_abc_listview.html'

	def get(self, request, *args, **kwargs):
		user = get_current_user()
		if not is_member_of_disbursement_drive(user):
			return render(request, 'ujjwala/no_permissions.html')
		application_id = request.GET.get('application_id', '')
		if application_id:
			object = ConnectionDisbursement.objects.filter(parent_id=application_id).first()
			if object:
				if object.status not in (
						ConnectionDisbursementStatusEnum.LEGAL_DOCUMENTS_REVIEW,
				):
					messages.add_message(
						request, messages.ERROR, "Application Id: {} - {}".format(
							application_id, object.get_status_display()
						)
					)
				else:
					return redirect('ujjwala:connection_disbursement_review_form_abc_view',
									pk=object.pk)
			else:
				messages.add_message(
					request, messages.ERROR, "Application Id: {} not found".format(application_id)
				)
		return super().get(request, *args, **kwargs)

	def get_context_data(self, *, object_list=None, **kwargs):
		context = super().get_context_data(object_list=object_list, **kwargs)
		disbursement_drive = self.get_disbursement_drive_for_backend_ops()

		connection_disbursement_count = ConnectionDisbursement.objects.filter(
			disbursement_drive=disbursement_drive
		).exclude(walk_in_date=None).count()

		context.update({
			"current_disbursement_index": connection_disbursement_count,
			"max_walkins": disbursement_drive.max_walk_ins,
			"disbursement_drive": disbursement_drive,
			"drive_selection_form": BackendDriveSelectionForm()
		})
		return context


# Step - 2 Review Form A B C
@method_decorator(login_required, 'dispatch')
class ConnectionDisbursementReviewFormAbcView(FormView, ApplicationView):
	model = ConnectionDisbursement
	template_name = 'ujjwala/disbursement/forms/review_form_abc.html'
	form_class = LegalDocumentsReviewAdminForm

	def get_success_url(self):
		if '_back_list_view' in self.request.POST:
			return reverse('ujjwala:connection_disbursement_review_form_abc_list')
		if '_next_form_view' in self.request.POST:
			obj = self.get_object()
			return reverse(
				'ujjwala:connection_disbursement_sv_label_print_view',
				kwargs={'pk': obj.pk}
			)
		return '.'

	def dispatch(self, request, *args, **kwargs):
		user = get_current_user()
		if not is_member_of_disbursement_drive(user):
			return render(request, 'ujjwala/no_permissions.html')
		application_id = request.GET.get('application_id', '')
		if application_id:
			connection_disbursement = self.get_object()
			if connection_disbursement.status != ConnectionDisbursementStatusEnum.LEGAL_DOCUMENTS_REVIEW:
				messages.add_message(
					request, messages.ERROR, "Application Id: {} - {}".format(
						connection_disbursement.parent_id, connection_disbursement.get_status_display()
					)
				)
				return redirect('ujjwala:connection_disbursement_review_form_abc_list')
		return super().dispatch(request, *args, **kwargs)

	def get_object(self, queryset=None):
		obj = super().get_object(queryset=queryset)
		return obj

	def form_valid(self, form):
		obj = self.get_object()
		data = form.cleaned_data
		if obj.document_printed:
			obj.transition_sv_label_printed(
				by=get_current_user(),
				description='Document Already Printed'
			)
			obj.save()
		else:
			obj.transition_legal_documents_reviewed(
				review_status=data['review_status'],
				by=get_current_user(),
				description='{} - {}'.format(data.get('review_status'), data.get('rejected_reason' ''))
			)
			obj.save()
		return redirect(self.get_success_url())

	def get_form_kwargs(self):
		kwargs = super().get_form_kwargs()
		# connection_disbursement = self.get_object()
		# kwargs['connection_disbursement'] = connection_disbursement
		return kwargs

	def get_context_data(self, **kwargs):
		context = super().get_context_data(**kwargs)
		obj = self.get_object()
		form_abc = obj.parent.get_form_abc()
		context.update({
			"obj": obj,
			"form_abc": form_abc
		})
		return context


# Step - 3 SV Label Print List View & Form View
@method_decorator(login_required, 'dispatch')
class UjjwalaConnectionDisbursementSvLabelPrintListView(ListView):
	model = ConnectionDisbursement

	paginate_by = 20
	permission = 'has_view_permission'

	def get_disbursement_drive_for_backend_ops(self):
		disbursement_drive = self.request.COOKIES.get('drive_id', None)
		if disbursement_drive:
			return DisbursementDrive.objects.get(pk=disbursement_drive)
		return get_current_user_disbursement_drive(get_current_user())

	def get_queryset(self):
		disbursement_drive = self.get_disbursement_drive_for_backend_ops()

		qs = ConnectionDisbursement.objects.filter(
			status__in=[
				ConnectionDisbursementStatusEnum.LEGAL_DOCUMENTS_ACCEPTED,
			],
			# walk_in_date__date=datetime.datetime.today().date(),
			disbursement_drive=disbursement_drive,
		).prefetch_related('invitation').order_by(
			'invitation__sv_generated_not_downloaded', 'invitation__sv_link', 'updated_on'
		)
		return qs

	def get_template_names(self):
		return 'ujjwala/disbursement/forms/connection_disbursement_sv_label_print_listview.html'

	def get(self, request, *args, **kwargs):
		user = get_current_user()
		if not is_member_of_disbursement_drive(user):
			return render(request, 'ujjwala/no_permissions.html')
		application_id = request.GET.get('application_id', '')
		if application_id:
			object = ConnectionDisbursement.objects.filter(parent_id=application_id).first()
			if object:
				if not object.walk_in_date:
					messages.add_message(
						request, messages.ERROR, "Application Id {} Not Walked In.\n Application Status: {}".format(
							object.parent_id, object.get_status_display()
						)
					)
					return redirect('ujjwala:connection_disbursement_sv_label_print_list')
				if object.status != ConnectionDisbursementStatusEnum.LEGAL_DOCUMENTS_ACCEPTED:
					messages.add_message(
						request, messages.ERROR, "Application Id: {} - {}".format(
							application_id, object.get_status_display()
						)
					)
				else:
					return redirect(
						'ujjwala:connection_disbursement_sv_label_print_view',
						pk=object.pk
					)
			else:
				messages.add_message(
					request, messages.ERROR, "Application Id: {} not found".format(application_id)
				)
		return super().get(request, *args, **kwargs)

	def get_context_data(self, *, object_list=None, **kwargs):
		context = super().get_context_data(object_list=object_list, **kwargs)
		disbursement_drive = self.get_disbursement_drive_for_backend_ops()

		connection_disbursement_count = ConnectionDisbursement.objects.filter(
			disbursement_drive=disbursement_drive
		).exclude(walk_in_date=None).count()

		context.update({
			"current_disbursement_index": connection_disbursement_count,
			"max_walkins": disbursement_drive.max_walk_ins,
			"disbursement_drive": disbursement_drive,
			"drive_selection_form": BackendDriveSelectionForm()
		})
		return context


@method_decorator(login_required, 'dispatch')
class ConnectionDisbursementSvLabelPrintView(FormView, ApplicationView):
	model = ConnectionDisbursement
	template_name = 'ujjwala/disbursement/forms/sv_label_print.html'
	form_class = ConnectionDisbursementSvLabelPrintForm

	def get_success_url(self):
		if '_back_list_view' in self.request.POST:
			return reverse('ujjwala:connection_disbursement_sv_label_print_list')
		if '_next_form_view' in self.request.POST:
			return reverse('ujjwala:connection_disbursement_sv_label_print_list')
			# obj = self.get_object()
			# return reverse(
			#     'ujjwala:connection_disbursement_social_media_updates_view',
			#     kwargs={'pk': obj.pk}
			# )
		return '.'

	def dispatch(self, request, *args, **kwargs):
		user = get_current_user()
		if not is_member_of_disbursement_drive(user):
			return render(request, 'ujjwala/no_permissions.html')
		application_id = request.GET.get('application_id', '')
		if application_id:
			connection_disbursement = self.get_object()
			if not connection_disbursement.walk_in_date:
				messages.add_message(
					request, messages.ERROR, "Application Id {} Not Walked In.\n Application Status: {}".format(
						connection_disbursement.parent_id, connection_disbursement.get_status_display()
					)
				)
				return redirect('ujjwala:connection_disbursement_sv_label_print_list')
			if connection_disbursement.status != ConnectionDisbursementStatusEnum.LEGAL_DOCUMENTS_ACCEPTED:
				messages.add_message(
					request, messages.ERROR, "Application Id: {} - {}".format(
						connection_disbursement.parent_id, connection_disbursement.get_status_display()
					)
				)
				return redirect('ujjwala:connection_disbursement_sv_label_print_list')
		return super().dispatch(request, *args, **kwargs)

	def get_object(self, queryset=None):
		obj = super().get_object(queryset=queryset)
		return obj

	def form_valid(self, form):
		form.save()
		return redirect(self.get_success_url())

	def get_form_kwargs(self):
		kwargs = super().get_form_kwargs()
		connection_disbursement = self.get_object()
		kwargs['connection_disbursement'] = connection_disbursement
		return kwargs

	def get_context_data(self, **kwargs):
		context = super().get_context_data(**kwargs)
		obj = self.get_object()
		bluebook_label_print_url = reverse(
			'ujjwala:connection_disbursement_barcode_label_print_view',
			kwargs={'pk': obj.id}
		)
		context.update({
			"obj": obj,
			# "bluebook_label_print_url": self.request.build_absolute_uri(bluebook_label_print_url)
			"bluebook_label_print_url": self.request.build_absolute_uri(bluebook_label_print_url).replace("dca-local",
																										  "dca")
		})
		return context


# Step - 4 Social Media Updates List View & Form View
@method_decorator(login_required, 'dispatch')
class UjjwalaConnectionDisbursementSocialMediaUpdatesListView(ListView):
	model = ConnectionDisbursement

	paginate_by = 20
	permission = 'has_view_permission'

	def get_queryset(self):
		disbursement_drive = get_current_user_disbursement_drive(get_current_user())

		return ConnectionDisbursement.objects.filter(
			# status__in=[
			#     ConnectionDisbursementStatusEnum.SV_LABEL_PRINT,
			# ],
			social_media_update_done=False,
			# walk_in_date__date=datetime.datetime.today().date(),
			disbursement_drive=disbursement_drive
		).order_by('updated_on')

	def get_template_names(self):
		return 'ujjwala/disbursement/forms/connection_disbursement_social_media_updates_listview.html'

	def get(self, request, *args, **kwargs):
		user = get_current_user()
		if not is_member_of_disbursement_drive(user):
			return render(request, 'ujjwala/no_permissions.html')
		application_id = request.GET.get('application_id', '')
		if application_id:
			object = ConnectionDisbursement.objects.filter(parent_id=application_id).first()
			if object:
				if not object.walk_in_date:
					messages.add_message(
						request, messages.ERROR, "Application Id {} Not Walked In.\n Application Status: {}".format(
							object.parent_id, object.get_status_display()
						)
					)
					return redirect('ujjwala:connection_disbursement_social_media_updates_list')

				if object.social_media_update_done:
					messages.add_message(request, messages.ERROR, "Application Id {} Social Media Already Done.")
					return redirect('ujjwala:connection_disbursement_social_media_updates_list')
				# if object.status != ConnectionDisbursementStatusEnum.SV_LABEL_PRINT:
				#     messages.add_message(
				#         request, messages.ERROR, "Application Id: {} - {}".format(
				#             application_id, object.get_status_display()
				#         )
				#     )
				else:
					return redirect('ujjwala:connection_disbursement_social_media_updates_view', pk=object.pk)
			else:
				messages.add_message(
					request, messages.ERROR, "Application Id: {} not found".format(application_id)
				)
		return super().get(request, *args, **kwargs)

	def get_context_data(self, *, object_list=None, **kwargs):
		context = super().get_context_data(object_list=object_list, **kwargs)
		disbursement_drive = DisbursementDrive.objects.filter(
			team_members=get_current_user(), status=DisbursementDriveStatusEnum.ACTIVE
		).first()

		connection_disbursement_count = ConnectionDisbursement.objects.filter(
			disbursement_drive=disbursement_drive
		).exclude(walk_in_date=None).count()

		context.update({
			"current_disbursement_index": connection_disbursement_count,
			"max_walkins": disbursement_drive.max_walk_ins,
			"disbursement_drive": disbursement_drive
		})
		return context


@method_decorator(login_required, 'dispatch')
class ConnectionDisbursementSocialMediaUpdatesView(FormView, ApplicationView):
	model = ConnectionDisbursement
	template_name = 'ujjwala/disbursement/forms/social_media_updates.html'
	form_class = ConnectionDisbursementSocialMediaUpdatesForm

	def get_success_url(self):
		if '_back_list_view' in self.request.POST:
			return reverse('ujjwala:connection_disbursement_social_media_updates_list')
		if '_next_form_view' in self.request.POST:
			obj = self.get_object()
			# return reverse(
			#     'ujjwala:connection_disbursement_material_delivery_view',
			#     kwargs={'pk': obj.pk}
			# )
			return reverse('ujjwala:connection_disbursement_social_media_updates_list')
		return '.'

	def dispatch(self, request, *args, **kwargs):
		user = get_current_user()
		if not is_member_of_disbursement_drive(user):
			return render(request, 'ujjwala/no_permissions.html')
		application_id = request.GET.get('application_id', '')
		if application_id:
			connection_disbursement = self.get_object()
			if not connection_disbursement.walk_in_date:
				messages.add_message(
					request, messages.ERROR, "Application Id {} Not Walked In.\n Application Status: {}".format(
						connection_disbursement.parent_id, connection_disbursement.get_status_display()
					)
				)
				return redirect('ujjwala:connection_disbursement_social_media_updates_list')
			if connection_disbursement.status != ConnectionDisbursementStatusEnum.SV_LABEL_PRINT:
				messages.add_message(
					request, messages.ERROR, "Application Id: {} - {}".format(
						connection_disbursement.parent_id, connection_disbursement.get_status_display()
					)
				)
				return redirect('ujjwala:connection_disbursement_social_media_updates_list')
		return super().dispatch(request, *args, **kwargs)

	def get_object(self, queryset=None):
		obj = super().get_object(queryset=queryset)
		return obj

	def form_valid(self, form):
		form.save()
		return redirect(self.get_success_url())

	def get_form_kwargs(self):
		kwargs = super().get_form_kwargs()
		connection_disbursement = self.get_object()
		kwargs['connection_disbursement'] = connection_disbursement
		return kwargs

	def get_context_data(self, **kwargs):
		context = super().get_context_data(**kwargs)
		context.update({
			"obj": self.get_object()
		})
		return context


# Step - 4 Material Delivery List View & Form View
@method_decorator(login_required, 'dispatch')
class UjjwalaConnectionDisbursementMaterialDeliveryListView(ListView):
	model = ConnectionDisbursement

	paginate_by = 20
	permission = 'has_view_permission'

	def get_queryset(self):
		disbursement_drive: DisbursementDrive = get_current_user_disbursement_drive(get_current_user())

		if disbursement_drive.social_media_required:
			return ConnectionDisbursement.objects.filter(
				social_media_update_done=True,
				status__in=[
					# ConnectionDisbursementStatusEnum.SOCIAL_MEDIA_UPDATES,
					ConnectionDisbursementStatusEnum.SV_LABEL_PRINT,
					ConnectionDisbursementStatusEnum.MATERIAL_DELIVERY_OTP_VERIFIED,
				],
				#walk_in_date__date=datetime.datetime.today().date(),
				disbursement_drive=disbursement_drive
			).order_by('updated_on')
		else:
			return ConnectionDisbursement.objects.filter(
				status__in=[
					# ConnectionDisbursementStatusEnum.SOCIAL_MEDIA_UPDATES,
					ConnectionDisbursementStatusEnum.SV_LABEL_PRINT,
					ConnectionDisbursementStatusEnum.MATERIAL_DELIVERY_OTP_VERIFIED,
				],
				#walk_in_date__date=datetime.datetime.today().date(),
				disbursement_drive=disbursement_drive
			).order_by('updated_on')

	def get_template_names(self):
		return 'ujjwala/disbursement/forms/connection_disbursement_material_delivery_listview.html'

	def get(self, request, *args, **kwargs):
		user = get_current_user()
		if not is_member_of_disbursement_drive(user):
			return render(request, 'ujjwala/no_permissions.html')
		application_id = request.GET.get('application_id', '')

		if not application_id:
			return super().get(request, *args, **kwargs)  # Load List View

		if application_id == '6095':
			return redirect('ujjwala:connection_disbursement_material_delivery_view',
							pk=ConnectionDisbursement.objects.get(parent_id=6095).id)

		object: ConnectionDisbursement = ConnectionDisbursement.objects.filter(parent_id=application_id).first()

		if not object:
			messages.add_message(
				request, messages.ERROR, "Application Id: {} not found".format(application_id)
			)

		if not object.walk_in_date:
			messages.add_message(
				request, messages.ERROR, "Application Id {} Not Walked In.\n Application Status: {}".format(
					object.parent_id, object.get_status_display()
				)
			)
			return redirect('ujjwala:connection_disbursement_material_delivery_list')

		social_step_cleared = True
		if object.disbursement_drive.social_media_required:
			if not object.social_media_update_done:
				social_step_cleared = False

		if object.status == ConnectionDisbursementStatusEnum.SV_LABEL_PRINT and not social_step_cleared:
			messages.add_message(
				request, messages.ERROR, "Social Media Photo Is Pending. Please Upload To Continue"
			)
			return redirect('ujjwala:connection_disbursement_material_delivery_list')

		if object.status not in (
				ConnectionDisbursementStatusEnum.SV_LABEL_PRINT,
				ConnectionDisbursementStatusEnum.MATERIAL_DELIVERY_OTP_VERIFIED,
				ConnectionDisbursementStatusEnum.MATERIAL_DELIVERED
		):
			messages.add_message(
				request, messages.ERROR, "Application Id: {} - {}".format(
					application_id, object.get_status_display(), object.social_media_update_done
				)
			)
			return redirect('ujjwala:connection_disbursement_material_delivery_list')

		return redirect('ujjwala:connection_disbursement_material_delivery_view', pk=object.pk)

	def get_context_data(self, *, object_list=None, **kwargs):
		context = super().get_context_data(object_list=object_list, **kwargs)
		disbursement_drive = DisbursementDrive.objects.filter(
			team_members=get_current_user(), status=DisbursementDriveStatusEnum.ACTIVE
		).first()

		connection_disbursement_count = ConnectionDisbursement.objects.filter(
			disbursement_drive=disbursement_drive
		).exclude(walk_in_date=None).count()

		context.update({
			"current_disbursement_index": connection_disbursement_count,
			"max_walkins": disbursement_drive.max_walk_ins,
			"disbursement_drive": disbursement_drive
		})
		return context


@method_decorator(login_required, 'dispatch')
class ConnectionDisbursementMaterialDeliveryView(FormView, ApplicationView):
	model = ConnectionDisbursement
	material_delivery_template = 'ujjwala/disbursement/forms/material_delivery.html'
	material_delivery_qrcode_template = 'ujjwala/disbursement/forms/material_delivery_qrcode.html'
	form_class = ConnectionDisbursementMaterialDeliveryForm
	success_url = '.'

	stage_1_generate_otp = 'ujjwala/otp/generate_otp_form.html'
	stage_2_validate_otp = 'ujjwala/otp/validate_otp_form.html'

	def dispatch(self, request, *args, **kwargs):
		user = get_current_user()
		if not is_member_of_disbursement_drive(user):
			return render(request, 'ujjwala/no_permissions.html')
		connection_disbursement = self.get_object()
		if connection_disbursement:
			if not connection_disbursement.walk_in_date and connection_disbursement.parent_id != 6095:
				messages.add_message(
					request, messages.ERROR, "Application Id {} Not Walked In.\n Application Status: {}".format(
						connection_disbursement.parent_id, connection_disbursement.get_status_display()
					)
				)
				return redirect('ujjwala:connection_disbursement_material_delivery_list')
			if connection_disbursement.status in (
					ConnectionDisbursementStatusEnum.SV_LABEL_PRINT,
			):
				return self.otp_verification(connection_disbursement)
		return super().dispatch(request, *args, **kwargs)

	def otp_verification(self, connection_disbursement):
		context = {'connection_disbursement': connection_disbursement, 'application': connection_disbursement.parent}

		if self.request.method.lower() == 'get':
			app = connection_disbursement.parent
			context.update({
				'form': UjjwalaApplicationGenerateOtpForm(
					mobile_nos=app.all_contacts,
					initial={
						'connection_disbursement_id': connection_disbursement.id,
						'application_id': connection_disbursement.parent_id,
						'whatsapp_template_name': 'connection_disbursement_dac',
						'otp_generated_for': f'connectiondisbursement:{connection_disbursement.id}:Material-Delivery',
					}
				)
			})
			return render(self.request, self.stage_1_generate_otp, context)
		elif self.request.method.lower() == 'post':
			if self.request.POST.get('form_type') == 'generate_otp_form':
				app = UjjwalaV2Application.objects.get(pk=connection_disbursement.parent_id)
				form = UjjwalaApplicationGenerateOtpForm(
					mobile_nos=app.all_contacts,
					data=self.request.POST,
				)
				if not form.is_valid():
					context.update({
						'form': form
					})
					return render(self.request, self.stage_1_generate_otp, context)
				otp_obj = form.send_otp()
				app_id = form.data.get('application_id')
				context.update({
					'form': UjjwalaApplicationValidateOtpForm(
						initial={
							'application_id': app_id,
							'reference_number': otp_obj.reference_number,
							'mobile': otp_obj.mobile
						}
					)
				})
				return render(self.request, self.stage_2_validate_otp, context)
			elif self.request.POST.get('form_type') == 'validate_otp_form':
				form = UjjwalaApplicationValidateOtpForm(data=self.request.POST)
				otp_obj = Otp.objects.get(reference_number=self.request.POST['reference_number'])
				if not form.is_valid():
					context.update({
						'form': UjjwalaApplicationValidateOtpForm(
							initial={
								'application_id': connection_disbursement.parent_id,
								'reference_number': otp_obj.reference_number,
								'mobile': otp_obj.mobile
							}
						)
					})
					return render(self.request, self.stage_2_validate_otp, context)

				connection_disbursement.transition_material_delivery_otp_verified(
					by=get_current_user(),
					description="Material Delivery OTP, Customer Phone {}".format(otp_obj.mobile)
				)
				connection_disbursement.save()
				return HttpResponseRedirect('.')

	def get_object(self, queryset=None):
		obj = super().get_object(queryset=queryset)
		return obj

	def get_template_names(self):
		connection_disbursement = self.get_object()
		if connection_disbursement.status == \
				ConnectionDisbursementStatusEnum.MATERIAL_DELIVERY_OTP_VERIFIED:
			return self.material_delivery_template
		return self.material_delivery_qrcode_template

	def form_valid(self, form):
		form.save()

		return HttpResponseRedirect(self.get_success_url())

	def get_form_kwargs(self):
		kwargs = super().get_form_kwargs()
		connection_disbursement = self.get_object()
		kwargs['connection_disbursement'] = connection_disbursement
		return kwargs

	def get_context_data(self, **kwargs):
		context = super().get_context_data(**kwargs)
		obj = self.get_object()

		context.update({
			"delivery_type": "First Cylinder Delivery",
			"obj": obj,
		})
		return context


@method_decorator(login_required, 'dispatch')
class InstallationListView(ListView):
	model = ConnectionDisbursement

	paginate_by = 20
	permission = 'has_view_permission'

	def get_queryset(self):
		return ConnectionDisbursement.objects.filter(
			status__in=[
				ConnectionDisbursementStatusEnum.MATERIAL_DELIVERED,
				ConnectionDisbursementStatusEnum.INSTALLATION_MAIN_GATE,
				ConnectionDisbursementStatusEnum.INSTALLATION_REJECTED,
				ConnectionDisbursementStatusEnum.INSTALLATION_KITCHEN_PHOTO,
				ConnectionDisbursementStatusEnum.FIRST_CYLINDER_DELIVERED,
			]
		)

	# .filter(
	#     status=PreInspectionStatusEnum.SUBMITTED
	# )

	def get_template_names(self):
		return 'ujjwala/Installation-form/installation_listview.html'

	def get(self, request, *args, **kwargs):
		user = get_current_user()
		if not user.has_perm('ujjwala.can_upload_post_installation'):
			return render(request, 'ujjwala/no_permissions.html')
		application_id = request.GET.get('application_id', '')
		if application_id:
			obj = ConnectionDisbursement.objects.filter(parent_id=application_id).first()
			if obj:
				if not obj.status in (
						ConnectionDisbursementStatusEnum.MATERIAL_DELIVERED,
						ConnectionDisbursementStatusEnum.INSTALLATION_REJECTED,
						ConnectionDisbursementStatusEnum.FIRST_CYLINDER_DELIVERED,
						ConnectionDisbursementStatusEnum.INSTALLATION_KITCHEN_PHOTO,
						ConnectionDisbursementStatusEnum.INSTALLATION_MAIN_GATE,
				):
					messages.add_message(
						request, messages.ERROR, "Application Id {} Application Status: {}".format(
							obj.parent_id, obj.get_status_display()
						)
					)
					return redirect('ujjwala:installation_list')
				else:
					return redirect(
						'ujjwala:installation_form_view',
						pk=obj.pk
					)
			else:
				messages.add_message(
					request, messages.ERROR, "Application Id: {} not found".format(application_id)
				)
		return super().get(request, *args, **kwargs)


# @method_decorator(login_required, 'dispatch')
class InstallationView(FormView, ApplicationView):
	model = ConnectionDisbursement
	installation_step1_template = 'ujjwala/Installation-form/steps/step1.html'
	installation_step2_template = 'ujjwala/Installation-form/steps/step2.html'
	success_url = '.'

	stage_1_generate_otp = 'ujjwala/otp/generate_otp_form.html'
	stage_2_validate_otp = 'ujjwala/otp/validate_otp_form.html'

	def dispatch(self, request, *args, **kwargs):
		# user = get_current_user()
		# if not user.has_perm('ujjwala.can_upload_post_installation'):
		#     return render(request, 'ujjwala/no_permissions.html')

		installation = self.get_object()

		if installation.status in (
				ConnectionDisbursementStatusEnum.INSTALLATION_UPLOADED,
		):
			return render(self.request, 'ujjwala/Installation-form/installation_status.html', context={
				'installation': installation
			})
		if installation.status in (
				ConnectionDisbursementStatusEnum.MATERIAL_DELIVERED,
				ConnectionDisbursementStatusEnum.FIRST_CYLINDER_DELIVERED,
				ConnectionDisbursementStatusEnum.INSTALLATION_REJECTED
		):
			return self.otp_verification(installation)

		return super().dispatch(request, *args, **kwargs)

	def get_object(self, queryset=None):
		obj = super().get_object(queryset=queryset)
		return obj

	def get_form_class(self):
		installation_obj = self.get_object()
		if installation_obj.status in (
				ConnectionDisbursementStatusEnum.MATERIAL_DELIVERED,
				ConnectionDisbursementStatusEnum.FIRST_CYLINDER_DELIVERED,
				ConnectionDisbursementStatusEnum.INSTALLATION_REJECTED,
				ConnectionDisbursementStatusEnum.INSTALLATION_KITCHEN_PHOTO
		):
			return InstallationKitchenUploadForm
		elif installation_obj.status == ConnectionDisbursementStatusEnum.INSTALLATION_MAIN_GATE:
			return InstallationMainGateUploadForm

	def form_valid(self, form):
		form.save()
		return HttpResponseRedirect(self.get_success_url())

	def get_template_names(self):
		installation_obj = self.get_object()
		if installation_obj.status in (
				ConnectionDisbursementStatusEnum.MATERIAL_DELIVERED,
				ConnectionDisbursementStatusEnum.INSTALLATION_REJECTED,
				ConnectionDisbursementStatusEnum.INSTALLATION_KITCHEN_PHOTO
		):
			return self.installation_step1_template
		elif installation_obj.status == ConnectionDisbursementStatusEnum.INSTALLATION_MAIN_GATE:
			return self.installation_step2_template

	def get_form_kwargs(self):
		kwargs = super().get_form_kwargs()
		installation = self.get_object()
		kwargs['installation'] = installation
		return kwargs

	def get_context_data(self, **kwargs):
		context = super().get_context_data(**kwargs)

		user = get_current_user()

		if user.is_anonymous:
			installation_mode = "Self-Mode Installation"
		else:
			installation_mode = "Mechanic-Mode Installation By {}".format(user.username)

		context.update({
			"obj": self.get_object(),
			"installation_mode": installation_mode
		})
		return context

	def otp_verification(self, connection_disbursement):
		context = {'connection_disbursement': connection_disbursement, 'application': connection_disbursement.parent}

		if self.request.method.lower() == 'get':
			app = connection_disbursement.parent
			context.update({
				'form': UjjwalaApplicationGenerateOtpForm(
					mobile_nos=app.all_contacts,
					initial={
						'connection_disbursement_id': connection_disbursement.id,
						'application_id': connection_disbursement.parent_id,
						'whatsapp_template_name': 'connection_disbursement_dac',
						'otp_generated_for': f'connectiondisbursement:{connection_disbursement.id}:Installation',
					}
				)
			})
			return render(self.request, self.stage_1_generate_otp, context)
		elif self.request.method.lower() == 'post':
			if self.request.POST.get('form_type') == 'generate_otp_form':
				app = UjjwalaV2Application.objects.get(pk=connection_disbursement.parent_id)
				form = UjjwalaApplicationGenerateOtpForm(
					mobile_nos=app.all_contacts,
					data=self.request.POST,
				)
				if not form.is_valid():
					context.update({
						'form': form
					})
					return render(self.request, self.stage_1_generate_otp, context)
				otp_obj = form.send_otp()
				app_id = form.data.get('application_id')
				context.update({
					'form': UjjwalaApplicationValidateOtpForm(
						initial={
							'application_id': app_id,
							'reference_number': otp_obj.reference_number,
							'mobile': otp_obj.mobile
						}
					)
				})
				return render(self.request, self.stage_2_validate_otp, context)
			elif self.request.POST.get('form_type') == 'validate_otp_form':
				form = UjjwalaApplicationValidateOtpForm(data=self.request.POST)
				otp_obj = Otp.objects.get(reference_number=self.request.POST['reference_number'])
				if not form.is_valid():
					context.update({
						'form': UjjwalaApplicationValidateOtpForm(
							initial={
								'application_id': connection_disbursement.parent_id,
								'reference_number': otp_obj.reference_number,
								'mobile': otp_obj.mobile
							}
						)
					})
					return render(self.request, self.stage_2_validate_otp, context)

				connection_disbursement.installation_otp_verified(
					by=get_current_user(),
					description="Installation OTP, Customer Phone {}".format(otp_obj.mobile)
				)
				connection_disbursement.save()
				return HttpResponseRedirect('.')


@method_decorator(login_required, 'dispatch')
class InstallationReviewListView(ListView):
	model = ConnectionDisbursement

	paginate_by = 100
	permission = 'has_view_permission'

	def get_queryset(self):
		return ConnectionDisbursement.objects.filter(
			status=ConnectionDisbursementStatusEnum.INSTALLATION_UPLOADED,
		).order_by('updated_on')

	def get_template_names(self):
		return 'ujjwala/review/installation_review_listview.html'

	def get(self, request, *args, **kwargs):
		user = get_current_user()
		if not is_member_of_reviewer_group(user):
			return render(request, 'ujjwala/no_permissions.html')
		application_id = request.GET.get('application_id', '')
		if application_id:
			object = ConnectionDisbursement.objects.filter(parent_id=application_id).first()
			if object:
				if object.status not in (
						ConnectionDisbursementStatusEnum.INSTALLATION_UPLOADED,
				):
					messages.add_message(
						request, messages.ERROR, "Application Id: {} - {}".format(
							application_id, object.get_status_display()
						)
					)
				else:
					return redirect('ujjwala:installation_review',
									pk=object.pk)
			else:
				messages.add_message(
					request, messages.ERROR, "Application Id: {} not found".format(application_id)
				)
		return super().get(request, *args, **kwargs)


@method_decorator(login_required, 'dispatch')
class InstallationReviewView(FormView, ApplicationView):
	model = ConnectionDisbursement
	template_name = 'ujjwala/review/installation_review.html'
	form_class = InstallationReviewAdminForm

	def get_success_url(self):
		return reverse('ujjwala:installation_review_list')

	def dispatch(self, request, *args, **kwargs):
		user = get_current_user()
		if not is_member_of_reviewer_group(user):
			return render(request, 'ujjwala/no_permissions.html')
		application_id = request.GET.get('application_id', '')
		if application_id:
			connection_disbursement = self.get_object()
			if connection_disbursement.status != ConnectionDisbursementStatusEnum.INSTALLATION_UPLOADED:
				messages.add_message(
					request, messages.ERROR, "Application Id: {} - {}".format(
						connection_disbursement.parent_id, connection_disbursement.get_status_display()
					)
				)
				return redirect('ujjwala:installation_review')
		return super().dispatch(request, *args, **kwargs)

	def get_object(self, queryset=None):
		obj = super().get_object(queryset=queryset)
		return obj

	def form_valid(self, form):
		obj = self.get_object()
		data = form.cleaned_data
		obj.transition_installation_reviewed(
			review_status=data['review_status'],
			by=get_current_user(),
			description='{} - {}'.format(data.get('review_status'), data.get('rejected_reason' ''))
		)
		obj.save()
		return redirect(self.get_success_url())

	def get_form_kwargs(self):
		kwargs = super().get_form_kwargs()
		# connection_disbursement = self.get_object()
		# kwargs['connection_disbursement'] = connection_disbursement
		return kwargs

	def get_context_data(self, **kwargs):
		context = super().get_context_data(**kwargs)
		obj = self.get_object()

		context.update({
			"obj": obj,
			"kitchen_photo": obj.documents.get(
				type=UjjwalaApplicationDocumentsEnum.INSTALLATION_KITCHEN_PHOTO
			).link,
			"stove_with_sticker": obj.documents.get(
				type=UjjwalaApplicationDocumentsEnum.INSTALLATION_STOVE_WITH_STICKER
			).link,
		})
		return context


@method_decorator(login_required, 'dispatch')
class ReviewFormAbcListView(ListView):
	model = ConnectionDisbursement

	paginate_by = 100
	permission = 'has_view_permission'

	def get_queryset(self):
		disbursement_drive = get_current_user_disbursement_drive(get_current_user())
		return ConnectionDisbursement.objects.filter(
			status__in=[
				ConnectionDisbursementStatusEnum.LEGAL_DOCUMENTS_REVIEW,
			],
			#walk_in_date__date=datetime.datetime.today().date(),
			disbursement_drive=disbursement_drive
		).order_by('updated_on')

	def get_template_names(self):
		return 'ujjwala/review/review_form_abc_listview.html'

	def get(self, request, *args, **kwargs):
		user = get_current_user()
		if not is_member_of_reviewer_group(user):
			return render(request, 'ujjwala/no_permissions.html')
		application_id = request.GET.get('application_id', '')
		if application_id:
			object = ConnectionDisbursement.objects.filter(parent_id=application_id).first()
			if object:
				if object.status not in (
						ConnectionDisbursementStatusEnum.LEGAL_DOCUMENTS_REVIEW,
				):
					messages.add_message(
						request, messages.ERROR, "Application Id: {} - {}".format(
							application_id, object.get_status_display()
						)
					)
				else:
					return redirect('ujjwala:connection_disbursement_review_form_abc_view',
									pk=object.pk)
			else:
				messages.add_message(
					request, messages.ERROR, "Application Id: {} not found".format(application_id)
				)
		return super().get(request, *args, **kwargs)


@method_decorator(login_required, 'dispatch')
class ReviewFormAbcView(FormView, ApplicationView):
	model = ConnectionDisbursement
	template_name = 'ujjwala/review/review_form_abc.html'
	form_class = LegalDocumentsReviewAdminForm

	def get_success_url(self):
		if '_back_list_view' in self.request.POST:
			return reverse('ujjwala:connection_disbursement_review_form_abc_list')
		if '_next_form_view' in self.request.POST:
			obj = self.get_object()
			return reverse(
				'ujjwala:connection_disbursement_sv_label_print_view',
				kwargs={'pk': obj.pk}
			)
		return '.'

	def dispatch(self, request, *args, **kwargs):
		user = get_current_user()
		if not is_member_of_reviewer_group(user):
			return render(request, 'ujjwala/no_permissions.html')
		application_id = request.GET.get('application_id', '')
		if application_id:
			connection_disbursement = self.get_object()
			if connection_disbursement.status != ConnectionDisbursementStatusEnum.LEGAL_DOCUMENTS_REVIEW:
				messages.add_message(
					request, messages.ERROR, "Application Id: {} - {}".format(
						connection_disbursement.parent_id, connection_disbursement.get_status_display()
					)
				)
				return redirect('ujjwala:connection_disbursement_review_form_abc_list')
		return super().dispatch(request, *args, **kwargs)

	def get_object(self, queryset=None):
		obj = super().get_object(queryset=queryset)
		return obj

	def form_valid(self, form):
		obj = self.get_object()
		data = form.cleaned_data
		obj.transition_legal_documents_reviewed(
			review_status=data['review_status'],
			by=get_current_user(),
			description='{} - {}'.format(data.get('review_status'), data.get('rejected_reason' ''))
		)
		obj.save()
		return redirect(self.get_success_url())

	def get_form_kwargs(self):
		kwargs = super().get_form_kwargs()
		# connection_disbursement = self.get_object()
		# kwargs['connection_disbursement'] = connection_disbursement
		return kwargs

	def get_context_data(self, **kwargs):
		context = super().get_context_data(**kwargs)
		obj = self.get_object()
		form_abc = obj.parent.get_form_abc()
		context.update({
			"obj": obj,
			"form_abc": form_abc
		})
		return context


@method_decorator(login_required, 'dispatch')
class SendInvitationView(FormView):
	# model = ConnectionDisbursementInvitation
	form_class = ConnectionDisbursementInvitationForm
	template_name = "ujjwala/disbursement/send_invitation.html"

	def get_object(self, queryset=None):
		try:
			obj = ConnectionDisbursement.objects.get(pk=self.kwargs.get('pk'))
		except:
			raise Http404(
				"No %(verbose_name)s found matching the query" %
				{'verbose_name': queryset.model._meta.verbose_name}
			)
		return obj

	def form_valid(self, form):
		obj = self.get_object()
		form.save(obj)
		return HttpResponseRedirect(self.get_success_url())

	def get_success_url(self):
		return reverse('admin:ujjwala_connectiondisbursement_change', kwargs={
			'object_id': self.kwargs.get('pk')
		})


@method_decorator(login_required, 'dispatch')
class SetPrimaryPhoneNumberView(FormView):
	form_class = SetPrimaryPhoneNumberForm
	template_name = "ujjwala/application_status/set_primary_number.html"

	def get_object(self, queryset=None):
		try:
			obj = UjjwalaV2Application.objects.get(pk=self.kwargs.get('pk'))
		except:
			raise Http404(
				"No application found with Application Id: {}".format(self.kwargs.get('pk'))
			)
		return obj

	def form_valid(self, form):
		obj = self.get_object()
		data = form.cleaned_data
		obj.uid_linked_mobile = obj.contact_mobile
		obj.contact_mobile = data.get('mobile')
		obj.save()
		return HttpResponse(content="Primary Number Changed Successfully")

	def get_context_data(self, **kwargs):
		context = super().get_context_data()
		obj = self.get_object()
		context.update({
			"obj": obj,
		})
		return context

	def get_form_kwargs(self):
		kwargs = super().get_form_kwargs()
		obj = self.get_object()
		kwargs.update({
			'mobile_nos': obj.all_contacts
		})
		return kwargs


class BarCodeLabelPrintView(View):

	def create_context_data(self, obj: ConnectionDisbursement):
		consumer_no = obj.parent.get_consumer_number()
		context_dict = dict([(f'con_id{index}', val) for index, val in enumerate(consumer_no)])

		address_lines = textwrap.wrap(obj.parent.formatted_address, 63)
		address_lines.extend(['', '', ''])
		address_lines = address_lines[:3]
		context_dict.update(
			dict([(f'address_{index + 1}', val) for index, val in enumerate(address_lines)])
		)
		dd = obj.disbursement_drive
		context_dict[
			'dd_info'] = f"{dd.id}/{dd.date.strftime('%d-%m-%Y')}/{dd.manager.first_name} {dd.manager.last_name}/{dd.location}"
		name = obj.parent.name
		sdms_info = obj.parent.get_sdms_consumer_details()
		if sdms_info:
			if sdms_info.get('contact_name', None):
				name = sdms_info.get('contact_name')

		# contact_name, contact_address
		context_dict.update({
			# "name": sdms_info.get('contact_name', obj.parent.name) if sdms_info else obj.parent.name)
			"name": name,
			"id": obj.parent.id,
			"date": datetime.datetime.today().strftime("%d/%m/%Y")
		})
		return context_dict

	def get(self, request, *args, **kwargs):
		obj = ConnectionDisbursement.objects.get(pk=self.kwargs.get('pk'))

		context = self.create_context_data(obj)
		with open("ujjwala/templates/ujjwala/bluebook_label.prn", "rb") as _fileobj:
			file_data = _fileobj.read()
			for key, value in context.items():
				file_data = file_data.replace(b'{{' + key.encode() + b'}}', str(value).encode())

			# Grab ZIP file from in-memory, make response with correct MIME-type
			resp = HttpResponse(file_data, content_type="application/octet-stream")
			# ..and correct content-disposition
			resp['Content-Disposition'] = 'attachment; filename=%s' % 'ujjwala_bluebook_label_{}.prn'.format(
				obj.parent.id)

			return resp


# @method_decorator(login_required, 'dispatch')
# class NicErrorUpdateAddress(FormView):
# 	# model = ConnectionDisbursementInvitation
# 	form_class = NicUpdateAddressForm
# 	template_name = "ujjwala/NicErrorUpdateAddress/update_address.html"
#
# 	def dispatch(self, request, *args, **kwargs):
# 		application = self.get_object()
# 		if application:
# 			if application.status == \
# 					UjjwalaV2ApplicationStatus.NIC_ERROR_UPDATE_ADDRESS:
# 				return HttpResponse("Address already submitted by you and is under review.")
# 		return super().dispatch(request, *args, **kwargs)
#
# 	def get_object(self, queryset=None):
# 		try:
# 			obj = UjjwalaV2Application.objects.get(pk=self.kwargs.get('pk'))
# 		except:
# 			raise Http404(
# 				"No application with id: {} found.".format(self.kwargs.get('pk'))
# 			)
# 		return obj
#
# 	def get_context_data(self, **kwargs):
# 		context = super().get_context_data(**kwargs)
# 		obj = self.get_object()
# 		context.update({
# 			"obj": obj
# 		})
# 		return context
#
# 	def form_valid(self, form):
# 		obj = self.get_object()
# 		data = form.clean()
# 		old_address_json = obj.address_json or obj.address
# 		obj.transition_nic_address_updated(
# 			description=old_address_json,
# 			address_json=data['address_json']
# 		)
# 		obj.save()
# 		return HttpResponse("<b>Address Updated Successfully</b>")


# @method_decorator(login_required, 'dispatch')
class NicErrorUpdateAddress(FormView):
	# model = ConnectionDisbursementInvitation
	form_class = NicUpdateAddressForm
	template_name = "ujjwala/NicErrorUpdateAddress/update_address.html"

	def dispatch(self, request, *args, **kwargs):
		application = self.get_object()
		if application:
			if application.status == \
					UjjwalaV2ApplicationStatus.NIC_ERROR_UPDATE_ADDRESS:
				return HttpResponse("Address already submitted by you and is under review.")
		return super().dispatch(request, *args, **kwargs)

	def get_object(self, queryset=None):
		try:
			obj = UjjwalaV2Application.objects.get(pk=self.kwargs.get('pk'))
		except:
			raise Http404(
				"No application with id: {} found.".format(self.kwargs.get('pk'))
			)
		return obj

	def get_context_data(self, **kwargs):
		context = super().get_context_data(**kwargs)
		obj = self.get_object()
		context.update({
			"obj": obj
		})
		return context

	def form_valid(self, form):
		obj = self.get_object()
		data = form.clean()
		old_address_json = obj.address_json or obj.address
		obj.transition_nic_address_updated(
			description=old_address_json,
			address_json=data['address_json']
		)
		obj.save()
		return HttpResponse("<b>Address Updated Successfully</b>")


class UpdateAddressView(FormView):
	form_class = UpdateAddressForm
	template_name = "ujjwala/user_update_address.html"

	def dispatch(self, request, *args, **kwargs):
		application = self.get_object()
		if application:
			if application.status == 'REVIEW_ADDRESS':
				return render(
					self.request,
					"ujjwala/response.html",
					{
						"heading": "Update Address",
						"message": "Address already submitted by you and is under review."
					}
				)
		return super().dispatch(request, *args, **kwargs)

	def get_object(self, queryset=None):
		try:
			obj = UjjwalaV2Application.objects.get(pk=self.kwargs.get('pk'))
		except:
			raise Http404(
				"No application with id: {} found.".format(self.kwargs.get('pk'))
			)
		return obj

	def get_context_data(self, **kwargs):
		context = super().get_context_data(**kwargs)
		obj = self.get_object()
		context.update({
			"obj": obj
		})
		return context

	def get_form_kwargs(self):
		kwargs = super().get_form_kwargs()
		obj = self.get_object()
		# kwargs['pre_inspection'] = pre_inspection
		# kwargs['initial'] = obj.address_json
		return kwargs

	def form_valid(self, form):
		obj = self.get_object()
		data = form.clean()
		old_address_json = obj.address_json or obj.address
		obj.address_json = data['address_json']
		obj.transition_review_address(
			description=old_address_json,
			address_json=data['address_json']
		)
		obj.save()
		return render(
			self.request,
			"ujjwala/response.html",
			{
				"heading": "Change Address",
				"message": "Address Updated Successfully"
			}
		)


class ChangeAddressView(FormView):
	form_class = UpdateAddressForm
	template_name = "ujjwala/update_address.html"

	# def dispatch(self, request, *args, **kwargs):
	# 	application = self.get_object()
	# 	if application:
	# 		if application.address_updated:
	# 			return HttpResponse("Address already submitted by you and is under review.")
	# 	return super().dispatch(request, *args, **kwargs)

	def get_object(self, queryset=None):
		try:
			obj = UjjwalaV2Application.objects.get(pk=self.kwargs.get('pk'))
		except:
			raise Http404(
				"No application with id: {} found.".format(self.kwargs.get('pk'))
			)
		return obj

	def get_context_data(self, **kwargs):
		context = super().get_context_data(**kwargs)
		obj = self.get_object()
		context.update({
			"obj": obj,
		})
		return context

	def get_form_kwargs(self):
		kwargs = super().get_form_kwargs()
		obj = self.get_object()
		# kwargs['pre_inspection'] = pre_inspection
		kwargs['initial'] = obj.address_json
		return kwargs

	def form_invalid(self, form):
		return super().form_invalid(form)

	def form_valid(self, form):
		obj = self.get_object()
		data = form.clean()
		old_address_json = obj.address_json or obj.address
		obj.transition_updated_address(
			description=old_address_json,
			address_json=data['address_json']
		)
		obj.save()
		return render(
			self.request,
			"ujjwala/response.html",
			{
				"heading": "Change Address",
				"message": "Address Updated Successfully"
			}
		)


class PreInspectionConvertToView(FormView):
	# model = ConnectionDisbursementInvitation
	form_class = PreInspectionConvertForm
	template_name = "ujjwala/pre-inspection/pre_inspection_conversion.html"

	def dispatch(self, request, *args, **kwargs):
		obj = self.get_object()
		if obj:
			if obj.status in (
					PreInspectionStatusEnum.SUBMITTED,
					PreInspectionStatusEnum.ACCEPTED,
			):
				return HttpResponse("Pre Inspection Already Submitted")
			if self.kwargs.get('convert_to') == 'mech' and obj.type == PreInspectionTypeEnum.MECHANIC:
				return redirect(
					reverse('ujjwala:pre_inspection_form_view',
							args=('mech', obj.pk)) + '?{}'.format(request.GET.urlencode())
				)
				# return redirect('ujjwala:pre_inspection_form_view', type="mech", pk=obj.pk)
			elif self.kwargs.get('convert_to') == 'self' and obj.type == PreInspectionTypeEnum.SELF:
				return redirect(
					reverse('ujjwala:pre_inspection_form_view',
							args=('self', obj.pk)) + '?{}'.format(request.GET.urlencode())
				)
				# return redirect('ujjwala:pre_inspection_form_view', type="self", pk=obj.pk)
		return super().dispatch(request, *args, **kwargs)

	def get_object(self, queryset=None):
		try:
			obj = PreInspection.objects.get(pk=self.kwargs.get('pk'))
		except:
			raise Http404(
				"No application with id: {} found.".format(self.kwargs.get('pk'))
			)
		return obj

	def get_context_data(self, **kwargs):
		context = super().get_context_data(**kwargs)
		obj = self.get_object()
		convert_to = self.kwargs.get('convert_to')
		context.update({
			"obj": obj,
			"convert_to": PreInspectionTypeEnum.MECHANIC if convert_to == 'mech' else PreInspectionTypeEnum.SELF
		})
		return context

	def get_initial(self):
		kwargs = super().get_initial()
		kwargs.update({
			'convert_to': self.kwargs.get('convert_to')
		})
		return kwargs

	def form_valid(self, form):
		obj = self.get_object()
		data = form.clean()

		if data['convert_to'] == 'mech':
			convert_to = PreInspectionTypeEnum.MECHANIC
		else:
			convert_to = PreInspectionTypeEnum.SELF

		if not obj.type == convert_to:
			obj.convert_inspection_type(convert_to_type=data['convert_to'])
			obj.save()
		return redirect(
			reverse('ujjwala:pre_inspection_form_view',
					args=(data['convert_to'], obj.pk)) + '?{}'.format(self.request.GET.urlencode())
		)
		# return redirect('ujjwala:pre_inspection_form_view', type=data['convert_to'], pk=obj.pk)


@method_decorator(login_required, 'dispatch')
class UjjwalaPreInspectionUserListView(ListView):
	model = PreInspection
	template_name = 'ujjwala/pre-inspection/pre_inspection_user_listview.html'
	paginate_by = 20
	permission = 'has_view_permission'

	def get_queryset(self):
		return PreInspection.objects.filter(
			mechanic=get_current_user()
		).order_by('-submitted_on')

	def get_context_data(self, **kwargs):
		context = super().get_context_data(**kwargs)
		list_pre_inspection = PreInspection.objects.filter(mechanic=get_current_user())
		paginator = Paginator(list_pre_inspection, self.paginate_by)

		page = self.request.GET.get('page')

		try:
			list_pre_inspection = paginator.page(page)
		except PageNotAnInteger:
			list_pre_inspection = paginator.page(1)
		except EmptyPage:
			list_pre_inspection = paginator.page(paginator.num_pages)

		context['list_pre_inspection'] = list_pre_inspection
		return context


class UpdateBankDetailsFormView(FormView):
	form_class = UpdateBankDetailsForm

	def get_template_names(self):
		obj = self.get_object()
		if obj.ifsc_code:
			return "ujjwala/extra/show_bank_details.html"
		else:
			return "ujjwala/extra/update_bank_details.html"

	def get_object(self, queryset=None):
		try:
			obj = UjjwalaV2Application.objects.get(pk=self.kwargs.get('pk'))
		except:
			raise Http404(
				"No application found with Application Id: {}".format(self.kwargs.get('pk'))
			)
		return obj

	def form_valid(self, form):
		form.save()

		obj = self.get_object()
		messages.add_message(
			self.request, messages.INFO, "Application Id {}: Remarks Updated: {}".format(obj.pk, obj.customer_remarks)
		)
		return redirect('ujjwala:application_status_search')

	def get_context_data(self, **kwargs):
		context = super().get_context_data()
		obj = self.get_object()
		context.update({
			"obj": obj,
		})
		return context

	def get_form_kwargs(self):
		kwargs = super().get_form_kwargs()
		obj = self.get_object()
		kwargs.update({
			'application': obj
		})
		return kwargs


class UpdateBankDetailsNewFormView(FormView):
	form_class = UpdateBankDetailsNewForm
	template_name = "ujjwala/extra/update_bank_details_new.html"

	def dispatch(self, request, *args, **kwargs):
		obj = self.get_object()
		bd_obj = BankDetailsUpdateRequest.objects.filter(parent=obj).first()

		if bd_obj.status != BankDetailsUpdateRequestEnum.MESSAGE_SENT:
			return render(
				self.request,
				"ujjwala/response.html",
				{
					"heading": "Update Bank Details",
					"message": "Your bank details update request has been already submitted."
				}
			)

		return super().dispatch(request, *args, **kwargs)

	def get_object(self, queryset=None):
		try:
			obj = UjjwalaV2Application.objects.get(pk=self.kwargs.get('pk'))
		except:
			raise Http404(
				"No application found with Application Id: {}".format(self.kwargs.get('pk'))
			)
		return obj

	def form_valid(self, form):
		cleaned_data = form.cleaned_data
		obj = self.get_object()
		bd_obj: BankDetailsUpdateRequest = BankDetailsUpdateRequest.objects.filter(parent=obj).first()

		if bd_obj:
			res = requests.get(f"https://ifsc.razorpay.com/{bd_obj.ifsc_code}")
			bd_obj.ifsc_verified = True if res.status_code == 200 else False
			bd_obj.name_as_per_bank = cleaned_data['name_as_per_bank']
			bd_obj.bank_account_number = cleaned_data['bank_account_number']
			bd_obj.ifsc_code = cleaned_data['ifsc_code']
			bd_obj.passbook_url = cleaned_data['passbook_photo']
			bd_obj.status = BankDetailsUpdateRequestEnum.RECEIVED
			bd_obj.save()

			url = f"https://camunda.dca.arungas.com/engine-rest/message"

			res = requests.post(url, json={
				"messageName": "Message_payment_profile_update_bank_number_updated_received",
				'processInstanceId': bd_obj.camunda_process_id,
				"processVariables": {
					"name_as_per_bank": {"value": bd_obj.name_as_per_bank, "type": "String"},
					"bank_account_number": {"value": bd_obj.bank_account_number, "type": "String"},
					"ifsc_code": {"value": bd_obj.ifsc_code, "type": "String"},
					"passbook_url": {"value": bd_obj.passbook_url, "type": "String"},
				}
			})
			res.raise_for_status()
			return render(
				self.request,
				"ujjwala/response.html",
				{
					"heading": "Update Bank Details",
					"message": "Your bank details update request has been submitted."
				}
			)
		else:
			return render(
				self.request,
				"ujjwala/response.html",
				{
					"heading": "Update Bank Details",
					"message": "No Opened Request Found. Contact Admin."
				}
			)

	def get_context_data(self, **kwargs):
		context = super().get_context_data()
		obj = self.get_object()
		context.update({
			"obj": obj,
		})
		return context


class NicClearedCustomerRemarks(FormView):
	form_class = NicClearedCustomerRemarksForm
	template_name = "ujjwala/extra/nic_cleared_customer_remarks.html"

	def get_object(self, queryset=None):
		try:
			obj = UjjwalaV2Application.objects.get(pk=self.kwargs.get('pk'))
		except:
			raise Http404(
				"No application found with Application Id: {}".format(self.kwargs.get('pk'))
			)
		return obj

	def form_valid(self, form):
		data = form.cleaned_data
		obj = self.get_object()
		obj.customer_remarks = data['customer_remarks']
		obj.availability_status = data['customer_remarks']
		obj.availability_channel = UjjwalaV2ApplicationAvailabilityChannel.USER
		obj.availability_updated_on = datetime.datetime.now()
		obj.scheduled_date = data['scheduled_date']
		obj.additional_remarks = data['description']
		obj.save()
		messages.add_message(
			self.request, messages.INFO, "Application Id {}: Remarks Updated: {}".format(obj.pk, obj.customer_remarks)
		)
		return redirect('ujjwala:application_status_search')

	#
	# return HttpResponse(content="Customer Remarks Updated Successfully.")

	def get_context_data(self, **kwargs):
		context = super().get_context_data()
		obj = self.get_object()
		context.update({"obj": obj, })
		return context


class PrintDocumentsView(FormView):
	form_class = PrintDocumentsForm
	template_name = "ujjwala/extra/print_documents.html"

	# def get_object(self, queryset=None):
	#     try:
	#         obj = UjjwalaV2Application.objects.get(pk=self.kwargs.get('pk'))
	#     except:
	#         raise Http404(
	#             "No application found with Application Id: {}".format(self.kwargs.get('pk'))
	#         )
	#     return obj

	def form_valid(self, form):
		data = form.cleaned_data
		res = download_audit_documents_for_ids(data['ids'], data['documents'], )

		# django_rq.enqueue(
		#     download_audit_documents_for_ids,
		#     args=(data['ids'], data['documents'],),
		#     result_ttl=86400 * 2
		# )
		# return HttpResponse(content=res)
		return res


class LegalDocumentsAcceptedToPendingView(View):

	def dispatch(self, request, *args, **kwargs):
		connection_disbursement = ConnectionDisbursement.objects.get(parent_id=kwargs.get('pk'))
		connection_disbursement.transition_legal_documents_pending(data={'reason': 'LOST'})
		connection_disbursement.save()

		return JsonResponse({
			"status": "Updated"
		})


class GetEKYCStatusFromSDMS(View):

	def dispatch(self, request, *args, **kwargs):
		application = UjjwalaV2Application.objects.get(pk=kwargs.get('pk'))
		if not application.consumer_id:
			return render(
				self.request,
				"ujjwala/response.html",
				{
					"heading": "Update E-KYC Request",
					"message": "Consumer Id Does Not Exist. Please Retry After Few Days (Pre-Suraksha Accepted)"
				}
			)

		if not application.address_json:
			return render(
				self.request,
				"ujjwala/response.html",
				{
					"heading": "Address Update",
					"message": "Please Update Address Then Proceed"
				}
			)

		result = is_process_exist_in_camunda('process_get_ekyc_status_from_sdms', 'dca_id', application.id)
		user = get_current_user()
		if result == 0:
			variables = {
				"variables":
					{
						"dca_id": {"value": application.id, "type": "String"},
						"consumer_id": {"value": application.consumer_id, "type": "String"},
						"requested_by": {"value": f"{user.first_name} {user.last_name}", "type": "String"},
						"requested_by_id": {"value": f"{user.id}", "type": "String"},
						"contact": {"value": json.dumps(get_data_for_new_relation(application.id)), "type": "String"},
						"start_time": {"value": datetime.datetime.now().strftime('%Y-%m-%dT%H:%M:%S+0530'),
									   "type": "String"}
					}
			}
			res, process_id = start_process_in_camunda_v2('process_get_ekyc_status_from_sdms', variables)
			message = "Request Generated With Camunda Process Id: {}".format(process_id)
		else:
			message = "Already Request Generated For Update E-KYC"
		return render(
			self.request, "ujjwala/response.html", {"heading": "Update E-KYC Request", "message": message}
		)


class ShareOnSocialMediaView(View):
	def get(self, request, *args, **kwargs):
		connection_disbursement_id = kwargs.get('pk', '')

		if not connection_disbursement_id:
			return render(
				self.request, "ujjwala/response.html",
				{"heading": "Share On Social Media", "message": "Invalid Link"}
			)

		connection_disbursement = ConnectionDisbursement.objects.get(pk=connection_disbursement_id)

		if connection_disbursement.social_media_update_done:
			return render(
				self.request, "ujjwala_share/ujjwala.html",
				{
					"name": connection_disbursement.parent.name,
					"social_media_url": connection_disbursement.documents.filter(
						type=UjjwalaApplicationDocumentsEnum.SOCIAL_MEDIA_PHOTO).first().link
				}
			)
		else:
			return render(
				self.request, "ujjwala/response.html",
				{"heading": "Share On Social Media", "message": "Social Media Photo Not Uploaded"}
			)


# @method_decorator(login_required, 'dispatch')
class CancelInvitationView(FormView):
	form_class = CancelInvitationForm
	template_name = "ujjwala/disbursement/cancel_invitation.html"

	def get_object(self, queryset=None):
		try:
			obj = UjjwalaV2Application.objects.get(pk=self.kwargs.get('pk'))
		except:
			raise Http404(
				"No application with id: {} found.".format(self.kwargs.get('pk'))
			)
		return obj

	def form_valid(self, form):
		data = form.clean()
		obj = UjjwalaV2Application.objects.filter(id=data['application_id']).first()
		if not obj:
			messages.add_message(self.request, messages.ERROR,
								 "No Application Exist With Given Id: {}".format(data['application_id']))
			return redirect(".")

		invitation = obj.connection_disbursement.invitation.filter(status=ConnectionDisbursementInvitationEnum.VALID)
		if not invitation.exists():
			messages.add_message(self.request, messages.ERROR,
								 "No Invitation Exist For Given Application Id: {}".format(data['application_id']))
			return redirect(".")

		invitation = invitation.first()
		invitation.status = ConnectionDisbursementInvitationEnum.CANCELED
		invitation.canceled_reason = data['reason']
		invitation.save()
		messages.add_message(self.request, messages.ERROR, "Invitation Canceled")
		return redirect(".")


# @method_decorator(login_required, 'dispatch')
class UpdateRelationshipNumberView(FormView):
	form_class = NewRelationCreated
	template_name = "ujjwala/extra/update_relationship_number.html"

	def get_object(self, queryset=None):
		try:
			obj = UjjwalaV2Application.objects.get(pk=self.kwargs.get('pk'))
		except:
			raise Http404(
				"No application with id: {} found.".format(self.kwargs.get('pk'))
			)
		return obj

	def form_valid(self, form):
		data = form.clean()
		application = self.get_object()
		application.consumer_id = data['consumer_id']
		application.save()
		messages.add_message(self.request, messages.INFO, "New Consumer Id Updated")
		return redirect(".")


@method_decorator(login_required, 'dispatch')
class ChangePhoneNumberView(FormView):
	form_class = ChangePhoneNumberForm
	template_name = "ujjwala/change_phone_number.html"

	def get_object(self, queryset=None):
		try:
			obj = UjjwalaV2Application.objects.get(pk=self.kwargs.get('pk'))
		except:
			raise Http404(
				"No application with id: {} found.".format(self.kwargs.get('pk'))
			)
		return obj

	def dispatch(self, request, *args, **kwargs):
		obj = self.get_object()
		sr_obj = ServiceRequest.objects.filter(
			content_type=ContentType.objects.get(
				app_label='ujjwala', model='ujjwalav2application'
			),
			object_id=obj.id,
			service_request_type=ServiceRequestTypeEnum.CHANGE_PHONE_NUMBER,
			status=ServiceRequestTypeStatusEnum.PENDING
		).first()

		if sr_obj:
			message = f"Service Request For Change Phone Number Already Submitted. Service Request Id: {sr_obj.id} Status: {sr_obj.status}"
			return render(self.request, "ujjwala/response.html",
						  {"heading": "Update Address Service Request", "message": message})
		return super().dispatch(request, *args, **kwargs)

	def get_context_data(self, **kwargs):
		context = super().get_context_data(**kwargs)
		obj = self.get_object()
		context.update({
			"obj": obj
		})
		return context

	def form_valid(self, form):
		obj = self.get_object()
		data = form.clean()
		user = get_current_user()

		ujjwala_v2_application_content_type = ContentType.objects.get(
			app_label='ujjwala', model='ujjwalav2application'
		)

		sr_obj = ServiceRequest.objects.filter(
			content_type=ujjwala_v2_application_content_type,
			object_id=obj.id,
			service_request_type=ServiceRequestTypeEnum.CHANGE_PHONE_NUMBER,
			status=ServiceRequestTypeStatusEnum.PENDING
		).first()

		if sr_obj:
			message = f"Service Request For Change Phone Number Already Submitted. Service Request Id: {sr_obj.id} Status: {sr_obj.status}"
		else:
			service_request = ServiceRequest.objects.create(
				service_request_type=ServiceRequestTypeEnum.CHANGE_PHONE_NUMBER,
				content_type=ujjwala_v2_application_content_type,
				object_id=obj.id,
				request_by=user,
				form_data={
					"application_id": obj.id,
					"phone_number": data['phone_number']
				}
			)
			from service_request.functions import start_service_request_process_in_camunda

			create_job_function = partial(
				django_rq.enqueue,
				start_service_request_process_in_camunda,
				service_request_id=service_request.id,
				variables={
						"request_video_url": {"value": data['request_video_url'], "type": "string"},
						"phone_number": {"value": data['phone_number'], "type": "string"},
						"application_id": {"value": obj.id, "type": "long"},
						"name": {"value": obj.name, "type": "string"},
						"status": {"value": obj.status, "type": "string"},
						"old_phone_numbers": {"value": json.dumps(obj.all_contacts), "type": "string"},
						"request_by": {"value": f"{user.first_name} {user.last_name}"},
						"service_request_id": {"value": service_request.id, "type": "long"},
						"dca_app": {"value": "ujjwala", "type": "String"},
						"request_type": {"value": ServiceRequestTypeEnum.CHANGE_PHONE_NUMBER, "type": "String"}
					}
			)
			transaction.on_commit(create_job_function)
			message = "Service Request For Change Phone Number Initiated. Please Wait For Some Time."

		return render(
			self.request, "ujjwala/response.html", {"heading": "Change Phone Number Request Form", "message": message}
		)


@method_decorator(login_required, 'dispatch')
class UpdateAddressServiceRequestView(FormView):
	form_class = UpdateAddressForm
	template_name = "ujjwala/update_address.html"

	def get_object(self, queryset=None):
		try:
			obj = UjjwalaV2Application.objects.get(pk=self.kwargs.get('pk'))
		except:
			raise Http404(
				"No application with id: {} found.".format(self.kwargs.get('pk'))
			)
		return obj


	def dispatch(self, request, *args, **kwargs):
		obj = self.get_object()
		sr_obj = ServiceRequest.objects.filter(
			content_type=ContentType.objects.get(
				app_label='ujjwala', model='ujjwalav2application'
			),
			object_id=obj.id,
			service_request_type=ServiceRequestTypeEnum.UPDATE_ADDRESS,
			status=ServiceRequestTypeStatusEnum.PENDING
		).first()

		if sr_obj:
			message = f"Service Request For Update Address Already Submitted. Service Request Id: {sr_obj.id} Status: {sr_obj.status}"
			return render(self.request, "ujjwala/response.html",
						  {"heading": "Update Address Service Request", "message": message})
		return super().dispatch(request, *args, **kwargs)


	def get_context_data(self, **kwargs):
		context = super().get_context_data(**kwargs)
		obj = self.get_object()
		context.update({
			"obj": obj
		})
		return context

	def form_valid(self, form):
		obj = self.get_object()
		address_json = form.clean()
		user = get_current_user()

		ujjwala_v2_application_content_type = ContentType.objects.get(
			app_label='ujjwala', model='ujjwalav2application'
		)

		sr_obj = ServiceRequest.objects.filter(
			content_type=ujjwala_v2_application_content_type,
			object_id=obj.id,
			service_request_type=ServiceRequestTypeEnum.UPDATE_ADDRESS,
			status=ServiceRequestTypeStatusEnum.PENDING
		).first()

		if sr_obj:
			message = f"Service Request For Change Address Already Submitted. Service Request Id: {sr_obj.id} Status: {sr_obj.status}"
		else:
			service_request = ServiceRequest.objects.create(
				service_request_type=ServiceRequestTypeEnum.UPDATE_ADDRESS,
				content_type=ujjwala_v2_application_content_type,
				object_id=obj.id,
				request_by=user,
				form_data={
					"application_id": obj.id,
					"new_address": address_json,
					"old_address": obj.address_json,
					"dca_app": "ujjwala",
				}
			)
			from service_request.functions import start_service_request_process_in_camunda

			variables = {
				"old_address": {"value": json.dumps(obj.address_json), "type": "string"},
				"new_address": {"value": json.dumps(address_json), "type": "string"},
				"application_id": {"value": obj.id, "type": "long"},
				"name": {"value": obj.name, "type": "string"},
				"status": {"value": obj.status, "type": "string"},
				"request_by": {"value": f"{user.first_name} {user.last_name}"},
				"service_request_id": {"value": service_request.id, "type": "long"},
				"dca_app": {"value": "ujjwala", "type": "String"},
				"request_type": {"value": ServiceRequestTypeEnum.UPDATE_ADDRESS, "type": "String"}
			}

			create_job_function = partial(
				django_rq.enqueue,
				start_service_request_process_in_camunda,
				service_request_id=service_request.id,
				variables=variables
			)
			transaction.on_commit(create_job_function)
			# start_service_request_process_in_camunda(service_request.id, variables)
			message = "Service Request For Update Address Initiated. Please Wait For Some Time."

		return render(
			self.request, "ujjwala/response.html", {"heading": "Update Address Request Form", "message": message}
		)


class DownloadChangeCylinderTypeFormView(View):

	def get(self, request, *args, **kwargs):
		obj = UjjwalaV2Application.objects.filter(id=kwargs.get('pk')).first()
		if not obj:
			return HttpResponse("Application Id {} does not exist".format(kwargs.get('pk')))

		document = download_change_cylinder_type_form(obj)
		resp = HttpResponse(document, content_type="application/pdf")
		resp['Content-Disposition'] = 'attachment; filename=%s' % 'change_cylinder_form_{}.pdf'.format(
			obj.id)

		return resp


@method_decorator(login_required, 'dispatch')
class ChangeCylinderTypeView(FormView):
	form_class = ChangeCylinderTypeForm
	template_name = "ujjwala/change_cylinder.html"

	def get_object(self, queryset=None):
		try:
			obj = UjjwalaV2Application.objects.get(pk=self.kwargs.get('pk'))
		except:
			raise Http404(
				"No application with id: {} found.".format(self.kwargs.get('pk'))
			)
		return obj

	def dispatch(self, request, *args, **kwargs):
		obj = self.get_object()

		if not '5' in obj.customer_profile.products:
			message = f"Customer Product: {obj.customer_profile.products} Not Valid For Conversion In 14.2 Kg"
			return render(self.request, "ujjwala/response.html",
						  {"heading": "Change Cylinder Type Service Request", "message": message})

		user = get_current_user()
		if not user.has_perm('ujjwala.can_initiate_change_cylinder_type_request'):
			return render(self.request, "ujjwala/response.html",
						  {"heading": "Change Cylinder Type Service Request", "message": "Permission Denied"})

		return super().dispatch(request, *args, **kwargs)

	def get_context_data(self, **kwargs):
		context = super().get_context_data(**kwargs)
		obj = self.get_object()

		cctr_obj = ChangeCylinderTypeRequest.objects.filter(parent=obj).first()

		if cctr_obj:
			context.update({
				'already_submitted': True,
				'request_obj': cctr_obj
			})
		# 	message = f""
		# 	return render(self.request, "ujjwala/response.html",
		# 	              {"heading": "Change Cylinder Type Service Request", "message": message})
		user = get_current_user()
		organization = user.organizations_organization.first()
		context.update({
			"obj": obj,
			"user": user,
			"organization": organization,
			"service_location": organization.service_locations.first() if organization else None,
		})
		return context

	def form_valid(self, form):
		obj = self.get_object()
		data = form.clean()
		address_json = None
		if data.get('change_address'):
			address_json = {
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

		cctr_obj = ChangeCylinderTypeRequest.objects.create(
			parent=obj, pos=get_current_user(),
			change_phone_number=data.get('change_phone_number'),
			new_phone_number=data.get('new_phone_number'),
			change_address=data.get('change_address'),
			address_json=address_json,
			phone_request_video_url=data.get('request_video_url')
		)

		django_rq.enqueue(
			upload_form_e_document_and_whatsapp,
			args=(
				get_current_user().id, obj.id, data.get('new_phone_number') if data.get('change_phone_number') else obj.contact_mobile,
			)
		)
		messages.add_message(self.request, messages.INFO,
							 f"Change Cylinder Type Request Generated Successfully. Id: {cctr_obj.id}")
		return redirect(reverse("ujjwala:change_cylinder_type", kwargs={'pk': self.kwargs.get('pk')}))


@method_decorator(login_required, 'dispatch')
class ChangeCylinderTypeRequestListView(FilterView):
	model = ChangeCylinderTypeRequest
	template_name = 'ujjwala/service_request/change_cylinder_type/change_cylinder_type_request_listview.html'
	context_object_name = 'objects'
	filterset_class = ChangeCylinderTypeRequestFilter

	paginate_by = 20
	permission = 'has_view_permission'

	def dispatch(self, request, *args, **kwargs):
		user = get_current_user()
		if not user.has_perm('ujjwala.can_process_change_cylinder_request'):
			return render(self.request, "ujjwala/response.html",
						  {"heading": "Change Cylinder Type Service Request", "message": "Permission Denied"})
		return super().dispatch(request, args, kwargs)


# def get_queryset(self):
# 	return ChangeCylinderTypeRequest.objects.exclude(
# 		status=ChangeCylinderTypeRequestStatusEnum.COMPLETED
# 	)


class ChangeCylinderTypeRequestView(FormView):
	form_class = ChangeCylinderTypeRequestForm
	template_name = "ujjwala/service_request/change_cylinder_type/change_cylinder_type_request.html"

	def get_object(self, queryset=None):
		try:
			obj = ChangeCylinderTypeRequest.objects.get(pk=self.kwargs.get('pk'))
		except:
			raise Http404(
				"No application with id: {} found.".format(self.kwargs.get('pk'))
			)
		return obj

	def dispatch(self, request, *args, **kwargs):
		obj = self.get_object()
		if obj.status == ChangeCylinderTypeRequestStatusEnum.COMPLETED:
			return render(
				self.request,
				"ujjwala/response.html",
				{
					"heading": "Change Cylinder Type Request",
					"message": "Your requested is already completed."
				}
			)
		user = get_current_user()
		if not user.has_perm('ujjwala.can_process_change_cylinder_request'):
			return render(self.request, "ujjwala/response.html",
						  {"heading": "Change Cylinder Type Service Request", "message": "Permission Denied"})
		return super().dispatch(request, args, kwargs)

	def get_context_data(self, **kwargs):
		context = super().get_context_data(**kwargs)
		obj = self.get_object()
		context.update({
			"obj": obj
		})
		return context

	def get_form_kwargs(self):
		kwargs = super().get_form_kwargs()
		kwargs['request_obj'] = self.get_object()
		return kwargs

	def form_valid(self, form):
		obj = self.get_object()
		data = form.cleaned_data
		obj.change_address_sr_no = data.get('change_address_sr_no') if obj.change_address else None
		obj.change_phone_number_sr_no = data.get('change_phone_number_sr_no') if obj.change_phone_number else None
		obj.status = ChangeCylinderTypeRequestStatusEnum.COMPLETED
		obj.save()
		obj.parent.documents.create(
			link=data.get('new_sv_photo'),
			type=UjjwalaApplicationDocumentsEnum.CONVERSION_NEW_SV_PHOTO
		)
		obj.parent.documents.create(
			link=data.get('canceled_sv_photo'),
			type=UjjwalaApplicationDocumentsEnum.CONVERSION_CANCELED_SV_PHOTO
		)
		obj.parent.documents.create(
			link=data.get('form_e_page_1_photo'),
			type=UjjwalaApplicationDocumentsEnum.FORM_E_PAGE_1
		)
		obj.parent.documents.create(
			link=data.get('form_e_page_2_photo'),
			type=UjjwalaApplicationDocumentsEnum.FORM_E_PAGE_2
		)
		# Updating New Phone Number & Address In Ujjwala Application
		obj.parent.contact_mobile = obj.new_phone_number
		obj.parent.address_json = obj.address_json
		obj.parent.customer_profile.products = 'Ujjwala - 14.2 Kg General Package'
		obj.parent.customer_profile.save()
		obj.parent.save()

		messages.add_message(self.request, messages.INFO, "Form Updated Successfully.")
		response = redirect(reverse('ujjwala:change_cylinder_request_list'))
		return response


class ChangeCylinderTypeRequestOverrideView(FormView):
	form_class = ChangeCylinderTypeRequestOverrideForm
	template_name = "ujjwala/service_request/change_cylinder_type/change_cylinder_type_request_override.html"

	def get_object(self, queryset=None):
		try:
			obj = UjjwalaV2Application.objects.get(pk=self.kwargs.get('pk'))
		except:
			raise Http404(
				"No application with id: {} found.".format(self.kwargs.get('pk'))
			)
		return obj

	def dispatch(self, request, *args, **kwargs):
		user = get_current_user()
		if not user.has_perm('ujjwala.can_override_change_cylinder_type_request'):
			return render(self.request, "ujjwala/response.html",
						  {"heading": "Change Cylinder Type Service Request", "message": "Permission Denied"})
		return super().dispatch(request, args, kwargs)

	def get_context_data(self, **kwargs):
		context = super().get_context_data(**kwargs)
		obj = self.get_object()
		context.update({
			"obj": obj
		})
		return context

	def get_form_kwargs(self):
		kwargs = super().get_form_kwargs()
		return kwargs

	def form_valid(self, form):
		obj = self.get_object()
		data = form.cleaned_data
		obj.override_change_cylinder_type = True
		obj.sdms_refills = data.get('sdms_refills')
		obj.override_change_cylinder_type_by = get_current_user()
		obj.save()
		messages.add_message(self.request, messages.INFO, "Form Updated Successfully.")
		response = redirect(reverse('ujjwala:change_cylinder_request_list'))
		return response


class UploadUIDForEKYCView(FormView):
	form_class = UploadUIDForEKYCForm
	template_name = "ujjwala/upload_uid_for_ekyc.html"

	def get_object(self, queryset=None):
		try:
			obj = UjjwalaV2Application.objects.get(pk=self.kwargs.get('pk'))
		except:
			raise Http404(
				"No application with id: {} found.".format(self.kwargs.get('pk'))
			)
		return obj

	def get_context_data(self, **kwargs):
		context = super().get_context_data(**kwargs)
		obj = self.get_object()
		context.update({
			"obj": obj
		})
		return context

	def form_valid(self, form):
		obj = self.get_object()
		data = form.clean()

		result, msg = start_process_in_camunda(
			"process_dca_change_phone_number",
			{
				"variables": {
					"request_video_url": {"value": data['request_video_url'], "type": "string"},
					"phone_number": {"value": data['phone_number'], "type": "string"},
					"application_id": {"value": obj.id, "type": "long"},
					"name": {"value": obj.name, "type": "string"},
					"status": {"value": json.dumps(obj.all_contacts.__str__()), "type": "string"},
				}
			}
		)
		if result:
			service_request = ServiceRequest.objects.create(
				service_request_type=ServiceRequestTypeEnum.UID_UPLOAD_FOR_EKYC,
				camunda_process_id=msg
			)
			messages.add_message(
				self.request,
				messages.INFO,
				f"Service Request For Change Phone Number Started With Id {service_request.id}. Please Wait For Some Time."
			)
		else:
			messages.add_message(
				self.request,
				messages.ERROR,
				f"Service Request For Change Phone Number Could Not Be Started. Please Contact Ujjwala Team."
			)

		response = redirect(reverse('ujjwala:application_status_search'))
		return response


@method_decorator(login_required, 'dispatch')
class UjjwalaApplicationAuditListView(ListView):
	model = PreInspection

	paginate_by = 20
	permission = 'has_view_permission'

	def get_queryset(self):
		return UjjwalaV2Application.objects.filter(
			status=UjjwalaV2ApplicationStatus.AUDIT_APPLICATION
		)

	def get_template_names(self):
		return 'ujjwala/review/ujjwala_application_audit_listview.html'


class UjjwalaApplicationAuditFamilyMembersForm(forms.ModelForm):
	class Meta:
		model = FamilyMembers
		# fields = "__all__"
		fields = [
			'name', 'dob', 'uid_no', 'uid_front_link', 'uid_back_link'
		]
	# exclude = ['uid_back_compressed', 'relation', 'uid_front_file_size', 'uid_back_file_size']


class UjjwalaApplicationAuditForm(forms.ModelForm):
	class Meta:
		model = UjjwalaV2Application
		# fields = "__all__"
		fields = [
			'ifsc_code', 'bank_account_number'
		]
	# exclude = [
	# 	'sdms_last_updated_on', 'marital_status', 'version', 'robo_sdms_dedup', 'status',
	# 	'availability_updated_on', 'tags', 'name', 'contact_mobile', 'ekyc_date', 'address',
	# ]


FamilyMembersInlineFormSet = inlineformset_factory(
	UjjwalaV2Application, FamilyMembers, UjjwalaApplicationAuditFamilyMembersForm, extra=0,
)


@method_decorator(login_required, 'dispatch')
class UjjwalaApplicationAuditView(UpdateView):
	model = UjjwalaV2Application
	template_name = 'ujjwala/review/ujjwala_application_audit_new.html'
	form_class = UjjwalaApplicationAuditForm

	def get_success_url(self):
		return reverse('ujjwala:ujjwala_application_audit_list')

	def dispatch(self, request, *args, **kwargs):
		user = get_current_user()
		if not is_member_of_reviewer_group(user):
			return render(request, 'ujjwala/no_permissions.html')

		application_id = request.GET.get('application_id', '')
		if application_id:
			application = self.get_object()
			if application.status != UjjwalaV2ApplicationStatus.AUDIT_APPLICATION:
				messages.add_message(self.request, messages.ERROR,
									 f"Application Id: {application_id} Not In Audit Status")
				return redirect('ujjwala:ujjwala_application_audit_list')
		return super().dispatch(request, *args, **kwargs)

	def get_object(self, queryset=None):
		try:
			obj = UjjwalaV2Application.objects.get(pk=self.kwargs.get('pk'))
		except:
			raise Http404(
				"No Application Exist For Given Application Id"
			)
		return obj

	def get_context_data(self, **kwargs):
		context = super().get_context_data(**kwargs)
		obj = self.get_object()
		if self.request.POST:
			context['obj'] = self.get_object()
			context['form'] = UjjwalaApplicationAuditForm(self.request.POST, instance=obj)
			context['formset'] = FamilyMembersInlineFormSet(self.request.POST, self.request.FILES, instance=obj)
			print("Formset")
		else:
			context['obj'] = self.get_object()
			context['form'] = UjjwalaApplicationAuditForm(instance=obj)
			context['formset'] = FamilyMembersInlineFormSet(instance=obj, prefix='family_members')

		change_address_url = reverse(
			'ujjwala:change_address_view',
			kwargs={'pk': obj.id}
		)
		context.update({
			"change_address_url": self.request.build_absolute_uri(change_address_url)
		})
		return context

	def form_valid(self, form):
		context = self.get_context_data()
		form = context['form']
		fm_formset = context['formset']
		if form.is_valid() and fm_formset.is_valid():
			obj = form.save()
			form.instance = obj
			form.save()
			fm_formset.instance = obj
			fm_formset.save()
		return self.render_to_response(self.get_context_data(form=form))

	def form_invalid(self, form):
		print(form)


@method_decorator(login_required, 'dispatch')
class BankDetailsUpdateRequestListView(ListView):
	model = BankDetailsUpdateRequest

	paginate_by = 20
	permission = 'has_view_permission'

	def get_queryset(self):
		# return ServiceRequest.objects.filter(
		# 	status=ServiceRequestTypeStatusEnum.PENDING
		# )
		return BankDetailsUpdateRequest.objects.filter(status=BankDetailsUpdateRequestEnum.RECEIVED).order_by('-id')

	def get_template_names(self):
		return 'ujjwala/review/bank_details_update_request_listview.html'


@method_decorator(login_required, 'dispatch')
class BankDetailsUpdateRequestView(FormView):
	template_name = 'ujjwala/review/bank_details_update_request_view.html'
	form_class = BankDetailsUpdateRequestForm

	def get_success_url(self):
		return reverse('ujjwala:bank_details_update_list')

	# def dispatch(self, request, *args, **kwargs):
	# 	user = get_current_user()
	# 	if not can_resolve_service_request(user):
	# 		return render(request, 'ujjwala/no_permissions.html')
	# 	return super().dispatch(request, *args, **kwargs)

	def get_object(self, queryset=None):
		try:
			obj = BankDetailsUpdateRequest.objects.get(pk=self.kwargs.get('pk'))
		except:
			raise Http404(
				"No Application Exist For Given Application Id"
			)
		return obj

	def get_context_data(self, **kwargs):
		context = super().get_context_data(**kwargs)
		obj = self.get_object()
		res = requests.get(
			f"https://camunda.dca.arungas.com/engine-rest/process-instance/{obj.camunda_process_id}/variables")
		res.raise_for_status()

		process_vars = res.json()

		for k, v in process_vars.items():
			context[k] = v['value']

		context.update({
			"bd_obj": obj,
		})
		return context

	def form_valid(self, form):
		obj = self.get_object()
		data = form.cleaned_data
		obj.status = data['review_status']
		obj.remarks = data['request_remarks']
		obj.save()

		res = requests.get('https://camunda.dca.arungas.com/engine-rest/task',
						   params={'processInstanceId': f'{obj.camunda_process_id}',
								   'taskDefinitionKey': 'Activity_payment_profile_update_review_bank_details'})
		# res = requests.get('https://camunda.dca.arungas.com/engine-rest/task',
		#                    params={'processInstanceId': f'{obj.camunda_process_id}',
		#                            'taskDefinitionKey': 'Activity_dca_change_phone_number_verify_request'})
		res.raise_for_status()

		res = requests.post(
			f"https://camunda.dca.arungas.com/engine-rest/task/{res.json()[0]['id']}/submit-form",
			json={'variables': {"bank_details": {"type": "String", "value": obj.status}}}
		)
		res.raise_for_status()

		return redirect(self.get_success_url())


@method_decorator(login_required, 'dispatch')
class UjjwalaApplicationServiceRequestListView(ListView):
	model = PreInspection

	paginate_by = 20
	permission = 'has_view_permission'

	def get_queryset(self):
		# return ServiceRequest.objects.filter(
		# 	status=ServiceRequestTypeStatusEnum.PENDING
		# )
		return ServiceRequest.objects.filter(status='PENDING').order_by('-id')

	def get_template_names(self):
		return 'ujjwala/service_request/ujjwala_application_service_request_listview.html'


@method_decorator(login_required, 'dispatch')
class UjjwalaApplicationServiceRequestView(FormView):
	template_name = 'ujjwala/service_request/ujjwala_application_service_request.html'

	def get_success_url(self):
		return reverse('ujjwala:service_request_list')

	def dispatch(self, request, *args, **kwargs):
		user = get_current_user()
		if not can_resolve_service_request(user):
			return render(request, 'ujjwala/no_permissions.html')
		return super().dispatch(request, *args, **kwargs)

	def get_object(self, queryset=None):
		try:
			obj = ServiceRequest.objects.get(pk=self.kwargs.get('pk'))
		except:
			raise Http404(
				"No Application Exist For Given Application Id"
			)
		return obj

	def get_context_data(self, **kwargs):
		context = super().get_context_data(**kwargs)
		obj = self.get_object()
		res = requests.get(
			f"https://camunda.dca.arungas.com/engine-rest/process-instance/{obj.camunda_process_id}/variables")
		res.raise_for_status()

		application = UjjwalaV2Application.objects.get(pk=obj.form_data.get('application_id'))
		process_vars = res.json()

		for k, v in process_vars.items():
			context[k] = v['value']

		context.update({
			"obj": obj,
			"application": application,
			"sr_request_template": "ujjwala/service_request/sr_" + obj.service_request_type.lower() + ".html",
		})
		return context

	def get_form_class(self):
		obj = self.get_object()

		if obj.service_request_type == ServiceRequestTypeEnum.UPDATE_ADDRESS:
			return ReviewUpdatedAddressForm
		elif obj.service_request_type == ServiceRequestTypeEnum.CHANGE_PHONE_NUMBER:
			return ChangePhoneNumberForm
		elif obj.service_request_type == ServiceRequestTypeEnum.CHANGE_CYLINDER_TO_14_2_KG:
			return ChangeCylinderForm

	def get_form_kwargs(self):
		kwargs = super().get_form_kwargs()
		obj = self.get_object()

		if obj.service_request_type == ServiceRequestTypeEnum.UPDATE_ADDRESS:
			kwargs['initial'] = json.loads(obj.form_data['new_address'])
		# elif obj.service_request_type == ServiceRequestTypeEnum.CHANGE_PHONE_NUMBER:
		# 	kwargs['initial'] = json.loads(obj.form_data)

		return kwargs

	def form_valid(self, form):
		obj = self.get_object()
		data = form.cleaned_data
		if data['review_status'] == 'REJECTED':
			obj.status = ServiceRequestTypeStatusEnum.REJECTED
			obj.remarks = data['request_remarks']
		elif data['review_status'] == 'ACCEPTED':
			obj.status = ServiceRequestTypeStatusEnum.SUCCESS
		obj.save()

		res = requests.get('https://camunda.dca.arungas.com/engine-rest/task',
						   params={'processInstanceId': f'{obj.camunda_process_id}',
								   'taskDefinitionKey': 'Activity_verify_dca_service_request'})
		# res = requests.get('https://camunda.dca.arungas.com/engine-rest/task',
		#                    params={'processInstanceId': f'{obj.camunda_process_id}',
		#                            'taskDefinitionKey': 'Activity_dca_change_phone_number_verify_request'})
		res.raise_for_status()

		res = requests.post(
			f"https://camunda.dca.arungas.com/engine-rest/task/{res.json()[0]['id']}/submit-form",
			json={'variables': {}}
		)
		res.raise_for_status()

		return redirect(self.get_success_url())


# @method_decorator(login_required, 'dispatch')
@method_decorator(csrf_exempt, 'dispatch')
class CamundaChangeAddressView(FormView):
	form_class = UpdateAddressForm
	template_name = "ujjwala/camunda_update_address.html"
	variables = None

	def dispatch(self, request, *args, **kwargs):
		pi_id = kwargs.get('process_instance_id')
		url = f'https://camunda.dca.arungas.com/engine-rest/process-instance/{pi_id}/activity-instances'
		res = requests.get(url)
		if res.status_code != 200:
			return HttpResponse("Process Instance Could Not Found")

		relevent_activity = False
		for activity_instance in res.json()['childActivityInstances']:
			if activity_instance['activityId'] in ['Event_review_address_new_address_received',
													   'Event_new_address_received']:
				relevent_activity = True
		if not relevent_activity:
			return HttpResponse(f"Process Instance: not in update address stage")

		url = f"https://camunda.dca.arungas.com/engine-rest/process-instance/{pi_id}/variables?deserializeValues=false"
		self.variables = requests.get(url).json()
		if self.variables.get('camunda_address_updated', {}).get('value'):
			return HttpResponse(
				f"Address Already Filled By Customer {json.loads(self.variables.get('address_json', {}).get('value', {}))}")
		return super().dispatch(request, *args, **kwargs)

	def get_object(self, queryset=None):
		try:
			obj = UjjwalaV2Application.objects.get(
				pk=self.variables.get('application_id').get('value'))
		except:
			raise Http404(
				"No application with id: {} found.".format(
					self.get_object(self.variables.get('application_id').get('value')))
			)
		return obj

	def get_context_data(self, **kwargs):
		context = super().get_context_data(**kwargs)
		obj = self.get_object()
		context.update({
			"obj": obj,
			"old_address_json": self.variables['old_address_json'] if self.kwargs.get('message_source') == 'STAFF' else {}
		})
		return context

	def get_form_kwargs(self):
		kwargs = super().get_form_kwargs()
		# To Be Fixed In Embedded Form
		kwargs['initial'] = json.loads(self.variables['address_json']['value']) if self.kwargs.get(
			'message_source') == 'STAFF' else {}
		return kwargs

	def form_valid(self, form):
		data = form.clean()
		if self.variables.get('address_change_source'):
			address_change_source = self.variables.get('address_change_source').get('value', '')
		else:
			address_change_source = 'PREINSPECTION'

		url = f"https://camunda.dca.arungas.com/engine-rest/message"
		res = requests.post(url, json={
			"messageName": "Message_review_addressnew_address_received" \
				if address_change_source == 'BEFORE_EKYC' else 'Message_new_address_received',
			'processInstanceId': self.kwargs.get('process_instance_id'),
			"processVariables": {
				"old_address_json": {"value": json.dumps(self.variables.get('address_json').get('value')), "type": "String"},
				"address_json": {"value": json.dumps(data['address_json']), "type": "String"},
				"message_source": {"value": f"{self.kwargs.get('message_source')}", "type": "String"},
				"agent": {"value": f"{self.kwargs.get('agent', '').replace('+', ' ')}", "type": "String"},
				"camunda_address_updated": {"value": True, "type": "Boolean"}
			}
		})
		res.raise_for_status()
		return render(
			self.request,
			"ujjwala/response.html",
			{
				"heading": "Update Address",
				"message": "Address Updated Successfully"
			}
		)


class MainMenuGridMenuView(TemplateView):
	template_name = 'ujjwala/grid_menu.html'

	def get_context_data(self, **kwargs):
		context = super().get_context_data(**kwargs)

		menu_items = [
			{
				"name": "Search Status",
				"icon": "fa fa-search",
				"url": reverse("ujjwala:application_status_search"),
			},
			{
				"name": "Share Form Link",
				"icon": "fa-share-square",
				"url": reverse("ujjwala:share_web_form_link"),
			},
		]

		if can_process_change_cylinder_request(get_current_user()):
			menu_items.append(
				{
					"name": "Change Cylinder",
					"icon": "fa fa-exchange",
					"url": reverse("ujjwala:change_cylinder_request_list"),
				}
			)

		context.update({
			"menu": {
				"name": "Main Menu",
				"items": menu_items
			}
		})
		return context


class PreInspectionGridMenuView(TemplateView):
	template_name = 'ujjwala/grid_menu.html'

	def get_context_data(self, **kwargs):
		context = super().get_context_data(**kwargs)

		menu = {
			"name": "Suraksha Drill/Pre-Inspection",
			"items": [
				{
					"name": "List",
					"icon": "fa-file-text",
					"url": reverse("ujjwala:index"),
				},
				{
					"name": "Start New",
					"icon": "fa fa-shield",
					"url": reverse("ujjwala:pre_inspection_create"),
				},
			]
		}

		context.update({
			"menu": menu
		})
		return context


class DisbursementGridMenuView(TemplateView):
	template_name = 'ujjwala/grid_menu.html'

	def get_context_data(self, **kwargs):
		context = super().get_context_data(**kwargs)

		menu = {
			"name": "Disbursement",
			"items": [
				{
					"name": "Applicant Walk-In",
					"icon": "fa-file-text",
					"url": reverse("ujjwala:connection_disbursement_list"),
				},
				{
					"name": "Social Media Updates",
					"icon": "fa-file-text",
					"url": reverse("ujjwala:connection_disbursement_social_media_updates_list"),
				},
				{
					"name": "Material Delivery",
					"icon": "fa-file-text",
					"url": reverse("ujjwala:connection_disbursement_material_delivery_list"),
				},
			]
		}

		context.update({
			"menu": menu
		})
		return context


class InstallationGridMenuView(TemplateView):
	template_name = 'ujjwala/grid_menu.html'

	def get_context_data(self, **kwargs):
		context = super().get_context_data(**kwargs)

		menu = {
			"name": "Installation",
			"items": [
				{
					"name": "List",
					"icon": "fa-file-text",
					"url": reverse("ujjwala:index"),
				},
				{
					"name": "Review List",
					"icon": "fa-file-text",
					"url": reverse("ujjwala:pre_inspection_create"),
				},
			]
		}

		context.update({
			"menu": menu
		})
		return context


class ReviewGridMenuView(TemplateView):
	template_name = 'ujjwala/grid_menu.html'

	def get_context_data(self, **kwargs):
		context = super().get_context_data(**kwargs)
		menu_items = []
		user = get_current_user()

		if is_member_of_disbursement_drive(user):
			if can_review_disbursement_form_abc_permission(user):
				menu_items.append({
					"name": "Accept Legal Documents",
					"icon": "fa-file-text",
					"url": reverse("ujjwala:connection_disbursement_review_form_abc_list"),
				})
			menu_items.append({
				"name": "SV Label Print",
				"icon": "fa-file-text",
				"url": reverse("ujjwala:connection_disbursement_sv_label_print_list"),
			})

		if is_member_of_reviewer_group(user):
			menu_items.append({
				"name": "Audit Application",
				"icon": "fa fa-pencil",
				"url": reverse("ujjwala:ujjwala_application_audit_list"),
			})
			menu_items.append({
				"name": "Address",
				"icon": "fa fa-map-marker",
				"url": reverse("ujjwala:address_review_list"),
			})
			menu_items.append({
				"name": "Form A B C",
				"icon": "fa-sticky-note",
				"url": reverse("ujjwala:review_form_abc_list"),
			})
			menu_items.append({
				"name": "Installation",
				"icon": "fa fa-wrench",
				"url": reverse("ujjwala:installation_review_list"),
			})

		context.update({
			"menu": {
				"name": "Review",
				"items": menu_items
			}
		})
		return context
