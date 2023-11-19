from django.http import HttpRequest, HttpResponse, JsonResponse
from django.utils import timezone
from rest_framework import viewsets
from rest_framework.decorators import action

from ujjwala.enums import UjjwalaV2ApplicationStatus, SVSDMSStatusEnum
from ujjwala.ujjwala_functions import omc_nic_status_update


class UjjwalaApplicationSVViewSet(viewsets.ViewSet):
	@action(methods=['post'], detail=True, url_path='sv_document_status')
	def sv_document_status(self, request: HttpRequest, *args, **kwargs):
		from ujjwala.models import UjjwalaV2Application, ConnectionDisbursementInvitation

		application: UjjwalaV2Application = UjjwalaV2Application.objects.get(pk=kwargs.get('pk'))
		invitation: ConnectionDisbursementInvitation = application.connection_disbursement.invitation.filter(
			status='VALID').first()
		invitation.sv_sdms_status = request.data.get('status')
		invitation.save()
		return JsonResponse({
			"status": "OK"
		})
