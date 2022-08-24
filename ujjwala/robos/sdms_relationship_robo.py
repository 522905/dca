from django.db.models import Q
from django.http import JsonResponse, HttpResponse
from rest_framework import viewsets
from rest_framework.decorators import action

from ujjwala.enums import UjjwalaV2ApplicationStatus, RoboSdmsDedeupStatusEnum, PreInspectionStatusEnum, \
	FamilyMemberRelationEnum
from ujjwala.models import UjjwalaV2Application


class UjjwalaApplicationSdmsRelationshipViewSet(viewsets.ViewSet):
    @action(methods=['get'], detail=False, url_path='get_records_for_new_relationship')
    def get_records_for_new_relationship(self, request, *args, **kwargs):
        record_list = UjjwalaV2Application.objects.filter(
            Q(status=UjjwalaV2ApplicationStatus.DOCUMENTS_UPLOADED) &
            Q(robo_sdms_dedup=RoboSdmsDedeupStatusEnum.PROCESSED_AND_UNIQUE) &
            Q(pre_inspection__status=PreInspectionStatusEnum.ACCEPTED)
        ).exclude(address_json__isnull=True).order_by("id")

        data = []

        for record in record_list:
            try:
                address = record.get_address_for_sdms_upload()
            except:
                continue

            self_fm = record.family_members.get(relation=FamilyMemberRelationEnum.SELF)
            self_name_split = record.name.split(" ")
            data.append({
                "id": record.id,
                "Salutation": "Mrs.",
                "First Name": self_name_split[0],
                "Last Name": ' '.join(self_name_split[1:]) if len(self_name_split) > 1 else '.',
                "Gender": "Female",
                "DOB": self_fm.dob,
                "Migrated": "Y",
                "Relationship": "SELF",
                "phone": record.contact_mobile,
                "identities": [{
                    "Identity Type": "POA-POI",
                    "Identity Method": "Aadhaar(UID)",
                    "Identity Num": self_fm.uid_no
                }],
                'consumer_id': record.consumer_id,
                "address": {
                    "address": address['addr_str'],
                    "landmark": record.address_json.get('landmark', 'NA'),
                    "pincode": address['pincode']
                }
            })
        return JsonResponse(data, safe=False)

    @action(methods=['post'], detail=False, url_path='update_new_relationship')
    def update_new_relationship(self, request, *args, **kwargs):
        application = UjjwalaV2Application.objects.get(id=request.data.get('id'))
        uid_check_result = request.data.get('uid_check_result')
        sdms_mobile_number = uid_check_result.get('sdms_mobile_number', '')
        self_fm = application.family_members.get(relation=FamilyMemberRelationEnum.SELF)
        self_fm.uid_check_result = uid_check_result
        self_fm.save()

        application.sdms_mobile_number = sdms_mobile_number
        application.consumer_id = request.data.get('consumer_id')
        application.manual_operation_code = "ROBO_STARTED_RELATION"

        application.ekyc_accepted_or_rejected(
            sdms_mobile_number=sdms_mobile_number,
            description="Bot Created New Relation"
        )
        application.save()

        return HttpResponse("Ok")


