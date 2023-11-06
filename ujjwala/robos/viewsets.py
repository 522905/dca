from django.http import HttpRequest, HttpResponse
from django.utils import timezone
from rest_framework import viewsets
from rest_framework.decorators import action


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
