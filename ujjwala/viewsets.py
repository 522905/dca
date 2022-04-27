from django.http import JsonResponse, HttpResponse
from django.urls import reverse
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from . import models
from .enums import UjjwalaV2ApplicationStatus
from .forms import ApplicationRejected
from .models import UjjwalaV2Application, FamilyMembers
from .serializers import UjjwalaV2ApplicationSerializer


class UjjwalaApplicationViewSet(viewsets.ModelViewSet):
    queryset = models.UjjwalaV2Application.objects.all()
    serializer_class = UjjwalaV2ApplicationSerializer

    @action(methods=['post'], detail=False, url_path='wf')
    def web_form(self, request, *args, **kwargs):
        request.PERFORM_SUBMIT = True
        return super().create(request, *args, **kwargs)

    @action(methods=['get'], detail=False, url_path='check_phone')
    def check_phone(self, request, *args, **kwargs):
        contact_mobile = request.GET.get('contact_mobile')

        application = UjjwalaV2Application.objects.objects().filter(mobile=contact_mobile)

        if application.exists():
            status_url = reverse('application_status', kwargs={'pk': application.first().pk})
            return JsonResponse({
                "status": False,
                "application_url": request.build_absolute_uri(status_url)
            })

        return JsonResponse({
            "status": True
        })

    @action(methods=['get'], detail=False, url_path='get_aadhar_list')
    def get_aadhar_list(self, request, *args, **kwargs):
        aadhar_list = UjjwalaV2Application.objects.filter(
            version='V3', status=UjjwalaV2ApplicationStatus.DOCUMENTS_UPLOADED, sdms_dedup=False
        ).order_by('-created_on')

        return JsonResponse([
            {
                'id': record.id,
                'family_members': [{
                    'id': member.id,
                    'uid': member.uid_no
                } for member in record.family_members.all()]
            } for record in aadhar_list[:49]
        ], safe=False)

    @action(methods=['post'], detail=False, url_path='update_result')
    def update_result(self, request, *args, **kwargs):
        record_valid = True
        invalid_result = {}

        for member in request.data['family_members']:
            try:
                member_obj = FamilyMembers.objects.get(pk=member.get('id'))
                member_obj.uid_check_result = member['result']
                member_obj.save()

                if not member['result'].get('distributor_name', ''):
                    continue
                else:
                    if 'arun' not in member['result'].get('distributor_name').lower():
                        record_valid = False
                        invalid_result = member['result']
            except FamilyMembers.DoesNotExist:
                pass

        member_obj = UjjwalaV2Application.objects.get(pk=request.data.get('id'))

        if not record_valid:
            try:
                form = ApplicationRejected(data={
                    'rejected_reason': 'CONNECTION_ALREADY_EXIST',
                    'description': "{} {} {}".format(
                        invalid_result['distributor_name'], invalid_result['consumer_id'],
                        invalid_result['contact_address']
                    )})
                form.is_valid()
                member_obj.application_rejected(**form.cleaned_data)
            except Exception as e:
                print(e)
                pass
        else:
            member_obj.sdms_dedup = True

        member_obj.save()


        return HttpResponse('OK')


    def perform_create(self, serializer):
        application = serializer.save()
        if getattr(self.request, "PERFORM_SUBMIT", False):
            try:
                application.event_submit_channel_whatsapp()
            except:
                pass

        return application
