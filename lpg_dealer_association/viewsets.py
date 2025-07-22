from django.http import HttpResponse
from rest_framework import viewsets
from rest_framework.decorators import action

from lpg_dealer_association.functions import send_response_template_phone_code_1_sms


class ViciDialViewSet(viewsets.ViewSet):

	@action(methods=['get'], detail=False, url_path='inbound_call_manage')
	def inbound_call_manage(self, request, *args, **kwargs):
		contact_mobile = request.GET.get('contact_mobile')
		phone_code = request.GET.get('phone_code')
		if phone_code == '1':
			send_response_template_phone_code_1_sms(contact_mobile)

		return HttpResponse("ok")
