import datetime

import django_filters
import requests
from django.db.models import Q
from django.http import JsonResponse, HttpResponse, HttpRequest
from django.utils import timezone
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.pagination import PageNumberPagination

from . import models
from .enums import UjjwalaV2ApplicationStatus, RoboSdmsDedeupStatusEnum, FamilyMemberRelationEnum, \
    ManualOperationCodeEnum, MaritalStatusEnum
from .forms import ApplicationRejected
from .models import UjjwalaV2Application, FamilyMembers, ConnectionDisbursement, ConnectionDisbursementDocuments
from .serializers import UjjwalaV2ApplicationSerializer
from .ujjwala_functions import download_ujjwala_documents, get_salutation, \
    download_pre_installation_documents, get_existing_duplicate_applications_detail, \
    download_ujjwala_legal_docs_to_upload, download_ujjwala_physical_legal_docs


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
        queryset = queryset.filter(
            status=UjjwalaV2ApplicationStatus.EKYC_ACCEPTED, consumer_id__isnull=False
        ).exclude(marital_status__in=[
            MaritalStatusEnum.DIVORCED, MaritalStatusEnum.WIDOW
        ])
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
        application.sdms_last_updated_on = timezone.now()
        application.product = request.data.get('product')
        nic_status = request.data.get('nic_status')
        legal_docs_uploaded = request.data.get('legal_docs_uploaded')

        if legal_docs_uploaded and application.status == UjjwalaV2ApplicationStatus.EKYC_ACCEPTED:
            application.legal_documents_upload(description='Status Updated By Bot, Uploaded by unknown person')
        elif not legal_docs_uploaded and application.status == UjjwalaV2ApplicationStatus.LEGAL_DOCUMENTS_UPLOAD:
            application.status == UjjwalaV2ApplicationStatus.EKYC_ACCEPTED

        if application.status == UjjwalaV2ApplicationStatus.LEGAL_DOCUMENTS_UPLOAD:
            if request.data.get('omc_status') == 'OMC Clear':
                application.transition_omc_clear(description="Bot Processed: OMC Clear")
            elif request.data.get('omc_status') == 'OMC Reject':
                application.transition_omc_reject(description="Bot Processed: OMC Reject")
        if application.status == UjjwalaV2ApplicationStatus.OMC_CLEARED and nic_status not in ('Pending', 'Awaited'):
            if nic_status == 'Cleared':
                application.transition_nic_cleared(description="Bot Processed: NIC Cleared")
#            elif nic_status == 'NIC Rejected':
            else:
                application.transition_nic_error(error_code='', description=nic_status)
        application.save()
        return HttpResponse('OK')

    @action(methods=['get'], detail=False, url_path='get_list_to_fetch_omc_nic_status')
    def get_list_to_fetch_omc_nic_status(self, request: HttpRequest, *args, **kwargs):
        aadhar_list = UjjwalaV2Application.objects.filter(
            Q(status=UjjwalaV2ApplicationStatus.LEGAL_DOCUMENTS_UPLOAD) |
            Q(status=UjjwalaV2ApplicationStatus.OMC_CLEARED)
        ).exclude(consumer_id__isnull=True).order_by('id')
#.filter(sdms_last_updated_on__lte=datetime.datetime.today()-datetime.timedelta(hours=6))
#.exclude(version='V1')
#.order_by('-id')
#        aadhar_list = UjjwalaV2Application.objects.filter(id__in=["1273","2120","2534","32","1265","323","76","601","2148","37"]).exclude(consumer_id__isnull=True).order_by('id')
        return JsonResponse([
            {
                'id': record.id,
                'consumer_id': record.consumer_id
            } for record in aadhar_list
        ], safe=False)


class UjjwalaApplicationViewSet(viewsets.ModelViewSet):
    queryset = models.UjjwalaV2Application.objects.all()
    serializer_class = UjjwalaV2ApplicationSerializer

    @action(methods=['post'], detail=False, url_path='wf')
    def web_form(self, request, *args, **kwargs):
        request.PERFORM_SUBMIT = True
        return super().create(request, *args, **kwargs)

    @action(methods=['post'], detail=False, url_path='legal_documents_upload')
    def legal_documents_upload(self, request, *args, **kwargs):
        connection_disbursement_id = request.data.get('connection_disbursement_id')
        documents = request.data.get('documents')

        try:
            connection_disbursement = ConnectionDisbursement.objects.get(id=connection_disbursement_id)

            if connection_disbursement:
                for document in documents:
                    ConnectionDisbursementDocuments.objects.create(
                        parent=connection_disbursement,
                        type=document.get('type'),
                        link=document.get('link')
                    )
                connection_disbursement.transition_legal_documents_uploaded(
                    description="Submitted On: {}".format(timezone.now().strftime('%d-%M-%Y'))
                )
                connection_disbursement.save()
                return JsonResponse({
                    "status": True
                })
        except:
            pass

        return JsonResponse({
            "status": False
        })

    @action(methods=['get'], detail=False, url_path='check_ujjwala_application')
    def check_ujjwala_application(self, request, *args, **kwargs):
        contact_mobile = request.GET.get('contact_mobile')

        application = UjjwalaV2Application.objects.filter(contact_mobile=contact_mobile).first()

        if application:
            return JsonResponse({
                "status": False,
                "date": application.created_on.strftime('%d-%m-%Y'),
                "application": "Ujjwala Application Id: {} {}".format(
                    application.pk, application.name
                ),
                "state": application.status
            })
        else:
            return JsonResponse({
                "status": False
            })

    # @action(methods=['post'], detail=True, url_path='submit_pre_inspection')
    # def submit_pre_inspection(self, request, *args, **kwargs):
    #     obj: UjjwalaV2Application = self.get_object()
    #     serializer = SubmitPreInspectionSerializer(instance=obj, data=request.data, partial=True)
    #     serializer.is_valid(raise_exception=True)
    #     obj.transition_pre_inspection_submit(**serializer.data)
    #     return HttpResponse('Ok')


    @action(methods=['get'], detail=False, url_path='check_phone')
    def dedup_phone_for_new_application(self, request, *args, **kwargs):
        contact_mobile = request.GET.get('contact_mobile')

        applications = UjjwalaV2Application.objects.filter(
            Q(contact_mobile=contact_mobile) |
            Q(uid_linked_mobile=contact_mobile)
        ).order_by('-id')

        if applications:
            # if application.status != 'DOCUMENTS_REUPLOAD':
            # status_url = reverse('application_status', kwargs={'pk': application.first().pk})
            result = {
                "status": False,
            }
            msg = get_existing_duplicate_applications_detail(applications)
            result.update(msg)
            return JsonResponse(result)

            # return JsonResponse({
            #         "status": False,
            #         "msg": "Application Id: {} exist with contact number: {} status: {}".format(
            #             application.pk, contact_mobile, application.status
            #         )
            #     })

        return JsonResponse({
            "status": True,
            "msg": "VALID_APPLICATION",
            "data": {}
        })

    @action(methods=['get'], detail=False, url_path='check_uid')
    def dedup_uid_for_new_application(self, request, *args, **kwargs):
        uid = request.GET.get('uid')
        if uid in ('999999999999', '666666666666'):
            return JsonResponse({
                "status": True,
                "msg": "VALID_APPLICATION",
                "data": {}
            })

        exiting_applications = UjjwalaV2Application.objects.filter(family_members__uid_no=uid).order_by('-id')
        if not exiting_applications.exists():
            return JsonResponse({
                "status": True,
                "msg": "VALID_APPLICATION",
                "data": {}
            })

        result = get_existing_duplicate_applications_detail(exiting_applications)
        result.update({
            "status": False,
        })
        return JsonResponse(result)

    @action(methods=['get'], detail=False, url_path='get_aadhar_list')
    def get_aadhar_list_for_iocl_sdms_dedup(self, request, *args, **kwargs):
        aadhar_list = UjjwalaV2Application.objects.filter(
            status__in=(
                UjjwalaV2ApplicationStatus.DOCUMENTS_UPLOADED,
                UjjwalaV2ApplicationStatus.EKYC_ACCEPTED,
                UjjwalaV2ApplicationStatus.LEGAL_DOCUMENTS_UPLOAD
            ),
            robo_sdms_dedup=RoboSdmsDedeupStatusEnum.NOT_PROCESSED
        ).exclude(family_members__uid_no__in=("0", "1")).order_by('-id')
        #aadhar_list = UjjwalaV2Application.objects.filter(id__in=["1273","2120","2534","32","1265","323","76","601","2148","37"])
        return JsonResponse([
            {
                'id': record.id,
                'family_members': [{
                    'id': member.id,
                    'uid': member.uid_no
                } for member in record.family_members.all()]
            } for record in aadhar_list
        ], safe=False)

    @action(methods=['post'], detail=False, url_path='update_result')
    def update_iocl_sdms_dedup_results(self, request, *args, **kwargs):
        record_valid = True
        invalid_result = {}
        invalid_result_relation = ''
        family_member_obj = {}

        consumer_id = ''
        application_obj = UjjwalaV2Application.objects.get(pk=request.data.get('id'))

        for member in request.data['family_members']:
            try:
                family_member_obj = FamilyMembers.objects.get(pk=member.get('id'))
                if family_member_obj.uid_no in ('999999999999', '666666666666'): continue

                family_member_obj.uid_check_result = member['result']

                family_member_obj.save()

                if request.data.get('alert', ''):
                    if 'SBL-BPR-00131' in request.data.get('alert'):
                        continue
                    else:
                        application_obj.status = UjjwalaV2ApplicationStatus.PROCESS_MANUAL
                        application_obj.save()
                        return HttpResponse('OK')

                if not member['result'].get('distributor_name', ''):
                    continue
                else:
                    is_our_record = 'arun indane' not in member['result'].get('distributor_name').lower()
                    if is_our_record:
                        if member['result'].get('relationship_status') != 'CANCELLED':
                            record_valid = False
                            invalid_result = member['result']
                            invalid_result_relation = family_member_obj.relation
                    elif family_member_obj.relation != 'SELF':
                        record_valid = False
                        invalid_result = member['result']
                        invalid_result_relation = family_member_obj.relation
                    elif family_member_obj.relation == 'SELF' and is_our_record:
                        application_obj.consumer_id = member['consumer_id']


            except FamilyMembers.DoesNotExist:
                pass

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
            application_obj.robo_sdms_dedup = RoboSdmsDedeupStatusEnum.PROCESSED_AND_UNIQUE
            application_obj.event_invite_for_ekyc_channel_whatsapp()
            if application_obj.consumer_id and \
                    application_obj.status == UjjwalaV2ApplicationStatus.DOCUMENTS_UPLOADED:
                application_obj.ekyc_accepted_or_rejected(description="Bot Processed")

        application_obj.save()
        return HttpResponse('OK')

    @action(methods=['get'], detail=False, url_path='get_ekyc_accepted_list')
    def get_list_to_fetch_consumer_id(self, request, *args, **kwargs):
        # .filter(robo_sdms_dedup=RoboSdmsDedeupStatusEnum.PROCESSED_AND_UNIQUE) \
        aadhar_list = UjjwalaV2Application.objects.filter(
            Q(status=UjjwalaV2ApplicationStatus.DOCUMENTS_UPLOADED) |
            (
                (
                        Q(status=UjjwalaV2ApplicationStatus.EKYC_ACCEPTED) |
                        Q(status=UjjwalaV2ApplicationStatus.APPLICATION_REJECTED)
                ) &
                (
                        Q(consumer_id__isnull=True) |
                        Q(consumer_id='')
                )
            )
        ).filter(
            Q(sdms_last_updated_on__lte=datetime.datetime.today()-datetime.timedelta(hours=12)) |
            Q(sdms_last_updated_on__isnull=True)
	    ).\
            exclude(family_members__uid_no__in=("0", "1")).\
            exclude(id__in=['113', '33', '157', '138', '37', '32', '259', '299', '295', '301']).\
            order_by('-id')

        #aadhar_list = UjjwalaV2Application.objects.filter(id='1022')

        return JsonResponse([
            {
                'id': record.id,
                'uid': record.family_members.filter(relation=FamilyMemberRelationEnum.SELF).first().uid_no
            } for record in aadhar_list
        ], safe=False)

    @action(methods=['post'], detail=False, url_path='update_consumer_id')
    def update_consumer_id(self, request, *args, **kwargs):
        result = request.data.get('result')
        application = UjjwalaV2Application.objects.get(pk=request.data.get('id'))
        application.sdms_last_updated_on = timezone.now()
        application.save()

        if 'arun indane' not in result.get('distributor_name', '').lower():
            return HttpResponse('OK')

        self_family_member = application.family_members.filter(relation=FamilyMemberRelationEnum.SELF).first()

        self_family_member.uid_check_result = result
        self_family_member.save()

        application.consumer_id = result.get('consumer_id', '')

        if application.status == UjjwalaV2ApplicationStatus.DOCUMENTS_UPLOADED:
            application.ekyc_accepted_or_rejected(description="Bot Processed")

        application.save()

        return HttpResponse('OK')

    def perform_create(self, serializer):
        application = serializer.save()
        if getattr(self.request, "PERFORM_SUBMIT", False):
            try:
                application.event_submit_channel_whatsapp()
                # Add lead to vicicial
                requests.post(
                    "http://vici.hawabadlo.in/vicidial/non_agent_api.php?source=ujjwala&user=6666&pass=C00lerMaster"
                    "&function=add_lead&phone_number={}&phone_code=1&list_id=1001&first_name={}&last_name={} ".format(
                        application.contact_mobile, application.name, application.id)
                )

                # django_rq.enqueue(add_lead_to_vicidial, args=(
                #     application.id, application.name, application.contact_mobile
                # ))
            except:
                pass

        return application

    @action(methods=['get'], detail=True, url_path='download_ujjwala_legal_docs')
    def download_ujjwala_legal_docs(self, request, *args, **kwargs):
        obj = self.get_object()
        return download_ujjwala_legal_docs_to_upload(obj)

    @action(methods=['get'], detail=True, url_path='download_ujjwala_physical_legal_documents')
    def download_ujjwala_physical_legal_documents(self, request, *args, **kwargs):
        obj = self.get_object()
        return download_ujjwala_physical_legal_docs(obj)
        # return download_ujjwala_physical_legal_docs(obj)

    @action(methods=['get'], detail=True, url_path='download_ujjwala_documents')
    def download_ujjwala_documents(self, request, *args, **kwargs):
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

        primary_record.update({
            "Category": "Gen"
        })

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
                # "Category": primary_record.get('Category') or "Gen",
                "Category": "Gen",
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
                # "Category": primary_record.get('Category') or "Gen",
                "Category": "Gen",
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
