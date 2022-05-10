import io
import zipfile
from datetime import datetime

import django_filters
import magic
import requests
from django.conf import settings
from django.http import JsonResponse, HttpResponse, HttpRequest
from django.template import loader
from django.urls import reverse
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response

from . import models
from .enums import UjjwalaV2ApplicationStatus, RoboSdmsDedeupStatusEnum, UjjwalaApplicationDocumentsEnum, \
    FamilyMemberRelationEnum, ResidentialStatusEnum, MaritalStatusEnum, ManualOperationCodeEnum
from .forms import ApplicationRejected
from .models import UjjwalaV2Application, FamilyMembers
from .serializers import UjjwalaV2ApplicationSerializer
from .ujjwala_functions import download_ujjwala_documents, get_salutation, download_pre_installation_documents


class CustomPagePagination(PageNumberPagination):
    page_size_query_param = 'page_size'
    page_size = 50


class UjjwalaApplicationAPIViewSet(viewsets.ModelViewSet):
    queryset = models.UjjwalaV2Application.objects.all()
    serializer_class = UjjwalaV2ApplicationSerializer
    filter_backends = [django_filters.rest_framework.DjangoFilterBackend]
    filterset_fields = ['id', 'status']
    ordering_fields = '__all__'
    pagination_class = CustomPagePagination


    @action(methods=['get'], detail=False, url_path='get_work_items_for_doc_upload')
    def get_work_items_for_doc_upload(self, request: HttpRequest, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())
        # queryset.filter(status=UjjwalaV2ApplicationStatus.EKYC_ACCEPTED)
        page = self.paginate_queryset(queryset)
        return self.get_paginated_response([
            {
                "payload": {
                    "application_id": application.pk,
                    "consumer_id": application.consumer_id
                }
            } for application in page
        ])

    @action(methods=['post'], detail=True, url_path='update_legal_doc_status')
    def update_legal_doc_status(self, request: HttpRequest, *args, **kwargs):
        application: UjjwalaV2Application = self.get_object()
        if application.status == UjjwalaV2ApplicationStatus.EKYC_ACCEPTED:
            status = request.data.get('status')
            message = request.data.get('message')
            application.legal_documents_upload(description="{} {}".format(status, message))
            application.save()
        return HttpResponse('OK')


    @action(methods=['post'], detail=True, url_path='update_omc_and_nic_status')
    def update_omc_and_nic_status(self, request: HttpRequest, *args, **kwargs):
        application: UjjwalaV2Application = self.get_object()
        if application.status == UjjwalaV2ApplicationStatus.LEGAL_DOCUMENTS_UPLOAD:
            # request.data.get('OMC Status') == 'OMC Cleared'
            # request.data.get('OMC Status') == 'OMC Reject'
            pass
        if application.status == UjjwalaV2ApplicationStatus.OMC_CLEARED:
            pass
        return HttpResponse('OK')


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
            status__in=(
                UjjwalaV2ApplicationStatus.DOCUMENTS_UPLOADED,
                UjjwalaV2ApplicationStatus.EKYC_ACCEPTED,
                UjjwalaV2ApplicationStatus.LEGAL_DOCUMENTS_UPLOAD
            ),
            robo_sdms_dedup=RoboSdmsDedeupStatusEnum.NOT_PROCESSED
        ).exclude(version='V1').order_by('-id')

        return JsonResponse([
            {
                'id': record.id,
                'family_members': [{
                    'id': member.id,
                    'uid': member.uid_no
                } for member in record.family_members.all()]
            } for record in aadhar_list
        ], safe=False)

    @action(methods=['get'], detail=False, url_path='get_ekyc_accepted_list')
    def get_ekyc_accepted_list(self, request, *args, **kwargs):
        aadhar_list = UjjwalaV2Application.objects.filter(
            status__in=UjjwalaV2ApplicationStatus.EKYC_ACCEPTED,
            consumer_id=None,
            robo_sdms_dedup=RoboSdmsDedeupStatusEnum.PROCESSED_AND_UNIQUE
        ).exclude(version='V1').order_by('-id')

        return JsonResponse([
            {
                'id': record.id,
                'uid': record.family_members.objects.filter(relation=FamilyMemberRelationEnum.SELF).first().uid_no
            } for record in aadhar_list
        ], safe=False)

    @action(methods=['post'], detail=False, url_path='update_consumer_id')
    def update_result(self, request, *args, **kwargs):
        application = UjjwalaV2Application.objects.filter(pk=request.data.get('id')).first()
        application.consumer_id = request.data.get('consumer_id')
        application.save()
        return HttpResponse('OK')

    @action(methods=['post'], detail=False, url_path='update_result')
    def update_result(self, request, *args, **kwargs):
        record_valid = True
        invalid_result = {}
        invalid_result_relation = ''
        family_member_obj = {}

        consumer_id = ''

        for member in request.data['family_members']:
            try:
                family_member_obj = FamilyMembers.objects.get(pk=member.get('id'))
                family_member_obj.uid_check_result = member['result']

                family_member_obj.save()

                if request.data.get('alert', ''):
                    if 'SBL-BPR-00131' in request.data.get('alert'):
                        continue
                    else:
                        application_obj = UjjwalaV2Application.objects.get(pk=request.data.get('id'))
                        application_obj.status = UjjwalaV2ApplicationStatus.PROCESS_MANUAL
                        application_obj.save()
                        return HttpResponse('OK')

                if not member['result'].get('distributor_name', ''):
                    continue
                else:
                    if 'arun indane' not in member['result'].get('distributor_name').lower():
                        record_valid = False
                        invalid_result = member['result']
                        invalid_result_relation = family_member_obj.relation
            except FamilyMembers.DoesNotExist:
                pass

        application_obj = UjjwalaV2Application.objects.get(pk=request.data.get('id'))

        if not record_valid:
            try:
                form = ApplicationRejected(data={
                    'rejected_reason': 'CONNECTION_ALREADY_EXIST',
                    'description': "{} {} {} {}".format(
                        invalid_result_relation,
                        invalid_result['distributor_name'], invalid_result['consumer_id'],
                        invalid_result['contact_address']
                    )})
                form.is_valid()
                application_obj.robo_sdms_dedup = RoboSdmsDedeupStatusEnum.PROCESSED_AND_DUPLICATE
                if application_obj.status == 'DOCUMENTS_UPLOADED':
                    application_obj.application_rejected(**form.cleaned_data)
                    application_obj.event_ioc_dedupe_reject_channel_whatsapp()
            except Exception as e:
                print(e)
                pass
        else:
            self_member = FamilyMembers
            application_obj.robo_sdms_dedup = RoboSdmsDedeupStatusEnum.PROCESSED_AND_UNIQUE
            application_obj.event_invite_for_ekyc_channel_whatsapp()

        application_obj.save()
        return HttpResponse('OK')

    def perform_create(self, serializer):
        application = serializer.save()
        if getattr(self.request, "PERFORM_SUBMIT", False):
            try:
                application.event_submit_channel_whatsapp()
            except:
                pass

        return application

    @action(methods=['get'], detail=True, url_path='download_ujjwala_legal_docs')
    def download_ujjwala_legal_docs(self, request, *args, **kwargs):
        obj = self.get_object()
        return download_ujjwala_documents(obj)

    @action(methods=['get'], detail=True, url_path='download_pre_inspection_docs')
    def download_pre_inspection_docs(self, request, *args, **kwargs):
        obj = self.get_object()
        return download_pre_installation_documents(obj)


    @action(methods=['post'], detail=True, url_path='validate_contacts')
    def validate_contacts(self, request: HttpRequest, *args, **kwargs):
        application = self.get_object()
        # To Check State If needs to be skipped

        contacts_table = request.data.get('contacts_table')
        contacts_list = {}

        primary_record = [i for i in contacts_table if i['Primary'] == 'Y']
        if not primary_record:
            application.robo_manual_legal_documents_upload(
                description='No primary record found',
                manual_operation_code=ManualOperationCodeEnum.NO_PRIMARY_RECORD
            )
            application.save()
            contacts_list.update({
                "action": "skip",
                "code": ManualOperationCodeEnum.NO_PRIMARY_RECORD
            })
            return JsonResponse(contacts_list)

        # Probably EKYC not done
        primary_record = primary_record[0]

        uid_record = [
            i for i in primary_record['identities'] \
            if i["Identity Method"] == "Aadhaar(UID)"
        ]
        if not uid_record:
            application.robo_manual_legal_documents_upload(
                description='UID does not exist',
                manual_operation_code=ManualOperationCodeEnum.NO_UID_FOUND
            )
            application.save()
            contacts_list.update({
                "action": "skip",
                "code": ManualOperationCodeEnum.NO_UID_FOUND
            })
            return JsonResponse(contacts_list)
        # reason need to be pushed, along with reason code (store in db) for query incase
        # robot is expanded to handle other user case
        uid_record = uid_record[0]

        identity_num = uid_record["Identity Num"].replace('x', '')
        uid_last_4_digits = identity_num.strip()
        applicant = application.family_members.filter(uid_no__endswith=uid_last_4_digits)
        if not applicant:
            # Applicant UID not matching SDMS
            application.robo_manual_legal_documents_upload(
                description='Applicant UID not matching SDMS',
                manual_operation_code=ManualOperationCodeEnum.UID_MISMATCH_SDMS
            )
            application.save()

            contacts_list.update({
                "action": "skip",
                "code": ManualOperationCodeEnum.UID_MISMATCH_SDMS
            })
            return JsonResponse(contacts_list)

        applicant = applicant.first()

        if applicant.relation != 'SELF':
            if application.family_members.exclude(id=applicant.id).count() == 1:
                other_member = application.family_members.exclude(id=applicant.id).first()
                other_member.relation = applicant.relation
                applicant.relation = 'SELF'
                other_member.save()
                applicant.save()
            else:
                # Applicant UID Relation Mismatch
                application.robo_manual_legal_documents_upload(
                    description='Applicant UID Relation Mismatch',
                    manual_operation_code=ManualOperationCodeEnum.UID_MISMATCH_SDMS
                )
                application.save()
                contacts_list.update({
                    "action": "skip",
                    "code": ManualOperationCodeEnum.UID_MISMATCH_SDMS
                })
                return JsonResponse(contacts_list)

        try:
            f_name, l_name = applicant.name.split(' ', 1)
        except ValueError:
            f_name, l_name = applicant.name, '.'

        url = request.build_absolute_uri(
            '/ujjwala/ujjwala-application/{}/download_ujjwala_legal_docs/'.format(
            application.pk
            )
        )

        contacts_list.update({
            "application_id": application.id,
            "application_doc_url": request.build_absolute_uri(url),
            "consumer_id": application.consumer_id,
            "primary_applicant": {
                "Salutation": get_salutation(applicant),
                "First Name": f_name.title(),
                "Last Name": l_name.title(),
                "Gender": applicant.get_gender(),
                "DOB": applicant.dob.strftime("%d-%b-%Y"),
                "Migrated": "Y",
                "Relationship": "SELF",
                "Category": primary_record.get('Category') or "Gen",
                "identities": [{
                    "Identity Type": "INTERNAL-UJJWALA",
                    "Identity Method": "ANNEXURE 1",
                    "Identity Num": applicant.uid_no[-4:],
                },
                    {
                        "Identity Type": "INTERNAL-UJJWALA",
                        "Identity Method": "14 Point Exclusion Declaration",
                        "Identity Num": applicant.uid_no[-4:],
                    }]
            }
        })

        family_members = application.family_members.exclude(uid_no__endswith=uid_last_4_digits)

        family_members_list = []

        for family_member in family_members:
            try:
                f_name, l_name = family_member.name.split(' ', 1)
            except ValueError:
                f_name, l_name = family_member.name, '.'

            family_members_list.append({
                "Salutation": get_salutation(family_member),
                "First Name": f_name.title(),
                "Last Name": l_name.title(),
                "Gender": family_member.get_gender(),
                "DOB": family_member.dob.strftime("%d-%b-%Y"),
                "Migrated": "Y",
                "Relationship": family_member.relation.upper(),
                "Category": primary_record.get('Category') or "Gen",
                "identities": [{
                    "Identity Type": "POA-POI",
                    "Identity Method": "Aadhaar(UID)",
                    "Identity Num": family_member.uid_no,
                }],
            })
        contacts_list.update({
            "others": family_members_list,
            "action": "upload",
            "code": "OK"
        })
        return JsonResponse(contacts_list)


    @action(methods=['post'], detail=True, url_path='robo_got_error_alert')
    def robo_got_error_alert(self, request: HttpRequest, *args, **kwargs):
        application: UjjwalaV2Application = self.get_object()
        application.do_manual_operations(
            description=request.data.get('message'),
            manual_operation_code=ManualOperationCodeEnum.ROBO_GOT_ERROR_ALERT
        )
        application.save()
        return HttpResponse('OK')
