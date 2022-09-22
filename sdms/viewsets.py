from rest_framework import viewsets
from rest_framework.decorators import action

from .models import SdmsFamilyMemberRecord
from .serializers import SdmsFamilyMemberRecordSerializer
from django.http import JsonResponse


class FamilyMemberAPIViewSet(viewsets.ModelViewSet):
    queryset = SdmsFamilyMemberRecord.objects.all()
    serializer_class = SdmsFamilyMemberRecordSerializer




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
