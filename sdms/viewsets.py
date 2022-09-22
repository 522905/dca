from rest_framework import viewsets
from rest_framework.decorators import action

from .models import SdmsFamilyMemberRecord
from .serializers import SdmsFamilyMemberRecordSerializer
from django.http import JsonResponse
from ujjwala.models import UjjwalaV2Application
from rest_framework.pagination import PageNumberPagination

ids = []


class CustomPagePagination(PageNumberPagination):
    page_size_query_param = 'page_size'
    page_size = 50


class FamilyMemberAPIViewSet(viewsets.ModelViewSet):
    queryset = SdmsFamilyMemberRecord.objects.all()
    serializer_class = SdmsFamilyMemberRecordSerializer
    pagination_class = CustomPagePagination

    @action(methods=['get'], detail=False, url_path='get_workitems_to_read')
    def add(self, request, *args, **kwargs):
        applications = UjjwalaV2Application.objects.filter(
            id__in=ids
        ).exclude(
            id__in=SdmsFamilyMemberRecord.objects.all().values_list("dca_id", flat=True)
        ).value_list('dca_id', 'consumer_id')

        page = self.paginate_queryset(applications)

        return self.get_paginated_response([
            {
                "payload": {
                    'dca_id': record.dca_id,
                    'consumer_id': record.consumer_id
                }
            } for record in page
        ])

    @action(methods=['post'], detail=False, url_path='add')
    def add(self, request, *args, **kwargs):
        consumer_id = request.data['consumer_id']
        dca_id = request.data['dca_id']
        for fm in request.data['members']:
            SdmsFamilyMemberRecord.objects.create(
                consumer_id=consumer_id,
                dca_id=dca_id,
                relation=fm['Relationship'],
                first_name=fm['First Name'],
                last_name=fm['Last Name']
            )
        return JsonResponse({'msg': 'ok'})
