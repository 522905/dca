from rest_framework import viewsets

from .models import SdmsFamilyMemberRecord
from .serializers import SdmsFamilyMemberRecordSerializer
from ujjwala.models import UjjwalaV2Application
from rest_framework.decorators import action


class FamilyMemberAPIViewSet(viewsets.ModelViewSet):
    queryset = SdmsFamilyMemberRecord.objects.all()
    serializer_class = SdmsFamilyMemberRecordSerializer

    @action(methods=['post'], detail=True, url_path='add')
    def add(self, request, *args, **kwargs):
        consumer_id = request.data['consumer_id']
        for fm in request.data['members']:
            SdmsFamilyMemberRecord.objects.create(
                consumer_id=consumer_id,
                relation=fm['Relationship'],
                first_name=fm['First Name'],
                last_name=fm['Last Name']
            )
