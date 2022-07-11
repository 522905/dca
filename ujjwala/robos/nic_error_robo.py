import django_filters
from django.http import HttpRequest, JsonResponse, HttpResponse
from django.utils import timezone
from rest_framework import viewsets
from rest_framework.decorators import action

from ujjwala import models
from ujjwala.enums import UjjwalaV2ApplicationStatus, MaritalStatusEnum
from ujjwala.models import UjjwalaV2Application
from ujjwala.serializers import UjjwalaV2ApplicationSerializer
from ujjwala.viewsets import CustomPagePagination


class UjjwalaApplicationNicErrorRobotAPIViewSet(viewsets.ModelViewSet):
    queryset = models.UjjwalaV2Application.objects.filter(
        consumer_id__isnull=False
    ).exclude(marital_status__in=[
        MaritalStatusEnum.DIVORCED, MaritalStatusEnum.WIDOW
    ])

    serializer_class = UjjwalaV2ApplicationSerializer
    filter_backends = [django_filters.rest_framework.DjangoFilterBackend]
    filterset_fields = ['id', 'status']
    ordering_fields = '__all__'


    @action(methods=['get'], detail=False, url_path='get_consumer_records_to_update_address')
    def get_consumer_records_to_update_address(self, request: HttpRequest, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())
        queryset = queryset.filter(
            status=UjjwalaV2ApplicationStatus.NIC_ERROR_ADDRESS_ACCEPTED
        )
        return JsonResponse([
            {
                "payload": {
                    "application_id": application.pk,
                    "consumer_id": application.consumer_id,
                    "address": application.get_address_for_sdms_upload()
                }
            } for application in queryset[:1]
        ], safe=False)

    @action(methods=['post'], detail=True, url_path='update_consumer_id')
    def update_consumer_id_after_new_address_seedg(self, request: HttpRequest, *args, **kwargs):
        application: UjjwalaV2Application = self.get_object()
        application.sdms_last_updated_on = timezone.now()

        consumer_id = request.data.get('consumer_id')
        application.transition_create_new_relation_after_nic_error_insufficent_address(consumer_id=consumer_id)
        application.save()

        return HttpResponse('OK')
