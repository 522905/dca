from django.http import HttpRequest, HttpResponse, JsonResponse
from django.utils import timezone
from rest_framework import viewsets
from rest_framework.decorators import action

from ujjwala.enums import UjjwalaV2ApplicationStatus
from ujjwala.ujjwala_functions import omc_nic_status_update


class UjjwalaApplicationNicViewSet(viewsets.ViewSet):
	# SDMS Relation Cancelled
	@action(methods=['post'], detail=True, url_path='sdms_relation_cancelled')
	def sdms_relation_cancelled(self, request: HttpRequest, *args, **kwargs):
		from ujjwala.models import UjjwalaV2Application

		application: UjjwalaV2Application = UjjwalaV2Application.objects.get(pk=kwargs.get('pk'))
		application.sdms_last_updated_on = timezone.now()
		application.transition_nic_cleared_sdms_relation_cancelled()
		application.save()

		return HttpResponse('OK')

	@action(methods=['get'], detail=True, url_path='is_sdms_relation_cancelled')
	def is_sdms_relation_cancelled(self, request: HttpRequest, *args, **kwargs):
		from ujjwala.models import UjjwalaV2Application

		application: UjjwalaV2Application = UjjwalaV2Application.objects.get(pk=kwargs.get('pk'))
		return JsonResponse({
			"cancelled": application.status == UjjwalaV2ApplicationStatus.NIC_CLEARED_SDMS_RELATION_CANCELLED
		})

	@action(methods=['post'], detail=True, url_path='sdms_relation_recreated')
	def sdms_relation_recreated(self, request: HttpRequest, *args, **kwargs):
		from ujjwala.models import UjjwalaV2Application

		application: UjjwalaV2Application = UjjwalaV2Application.objects.get(pk=kwargs.get('pk'))
		application.transition_sdms_relation_cancelled_to_legal_documents_upload()
		application.save()

		application = omc_nic_status_update(application, request)
		return JsonResponse({
			"status": application.status
		})
