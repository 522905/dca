from django.http import HttpResponse
from rest_framework import viewsets
from rest_framework.decorators import action

from ujjwala.models import UjjwalaV2Application
from vicidial.functions import update_lead_in_ujjwala_welcome, send_new_connection_application_sms_link, \
	send_ujjwala_application_status_sms_link, send_ujjwala_application_sms_link, \
	send_non_ujjwala_applicant_status_sms_link


class ViciDialViewSet(viewsets.ViewSet):

	@action(methods=['get'], detail=False, url_path='inbound_call_manage')
	def inbound_call_manage(self, request, *args, **kwargs):
		contact_mobile = request.GET.get('contact_mobile')
		phone_code = request.GET.get('phone_code')
		inbound_call_user_id = 87
		host = f"{request.scheme}://{request.get_host()}"
		if phone_code == '1':
			application = UjjwalaV2Application.objects.filter(contact_mobile=contact_mobile).first()
			if application:
				send_ujjwala_application_status_sms_link(contact_mobile, application.id, host)
			else:
				send_ujjwala_application_sms_link(contact_mobile, inbound_call_user_id, host)
				update_lead_in_ujjwala_welcome(contact_mobile)
		elif phone_code == '2':
			application = UjjwalaV2Application.objects.filter(contact_mobile=contact_mobile).first()
			if application:
				send_ujjwala_application_status_sms_link(contact_mobile, application.id, host)
			else:
				send_non_ujjwala_applicant_status_sms_link(contact_mobile, inbound_call_user_id, host)
		elif phone_code == '3':
			send_new_connection_application_sms_link(contact_mobile, host)
		return HttpResponse("ok")

	# @action(methods=['get'], detail=False, url_path='offer_call_manage')
	# def offer_call_manage(self, request, *args, **kwargs):
	# 	contact_mobile = request.GET.get('contact_mobile')
	# 	update_lead_in_out1005_campaign(contact_mobile)
	# 	send_offer_whatsapp_link(contact_mobile)
	# 	return HttpResponse("ok")
	#
	# @action(methods=['get'], detail=False, url_path='get_payment_variables')
	# def get_payment_variables(self, request, *args, **kwargs):
	# 	application_id = request.GET.get('application_id')
	# 	force_main_branch = request.GET.get('force_main_branch', False)
	# 	result = fetch_payment_profile_variables(application_id, force_main_branch=force_main_branch)
	# 	return JsonResponse({'result': result}, safe=False)
