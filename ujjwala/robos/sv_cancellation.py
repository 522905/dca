import datetime
import re

from django.db.models import Q
from django.db.models import Case, When, Value, IntegerField
from django.http import JsonResponse, HttpResponse
from rest_framework import viewsets
from rest_framework.decorators import action

from ujjwala.enums import UjjwalaV2ApplicationStatus, RoboSdmsDedeupStatusEnum, PreInspectionStatusEnum, \
	FamilyMemberRelationEnum
from ujjwala.models import UjjwalaV2Application, ConnectionDisbursement, ConnectionDisbursementInvitation
from ujjwala.ujjwala_functions import get_salutation


class SvCancellationViewSet(viewsets.ViewSet):
	def list(self, request):
		queryset = ConnectionDisbursementInvitation.objects.filter(
				status='VALID', sv_uploaded_on__date=datetime.datetime.today().date()
			).exclude(parent__status='MATERIAL_DELIVERED')
		return JsonResponse([{
			'payload': {
				'connection_disbursement_id': i.parent_id, 'consumer_id': i.parent.parent.consumer_id, 'invite_id': i.id,
				'name': i.parent.parent.name, 'application_id': i.parent.parent.id
			}
		} for i in queryset], safe=False)


	@action(methods=['get'], detail=False, url_path='is_cancelled')
	def is_cancelled(self, request, *args, **kwargs):
		invite = ConnectionDisbursementInvitation.objects.get(id=request.GET.get('invite_id'))
		return JsonResponse({'is_cancelled': invite.status!='VALID'})

	@action(methods=['post'], detail=False, url_path='mark_as_cancelled')
	def mark_as_cancelled(self, request, *args, **kwargs):
		invite = ConnectionDisbursementInvitation.objects.get(id=request.data.get('invite_id'))
		invite.status = 'CANCELLED'
		invite.save()
		return HttpResponse("Ok")
