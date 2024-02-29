import datetime
import io
from functools import partial

import django_filters
import django_rq
import requests
from django.contrib.auth.models import User
from django.contrib.contenttypes.models import ContentType
from django.db import transaction
from django.db.models import Q
from django.http import JsonResponse, HttpResponse, HttpRequest
from django.urls import reverse
from django.utils import timezone
from django_currentuser.middleware import get_current_user
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.pagination import PageNumberPagination

from sdms.models import SdmsCustomerRecord
from service_request.enums import ServiceRequestTypeStatusEnum
from service_request.models import ServiceRequest
from utils.global_functions import upload_file_to_minio_bucket, upload_file_type_obj_to_minio_bucket
from utils.qrcode import append_qr_code_to_sv
from . import models
from .camunda_functions import start_process_in_camunda, start_process_in_camunda_v2
from .enums import UjjwalaV2ApplicationStatus, RoboSdmsDedeupStatusEnum, FamilyMemberRelationEnum, \
    ManualOperationCodeEnum, MaritalStatusEnum, PreInspectionStatusEnum, PreInspectionTypeEnum, \
    UjjwalaApplicationDocumentsEnum, UjjwalaV2ApplicationAvailabilityStatus, UjjwalaV2ApplicationAvailabilityChannel
from .forms import ApplicationRejected
from .global_functions import get_sdms_mismatched_records
from .jobs import do_primary_omc_dedupe_check, enqueue_dedupe_and_audit_jobs
from .models import UjjwalaV2Application, FamilyMembers, ConnectionDisbursement, ConnectionDisbursementDocuments, \
    PreInspection
from .serializers import UjjwalaV2ApplicationSerializer
from .ujjwala_functions import download_ujjwala_documents, get_salutation, \
    download_pre_installation_documents, get_existing_duplicate_applications_detail, \
    download_ujjwala_physical_legal_docs, \
    process_family_uid_result, process_omc_dedupe_result, send_whatsapp_contact_otp, verify_whatsapp_contact_otp, \
    send_sms_contact_otp, verify_sms_contact_otp, send_ujjwala_application_whatsapp_link_v2, download_installation_form, \
    download_ujjwala_legal_docs_to_upload, send_upload_uid_for_ekyc_whatsapp_link, re_create_legal_docs
from .vici_functions import add_lead_to_vicidial


class CustomPagePagination(PageNumberPagination):
    page_size_query_param = 'page_size'
    page_size = 50


upload_docs = ('5745','1994','6880','2821','2112','6163','2367','6999','7022','5206','5207','2370','5871','2860','8','5714','6215','2699','2725','2521','1985','2286','2074','2349','1300','2312','2234','2225','1884','2114','2233','2262','2279','2217','2236','2256','2238','2477','2252','2254','2244','2281','1866','1782','2878','3883','2863','2481','2514','2495','4414','2220','4312','4983','2340','4186','2218','1759','1897','2547','5608','5073','171','213','262','270','883','921','926','934','969','1292','1308','1332','1334','1385','1558','1583','1595','1730','1746','1887','1948','1959','1966','2210','2224','2273','2351','2396','2447','2513','2522','2527','2539','2542','2544','2554','2559','2571','2575','2583','2590','2695','2733','2847','2851','2853','2877','2950','4013','3058','3061','3072','4176','4202','4222','3174','3199','4280','4291','4340','4411','4442','4456','3318','4521','3402','3471','3528','3531','3569','3575','5409','6318','3799','5723','5849','5868','6034','6061','6174','7610','6740','7676','7064','7882','5005','5044','5148','5159','5161','5228','4843','2543','8257','8302','8171','8205','8215','8354','8378','8485','7998','8836','8536','9437','3146')
nic_oms_update = ['7200000023289375','7200000023340267','7200000023342363','7200000023368273','7200000023408889','7200000023419908','7200000023434484','7200000023488189','7200000023503142','7200000023503600','7200000023514594','7200000023531011','7200000023531927','7200000023549593','7200000023552566','7200000023553382','7200000023554000','7200000023554458','7200000023554465','7200000023554908','7200000023555435','7200000023555950','7200000023555956','7200000023556389','7200000023556470','7200000023556672','7200000023556795','7200000023556974','7200000023557397','7200000023557529','7200000023557653','7200000023557833','7200000023558019','7200000023558306','7200000023558382','7200000023559400','7200000023562783','7200000023565562','7200000023571986','7200000023572268','7200000023572539','7200000023577982','7200000023578051','7200000023579391','7200000023579690','7200000023580190','7200000023580512','7200000023581032','7200000023583116','7200000023586410','7200000023587707','7200000023590401','7200000023591395','7200000023594586','7200000023607350','7200000023615939','7200000023624994','7200000023636241','7200000023641386','7200000023642663','7200000023648728','7200000023649712','7200000023653432','7200000023653949','7200000023654454','7200000023654836','7200000023655718','7200000023684986','7200000023685217','7200000023690763','7200000023697125','7200000023714420','7200000023719682','7200000023719741','7200000023730063','7200000023733326','7200000023749433','7200000023772363','7200000023776039','7200000023804562','7200000023823927','7200000023849876','7200000023852557','7200000023853988','7200000023853992','7200000023855790','7200000023856680','7200000023863140','7200000023875594','7200000023887783','7200000023897923','7200000023898929','7200000023901066','7200000023901185','7200000023902338','7200000023903017','7200000023907145','7200000023959425','7200000023968068','7200000023970230','7200000023985412','7200000023996563','7200000023998368','7200000024013319','7200000024051214','7200000024070115','7200000024078150','7200000024101931','7200000024102174','7200000024129137','7200000024130452','7200000024147063','7200000024149000','7200000024155824','7200000024156641','7200000024160475','7200000024166745','7200000024171200','7200000024173903','7200000024201279','7200000024214655','7200000024220252','7200000024227853','7200000024242781','7200000024243600','7200000024245580','7200000024246115','7200000024247013','7200000024247377','7200000024249215','7200000024265613','7200000024269591','7200000024271091','7200000024273600','7200000024281795','7200000024282317','7200000024295706','7200000024309112','7200000024317312','7200000024326410','7200000024329022','7200000024330960','7200000024331702','7200000024337367','7200000024361433','7200000024367213','7200000024396389','7200000024407637','7200000024411773','7200000024415783','7200000024424328','7200000024434195','7200000024447844','7200000024460071','7200000024507489','7200000024538087','7200000024578589','7200000024639057','7200000024657853','7200000024668056','7200000024668554','7200000024789028','7200000024848867','7200000024849969','7200000024850480','7200000024851314','7200000024856342','7200000024856458','7200000024863451','7200000024863960','7200000024864287','7200000024864933','7200000024867459','7200000024868491','7200000024875150','7200000024879600','7200000024881859','7200000024882172','7200000024889322','7200000024891219','7200000024891408','7200000024891929','7200000024892347','7200000024893704','7200000024921689','7200000024940788','7200000024991301','7200000024992119']
upload_uid = ['4029','4064','4065','4080','4101','4103','4153','4177','4207','4226','4250','4266','4341','4353','4371','4390','4409','4473','4492','4515','4618','4623','4644','4677','4683','4685','4753','4844','4851','4886','4904','4906','4907','4918','4931','4943','4944','4947','5004','5011','5038','5045','5077','5126','5142','5173','5365','5399','5435','5528','5543','5565','5616','5778','5881','5986','5989','6013','6056','6129','6131','6155','6177','6330','6379','6398','6400','6404','6436','6618','6657','6663','6666','6713','6749','6769','6813','6832','6883','6926','6945','6947','6999','7004','7026','7068','7127','7138','7220','7285','7328','7624','7704','7818','7870','8033','8060','8203','8245','8319','8339','8352','8381','8419','8460','8613','8633','8639','8745','8797','8822','8829','8911','8966','9051','9275','9402','9435','9436','9465','9475','9497','9498','9544','9636','9655','9701','9723','9724','9750','9851','9912','9941','9954','9987']


class UjjwalaApplicationAPIViewSet(viewsets.ModelViewSet):
    queryset = models.UjjwalaV2Application.objects.all()
    serializer_class = UjjwalaV2ApplicationSerializer
    filter_backends = [django_filters.rest_framework.DjangoFilterBackend]
    filterset_fields = ['id', 'status']
    ordering_fields = '__all__'
    pagination_class = CustomPagePagination


    @action(methods=['get'], detail=False, url_path='check_if_already_uploaded_sv')
    def check_if_already_uploaded_sv(self, request, *args, **kwargs):
        sv_uploaded = ConnectionDisbursement.objects.get(
            pk=request.GET.get('cid')
        ).invitation.filter(status='VALID').exclude(sv_link='').count() > 0
        return JsonResponse({
             "uploaded": sv_uploaded
        })

    @action(methods=['get'], detail=False, url_path='get_uid_to_upload_list')
    def get_uid_to_upload_list(self, request, *args, **kwargs):
        gte = request.GET.get('gte', None)
        lte = request.GET.get('lte', None)
        filters = {'status__in': ['NIC_CLEARED', 'READY_FOR_DISBURSEMENT']}
        if gte:
            filters['id__gte'] = gte
        if lte:
            filters['id__lte'] = lte

        application_list = UjjwalaV2Application.objects.filter(
            Q(uid_uploaded=False)
        ).filter(**filters).exclude(consumer_id=None).order_by('id')
    #.filter(id__in=upload_uid).exclude(consumer_id=None).order_by('id')
        return JsonResponse([
            {
                'id': record.id,
                'consumer_id': record.consumer_id,
                'uid_link': record.family_members.get(relation='SELF').uid_front_link
            } for record in application_list if record.family_members.get(relation='SELF').uid_front_link
        ], safe=False)

    @action(methods=['post'], detail=True, url_path='mark_uid_uploaded')
    def mark_uid_uploaded(self, request, *args, **kwargs):
        application = self.get_object()
        application.uid_uploaded = True
        application.save()
        return JsonResponse({"status": "OK"})

    @action(methods=['get'], detail=True, url_path='get_printing_urls')
    def get_printing_urls(self, request: HttpRequest, *args, **kwargs):
        obj = self.get_object()
        connection_disbursement = obj.connection_disbursement
        bluebook_label_print_url = reverse(
            'ujjwala:connection_disbursement_barcode_label_print_view',
            kwargs={'pk':connection_disbursement.id}
        )
        return JsonResponse({
            "form_abc": obj.physical_legal_document_link(),
            "ujjwala_sv": connection_disbursement.valid_sv_link(),
            "label": self.request.build_absolute_uri(bluebook_label_print_url),
            "form_d": connection_disbursement.form_d_link()
        })

    @action(methods=['get'], detail=False, url_path='get_work_items_for_doc_upload')
    def get_work_items_for_doc_upload(self, request: HttpRequest, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())
        #queryset = queryset.filter(id__in=upload_docs)
        #queryset = queryset.filter(id__gt=1439)
        queryset = queryset.filter(
            status=UjjwalaV2ApplicationStatus.EKYC_ACCEPTED, consumer_id__isnull=False, residential_status='LIVING_WITH_FAMILY'
        ).exclude(marital_status__in=[
            MaritalStatusEnum.DIVORCED, MaritalStatusEnum.WIDOW
        ]).exclude(
            robo_execution_failed_count__gte=2
        ).exclude(
		family_members__dob__gte='2004-10-01'
	).exclude(family_members__uid_no__in=[
		'999999999999','666666666666','0','1'
	]).exclude(version='V1').order_by('id')

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
        if not request.data.get('omc_status'): return HttpResponse('No Data, Skip Update')
        application: UjjwalaV2Application = self.get_object()

        nic_status = request.data.get('nic_status')

        transition_executed = False

        if application.status == UjjwalaV2ApplicationStatus.LEGAL_DOCUMENTS_UPLOAD:
            if request.data.get('omc_status') == 'OMC Clear':
                application.transition_omc_clear(description="Bot Processed: OMC Clear")
                transition_executed = True
            elif request.data.get('omc_status') == 'OMC Reject':
                application.transition_omc_reject(description="Bot Processed: OMC Reject")
                transition_executed = True
        if application.status in (
            UjjwalaV2ApplicationStatus.OMC_CLEARED,
            UjjwalaV2ApplicationStatus.NIC_ERROR_APPROVED
        ) and nic_status not in ('Pending', 'Awaited'):
            if nic_status == 'Cleared' or 'approved' in nic_status.lower():
                if application.status == UjjwalaV2ApplicationStatus.OMC_CLEARED:
                    application.transition_nic_cleared(description="Bot Processed: NIC Cleared {}".format(nic_status))
                    transition_executed = True
                else:
                    application.transition_nic_error_approved_to_nic_clear(
                        description="Bot Processed: NIC Cleared {}".format(nic_status)
                    )
                    transition_executed = True
            elif nic_status == 'Address Insufficient':
                application.transition_nic_error_insufficient_address(
                    error_code='', description="Bot Processed: {}".format(nic_status)
                )
                transition_executed = True
            else:
                code = 'DIST' if 'dist' in nic_status.lower() else 'FO'
                application.transition_nic_error(error_code=code, description=nic_status)
                transition_executed = True

        application.sdms_last_updated_on = timezone.now()
        application.product = request.data.get('product')
        application.manual_operation_code = nic_status
        application.ekyc_cleared = request.data.get('ekyc_flag')
        application.legal_documents_upload_status = request.data.get('legal_docs_uploaded')
        if transition_executed:
            application.save()
        else:
            application.save(
                update_fields=[
                    'sdms_last_updated_on', 'product',
                    'manual_operation_code', 'ekyc_cleared', 'legal_documents_upload_status']
            )
        return HttpResponse('OK')

    @action(methods=['get'], detail=False, url_path='get_list_to_fetch_omc_nic_status')
    def get_list_to_fetch_omc_nic_status(self, request: HttpRequest, *args, **kwargs):
        aadhar_list = UjjwalaV2Application.objects.filter(
            Q(status=UjjwalaV2ApplicationStatus.LEGAL_DOCUMENTS_UPLOAD) |
            Q(status=UjjwalaV2ApplicationStatus.OMC_CLEARED) |
            Q(status=UjjwalaV2ApplicationStatus.NIC_ERROR_APPROVED)
        ).exclude(consumer_id__isnull=True).filter(
            Q(sdms_last_updated_on__lte=datetime.datetime.today()-datetime.timedelta(hours=1)) |
            Q(sdms_last_updated_on__isnull=True)
        ).order_by('updated_on')
#.exclude(version='V1')
#.order_by('-id')
#        aadhar_list = UjjwalaV2Application.objects.filter(id__in=["1273","2120","2534","32","1265","323","76","601","2148","37"]).exclude(consumer_id__isnull=True).order_by('id')
        return JsonResponse([{
            "payload": {
                'id': record.id,
                'consumer_id': record.consumer_id
                }
            } for record in aadhar_list
        ], safe=False)

    @action(methods=['get'], detail=False, url_path='get_mismatched_sdms_records')
    def get_mismatched_sdms_records(self, request: HttpRequest, *args, **kwargs):
        before_days = request.GET.get('before_days')
        upto_date = datetime.datetime.today() - datetime.timedelta(days=int(before_days))
        records = get_sdms_mismatched_records(upto_date.strftime('%Y-%m-%d'))
        if records:
            return JsonResponse([
                {
                    'consumer_id': record[0],
                } for record in records
            ], safe=False)
        else:
            return HttpResponse("No records found.")

    @action(methods=['post'], detail=False, url_path='update_mobile_number_sdms_record')
    def update_mobile_number_sdms_record(self, request: HttpRequest, *args, **kwargs):
        consumer_id = request.data.get('consumer_id')
        contact_number = request.data.get('contact_number')

        obj = SdmsCustomerRecord.objects.get(consumer_id=consumer_id)

        obj.contact_number = contact_number
        obj.save()
        res = requests.post(
         	"http://vici.arungas.com/vicidial/non_agent_api.php?source=ujjwala&user=6666&pass=C00lerMaster101"
         	"&function=add_lead&phone_number={}&list_id=1000&first_name={}&address1={}&kyc_date={}".format(
         		obj.contact_number, obj.name, obj.address, obj.kyc_date
         	)
        )
        return HttpResponse("Contact Number Updated Successfully")

    @action(methods=['post'], detail=True, url_path='update_ujjwala_application_mobile_number')
    def update_ujjwala_application_mobile_number(self, request: HttpRequest, *args, **kwargs):
        obj = self.get_object()
        phone_number = request.data.get('phone_number')

        service_request_id = request.data.get('service_request_id')

        if phone_number:
            obj.contact_mobile = phone_number
            obj.save()
            service_request = ServiceRequest.objects.get(pk=service_request_id)
            service_request.status = ServiceRequestTypeStatusEnum.SUCCESS
            service_request.save()
            return HttpResponse("Contact Number Updated Successfully")
        else:
            raise Exception("Phone Number Missing")


class UjjwalaApplicationViewSet(viewsets.ModelViewSet):
    queryset = models.UjjwalaV2Application.objects.all()
    serializer_class = UjjwalaV2ApplicationSerializer

    @action(methods=['post'], detail=False, url_path='wf')
    def web_form(self, request, *args, **kwargs):
        request.PERFORM_SUBMIT = True
        referral_username = request.data.get('referral_code').split("(")[0].strip()
        user = User.objects.filter(username=referral_username).first()
        if user:
            request.data['referred_by_id'] = user.id
        self_family_member = FamilyMembers.objects.filter(uid_no=request.data.get('SELF-uid_no')).first()
        if self_family_member:
            existing_application = self_family_member.parent
            if existing_application.status != UjjwalaV2ApplicationStatus.DOCUMENTS_REUPLOAD:
                return JsonResponse({
                    "message": "Application Already Exist With Id: {} In Status: {}".format(
                        existing_application.id, existing_application.status
                    )
                })

            response = super().create(request, *args, **kwargs)

            connection_disbursement = ConnectionDisbursement.objects.filter(
                parent_id=existing_application.id
            ).first()

            pre_inspection = PreInspection.objects.filter(
                parent_id=existing_application.id
            ).first()

            if pre_inspection:
                if pre_inspection.status in (PreInspectionStatusEnum.ACCEPTED, PreInspectionStatusEnum.SUBMITTED):
                    pre_inspection.parent_id = response.data.get('id')
                    pre_inspection.save()
                else:
                    pre_inspection.delete()

            if connection_disbursement:
                connection_disbursement.parent_id = response.data.get('id')
                connection_disbursement.save()
                re_create_legal_docs(UjjwalaV2Application.objects.get(pk=response.data.get('id')))

            existing_application.delete()
            return response
        return super().create(request, *args, **kwargs)

    @action(methods=['post'], detail=False, url_path='ujjwala_ivr_confirmation')
    def ujjwala_ivr_confirmation(self, request, *args, **kwargs):
        application_id = request.data.get('application_id')
        response_code = request.data.get('response_code')

        application = UjjwalaV2Application.objects.get(id=application_id)


        if response_code == 1:
            application.availability_status = UjjwalaV2ApplicationAvailabilityStatus.INTERESTED
        elif response_code == 5:
            application.availability_status = UjjwalaV2ApplicationAvailabilityStatus.INTERESTED_ADDRESS_CHANGE
        elif response_code == 9:
            application.availability_status = UjjwalaV2ApplicationAvailabilityStatus.NOT_INTERESTED
        else:
            return JsonResponse({"status": "Invalid Response Code"})
        application.availability_channel = UjjwalaV2ApplicationAvailabilityChannel.IVR
        application.availability_updated_on = datetime.datetime.now()
        application.save()
        if response_code == 5:
            application.transition_address_change()
            application.save()

        return JsonResponse({"status": "Updated"})

    @action(methods=['post'], detail=False, url_path='legal_documents_reupload')
    def legal_documents_reupload(self, request, *args, **kwargs):
        application_id = request.data.get('application_id')

        application = UjjwalaV2Application.objects.get(id=application_id)
        application.transition_legal_documents_pending(data={'reason': 'LOST'})
        application.save()

        return JsonResponse({
            "status": "Updated"
        })

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
                    description="Submitted On: {}".format(timezone.now().strftime('%d-%m-%Y'))
                )
                connection_disbursement.save()

                create_txn_status_job_function = partial(
                    django_rq.enqueue,
                    "ujjwala.jobs.compress_connection_disbursement_documents",
                    ci_id=connection_disbursement.id
                )
                transaction.on_commit(create_txn_status_job_function)

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

        application = UjjwalaV2Application.objects.filter(
            Q(contact_mobile=contact_mobile) | Q(uid_linked_mobile=contact_mobile) | Q(
                sdms_mobile_number=contact_mobile)
        ).first()

        if application:
            return JsonResponse({
                "status": False,
                "date": application.created_on.strftime('%d-%m-%Y'),
                "application": "Ujjwala Application Id: {} {}".format(
                    application.pk, application.name
                ),
                "application_id": application.pk,
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
        ).exclude(
            status=UjjwalaV2ApplicationStatus.DOCUMENTS_REUPLOAD
        ).order_by('-id')

        if applications.exists():
            result = {
                "status": False,
            }
            msg = get_existing_duplicate_applications_detail(applications)
            result.update(msg)
            return JsonResponse(result)

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

        existing_applications = UjjwalaV2Application.objects.filter(family_members__uid_no=uid).order_by('-id')
        if existing_applications:
            if len(existing_applications) == 1:
                if existing_applications.first().status == UjjwalaV2ApplicationStatus.DOCUMENTS_REUPLOAD:
                    return JsonResponse({
                        "status": True,
                        "msg": "VALID_APPLICATION",
                        "data": {}
                    })

        if not existing_applications.exists():
            return JsonResponse({
                "status": True,
                "msg": "VALID_APPLICATION",
                "data": {}
            })

        result = get_existing_duplicate_applications_detail(existing_applications)
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

    @action(methods=['get'], detail=False, url_path='get_aadhar_list_v2')
    def get_aadhar_list_for_iocl_sdms_dedup_v2(self, request, *args, **kwargs):
        aadhar_list = UjjwalaV2Application.objects.filter(
            status__in=(
                UjjwalaV2ApplicationStatus.DOCUMENTS_UPLOADED,
                # UjjwalaV2ApplicationStatus.EKYC_ACCEPTED,
                # UjjwalaV2ApplicationStatus.LEGAL_DOCUMENTS_UPLOAD
            ),
            robo_sdms_dedup=RoboSdmsDedeupStatusEnum.PROCESS_MANUAL,
            created_on__date__lte=datetime.datetime.strptime('2022-06-01', '%Y-%m-%d')
            # robo_sdms_dedup=RoboSdmsDedeupStatusEnum.NOT_PROCESSED
        ).exclude(family_members__uid_no__in=("0", "1")).order_by('id')[:5]
        # aadhar_list = UjjwalaV2Application.objects.filter(id__in=["1273","2120","2534","32","1265","323","76","601","2148","37"])
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
            # Create PreInspection Object
            obj = PreInspection.objects.create(
                parent_id=application_obj.id,
                # status=PreInspectionStatusEnum.KITCHEN_PHOTO,
                status=PreInspectionStatusEnum.CHANGE_ADDRESS,
                type=PreInspectionTypeEnum.SELF
            )
            application_obj.event_whatsapp_pre_inspection_type_self(obj.id)
            # application_obj.event_invite_for_ekyc_channel_whatsapp()
            if application_obj.consumer_id and \
                    application_obj.status == UjjwalaV2ApplicationStatus.DOCUMENTS_UPLOADED:
                sdms_contact = application_obj.family_members.filter(
                    relation='SELF'
                ).uid_check_result.get('phone_number', '')
                application_obj.ekyc_accepted_or_rejected(
                    description="Bot Processed",
                    sdms_mobile_number=sdms_contact
                )
        application_obj.save()
        return HttpResponse('OK')

    @action(methods=['post'], detail=False, url_path='update_result_v2')
    def update_iocl_sdms_dedup_results_v2(self, request, *args, **kwargs):
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
                result = process_family_uid_result(member.get('alert', ''))
                member['result'] = result
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
                        if member['result']['consumer_id']:
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
                        invalid_result.get('distributor_name', ''), invalid_result.get('consumer_id', ''),
                        invalid_result.get('contact_address', '')
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
            # Create PreInspection Object
            if not application_obj.pre_inspection:
                obj = PreInspection.objects.create(
                    parent_id=application_obj.id,
                    # status=PreInspectionStatusEnum.KITCHEN_PHOTO,
                    status=PreInspectionStatusEnum.CHANGE_ADDRESS,
                    type=PreInspectionTypeEnum.SELF
                )
                application_obj.event_whatsapp_pre_inspection_type_self(obj.id)
            # application_obj.event_invite_for_ekyc_channel_whatsapp()
            if application_obj.consumer_id and \
                    application_obj.status == UjjwalaV2ApplicationStatus.DOCUMENTS_UPLOADED:
                self_fm = application_obj.family_members.filter(relation=FamilyMemberRelationEnum.SELF).first()
                sdms_mobile_number = self_fm.uid_check_result.get('phone_number', '')
                application_obj.ekyc_accepted_or_rejected(
                    sdms_mobile_number=sdms_mobile_number,
                    description="Bot Processed"
                )
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
            Q(sdms_last_updated_on__lte=datetime.datetime.today()-datetime.timedelta(hours=16)) |
            Q(sdms_last_updated_on__isnull=True)
	).\
            exclude(family_members__uid_no__in=("0", "1")).\
            exclude(sync_with_sdms=False).\
            exclude(id__in=['113', '33', '157', '138', '37', '32', '259', '299', '295', '301']).\
            order_by('-id')

        #aadhar_list = UjjwalaV2Application.objects.filter(id='1022')

        return JsonResponse([
            {
                'id': record.id,
                'uid': record.family_members.filter(relation=FamilyMemberRelationEnum.SELF).first().uid_no
            } for record in aadhar_list
        ], safe=False)

    @action(methods=['post'], detail=False, url_path='robo_send_invitation')
    def robo_send_invitation(self, request: HttpRequest, *args, **kwargs):
        consumer_disbursement_id = request.POST.get('connection_disbursement_id')
        obj = ConnectionDisbursement.objects.filter(id=consumer_disbursement_id).first()
        if not obj:
             return HttpResponse('Connection Disbursement Not Found')

        sv_upload_link = None
        booking_id = request.POST.get('booking_id', None)

        if not request.POST.get('sv_generated_not_downloaded'):
            sv_generated_not_downloaded = False
            file = request.FILES.get('file')
            pdf_file_bytes = io.BytesIO(file.read())
            bytes_stream = append_qr_code_to_sv(
                "{},SV".format(obj.parent_id),
                booking_id,
                pdf_file_bytes
            )
            # Bucket Name: ujjwaladocuments
            doc_file_bytes = io.BytesIO(bytes_stream)
            sv_upload_link = upload_file_type_obj_to_minio_bucket(
                doc_file_bytes, 'ujjwaladocuments', "sv_{}".format(obj.parent_id), "application/pdf"
            )
        else:
            sv_generated_not_downloaded = True

        # Installation Form Upload
        installation_document = download_installation_form(obj.parent)
        upload_url = upload_file_to_minio_bucket(
            installation_document,
            "ujjwaladocuments",
            "ujjwala_{}_installation_document".format(obj.parent_id)
        )
        obj.documents.create(
            type=UjjwalaApplicationDocumentsEnum.INSTALLATION_DOCUMENT,
            link=upload_url
        )

        invitation_obj = obj.invitation.create(
            sv_link=sv_upload_link if sv_upload_link else '',
            booking_id=booking_id,
            sv_uploaded_on=datetime.datetime.now() if sv_upload_link else None
        )
        invitation_obj.sv_generated_not_downloaded = sv_generated_not_downloaded
        invitation_obj.save()
        return HttpResponse('OK')

    @action(methods=['post'], detail=True, url_path='update_consumer_id_for_application')
    def update_consumer_id_for_application(self, request, *args, **kwargs):
        application = self.get_object()
        #application = UjjwalaV2Application.objects.get(pk=request.data.get('id'))
        application.consumer_id = request.data.get('consumer_id')
        application.save()
        return HttpResponse('OK')

    @action(methods=['post'], detail=False, url_path='update_consumer_id')
    def update_consumer_id(self, request, *args, **kwargs):
        result = request.data.get('result')
        application = UjjwalaV2Application.objects.get(pk=request.data.get('id'))
        application.sdms_last_updated_on = timezone.now()
        application.save()

        if not result.get('distributor_name', ''):
            return HttpResponse('OK')

        if 'arun indane' in result.get('distributor_name', '').lower():
            self_family_member = application.family_members.filter(relation=FamilyMemberRelationEnum.SELF).first()

            self_family_member.uid_check_result = result
            self_family_member.save()

            application.consumer_id = result.get('consumer_id', '')
            application.sdms_mobile_number = result.get('phone_number', '')
            if application.status == UjjwalaV2ApplicationStatus.DOCUMENTS_UPLOADED:
                sdms_contact = application.family_members.filter(
                    relation='SELF'
                ).uid_check_result.get('phone_number', '')
                application.ekyc_accepted_or_rejected(
                    description="Bot Processed",
                    sdms_mobile_number=sdms_contact
                )
        else:
            application.sync_with_sdms = False
            form = ApplicationRejected(data={
                'rejected_reason': 'CONNECTION_ALREADY_EXIST',
                'description': "{} {} {} {}".format(
                    'SELF',
                    result['distributor_name'], result['consumer_id'],
                    result['contact_address']
                )})
            form.is_valid()
            if application.status == 'DOCUMENTS_UPLOADED':
                application.application_rejected(**form.cleaned_data)
                application.event_ioc_dedupe_reject_channel_whatsapp()

        application.save()

        return HttpResponse('OK')

    def perform_create(self, serializer):
        application = serializer.save()
        user = get_current_user()
        application.filled_by = None if user.is_anonymous else user
        application.save()
        if getattr(self.request, "PERFORM_SUBMIT", False):
            try:
                create_txn_status_job_function = partial(
                    enqueue_dedupe_and_audit_jobs, application.id, self.request.data
                )
                # create_txn_status_job_function = partial(
                #     start_process_in_camunda_v2, application.id, self.request.data
                # )
                transaction.on_commit(create_txn_status_job_function)

                # create_compress_docs_job_function = partial(
                #     django_rq.enqueue,
                #     "ujjwala.jobs.compress_application_documents",
                #     application_id=application.id
                # )
                # transaction.on_commit(create_compress_docs_job_function)

                # commented for development
                application.event_submit_channel_whatsapp()
                result = django_rq.enqueue(do_primary_omc_dedupe_check, args=(application.id,))
                django_rq.enqueue(add_lead_to_vicidial, args=(
                    application.contact_mobile, application.name, application.id,
                ))

            except Exception as e:
                print("Peform Submit: {}".format(e))
                pass
        return application

    @action(methods=['get'], detail=True, url_path='download_ujjwala_legal_docs')
    def download_ujjwala_legal_docs(self, request, *args, **kwargs):
        obj = self.get_object()
        django_rq.enqueue(re_create_legal_docs, args=(obj,))
        return download_ujjwala_legal_docs_to_upload(obj)

    @action(methods=['get'], detail=True, url_path='download_ujjwala_physical_legal_documents')
    def download_ujjwala_physical_legal_documents(self, request, *args, **kwargs):
        pre_inspection_obj = PreInspection.objects.filter(id=kwargs.get('pk')).first()
        if pre_inspection_obj:
            if pre_inspection_obj.status == PreInspectionStatusEnum.ACCEPTED:
                obj = pre_inspection_obj.parent
                return download_ujjwala_physical_legal_docs(obj)

            return HttpResponse("Not Valid Status: {}".format(pre_inspection_obj.status))
        return HttpResponse("No Valid Record Found")
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
            # application.robo_manual_legal_documents_upload(
            #     description='No primary record found',
            #     manual_operation_code=ManualOperationCodeEnum.NO_PRIMARY_RECORD
            # )
            application.do_manual_operations(
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
            # application.robo_manual_legal_documents_upload(
            #     description='UID does not exist',
            #     manual_operation_code=ManualOperationCodeEnum.NO_UID_FOUND
            # )
            application.do_manual_operations(
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

        identity_num = uid_record["Identity Num"].lower().replace('x', '')
        uid_last_4_digits = identity_num.strip()
        applicant = application.family_members.filter(uid_no__endswith=uid_last_4_digits)
        if not applicant:
            # Applicant UID not matching SDMS
            # application.robo_manual_legal_documents_upload(
            #     description='Applicant UID not matching SDMS',
            #     manual_operation_code=ManualOperationCodeEnum.UID_MISMATCH_SDMS
            # )
            application.do_manual_operations(
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
                # application.robo_manual_legal_documents_upload(
                #     description='Applicant UID Relation Mismatch',
                #     manual_operation_code=ManualOperationCodeEnum.UID_MISMATCH_SDMS
                # )
                application.do_manual_operations(
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
                    "Identity Num": applicant.uid_no[-6:],
                },
                    {
                        "Identity Type": "INTERNAL-UJJWALA",
                        "Identity Method": "14 Point Exclusion Declaration",
                        "Identity Num": applicant.uid_no[-6:],
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
        if application.status == 'EKYC_ACCEPTED':
            application.do_manual_operations(
                description=request.data.get('message'),
                manual_operation_code=ManualOperationCodeEnum.ROBO_GOT_ERROR_ALERT
            )
            application.save()
        return HttpResponse('OK')

    @action(methods=['get'], detail=True, url_path='relation_uid')
    def relation_uid(self, request: HttpRequest, *args, **kwargs):
        application: UjjwalaV2Application = self.get_object()
        uid_list = []
        for record in application.family_members.filter().exclude(relation='SELF').all():
            uid_list.append(record.uid_no)
        return JsonResponse(uid_list, safe=False)

    @action(methods=['get'], detail=True, url_path='relation_data')
    def relation_data(self, request: HttpRequest, *args, **kwargs):
        application: UjjwalaV2Application = self.get_object()
        uid_list = []
        for record in application.family_members.filter().exclude(relation='SELF').all():
            fm = {"uid": record.uid_no}
            try:
                fm["first_name"], fm["last_name"] = record.name.split(' ', 1)
            except ValueError:
                fm["first_name"], fm["last_name"] = record.name, '.'

            if record.relation in ['HUSBAND', 'FATHER']:
                fm["gender"] = "Male"
            else:
                fm["gender"] = "Female"
            fm["dob"] = record.dob.strftime("%d-%b-%Y")
            uid_list.append(fm)
        return JsonResponse(uid_list, safe=False)

    @action(methods=['get'], detail=False, url_path='get_enrich_rejection_records')
    def get_enrich_rejection_records(self, request, *args, **kwargs):
        record_list = UjjwalaV2Application.objects.filter(
            robo_sdms_dedup=RoboSdmsDedeupStatusEnum.ENRICH_REJECTION_DETAILS
        ).order_by("id")

        return JsonResponse([
            {
                'id': record.id,
                'family_members': [{
                    'id': member.id,
                    'uid': member.uid_no
                } for member in record.family_members.exclude(
                    uid_no__in=('999999999999', '666666666666', '0', '1')
                )]
            } for record in record_list
        ], safe=False)

    @action(methods=['post'], detail=False, url_path='update_enrich_rejection_record')
    def update_enrich_rejection_record(self, request, *args, **kwargs):
        record_valid = True
        invalid_result = {}
        invalid_result_relation = ''
        application_obj = UjjwalaV2Application.objects.get(pk=request.data.get('id'))

        for member in request.data['family_members']:
            result = process_omc_dedupe_result(member['omc_dedup_result'])

            if not result:
                continue

            family_member_obj = FamilyMembers.objects.get(pk=member.get('id'))
            family_member_obj.uid_check_result = result
            family_member_obj.save()

            if family_member_obj.relation == 'SELF' and 'arun indane' in family_member_obj.uid_check_result['distributor_name'].lower():
                continue

            record_valid = False

            if family_member_obj.relation == 'SELF':
                invalid_result_relation = 'SELF'
                invalid_result = result
            elif not invalid_result:
                invalid_result_relation = family_member_obj.relation
                invalid_result = result

        if record_valid:
            application_obj.robo_sdms_dedup = RoboSdmsDedeupStatusEnum.PROCESS_MANUAL
            application_obj.save()
            return HttpResponse('PROCESS MANUAL')

        if application_obj.status not in ('OMC_REJECTED', 'APPLICATION_REJECTED'):
            form = ApplicationRejected(data={
                'rejected_reason': 'CONNECTION_ALREADY_EXIST',
                'description': "{} {} {}".format(
                    invalid_result_relation,
                    invalid_result['distributor_name'], invalid_result['consumer_id']
                )})
            form.is_valid()
            application_obj.application_rejected(**form.cleaned_data)
            application_obj.event_ioc_dedupe_reject_channel_whatsapp()

        application_obj.robo_sdms_dedup = RoboSdmsDedeupStatusEnum.PROCESSED_AND_DUPLICATE
        application_obj.save()

        return HttpResponse('OK')

    @action(methods=['get'], detail=False, url_path='get_iocl_investigation_records')
    def get_iocl_investigation_records(self, request, *args, **kwargs):
        record_list = UjjwalaV2Application.objects.filter(
            robo_sdms_dedup=RoboSdmsDedeupStatusEnum.IOCL_INVESTIGATION_REQUIRED
        ).order_by("id")
        # record_list = UjjwalaV2Application.objects.filter(
        #     id=11351
        # ).order_by("id")

        return JsonResponse([
            {
                'id': record.id,
                'family_members': [{
                    'id': member.id,
                    'relation': member.relation,
                    'uid': member.uid_no
                } for member in record.family_members.exclude(
                    uid_no__in=('999999999999', '666666666666', '0', '1')
                )]
            } for record in record_list
        ], safe=False)

    @action(methods=['post'], detail=False, url_path='update_iocl_investigation_record')
    def update_iocl_investigation_record(self, request, *args, **kwargs):
        record_valid = True
        invalid_result = {}
        invalid_result_relation = ''
        application_obj = UjjwalaV2Application.objects.get(pk=request.data.get('id'))

        self_record = [
            i for i in request.data['family_members'] if i['relation'] == 'SELF'
        ][0]
        self_consumer_id = self_record['result'].get('consumer_id', '')

        if self_consumer_id:
            for member in request.data['family_members']:
                if member['relation'] == 'SELF': continue
                if member['result'].get('consumer_id', '') == self_consumer_id:
                    member['result'] = {}

        for member in request.data['family_members']:
            family_member_obj = FamilyMembers.objects.get(pk=member.get('id'))
            family_member_obj.uid_check_result = member['result']
            family_member_obj.save()

            if not member['result'].get('distributor_name', ''):
                continue

            is_our_record = 'arun indane' in member['result'].get('distributor_name').lower()

            if not (
                family_member_obj.relation == 'SELF' and
                is_our_record and
                member['result'].get('relationship_status') == 'IN PROCESS'
            ):
                invalid_result_relation = family_member_obj.relation
                invalid_result = member['result']
                record_valid = False

        if record_valid:
            application_obj.robo_sdms_dedup = RoboSdmsDedeupStatusEnum.PROCESSED_AND_UNIQUE
            if self_consumer_id:
                application_obj.consumer_id = self_consumer_id

                if application_obj.status == UjjwalaV2ApplicationStatus.DOCUMENTS_UPLOADED:
                    sdms_contact = application_obj.family_members.get(
                        relation='SELF'
                    ).uid_check_result.get('phone_number', '')
                    application_obj.ekyc_accepted_or_rejected(
                        application_obj="Bot Processed",
                        sdms_mobile_number=sdms_contact
                    )
        else:
            form = ApplicationRejected(data={
                'rejected_reason': 'CONNECTION_ALREADY_EXIST',
                'description': "{} {} {} {}".format(
                    invalid_result_relation,
                    invalid_result['distributor_name'], invalid_result['consumer_id'],
                    invalid_result['contact_address']
                )})
            form.is_valid()
            application_obj.robo_sdms_dedup = RoboSdmsDedeupStatusEnum.PROCESSED_AND_DUPLICATE
            if not application_obj.status == UjjwalaV2ApplicationStatus.APPLICATION_REJECTED:
                application_obj.application_rejected(**form.cleaned_data)
                application_obj.event_ioc_dedupe_reject_channel_whatsapp()
        application_obj.save()
        return HttpResponse('OK')

    @action(methods=['get'], detail=False, url_path='get_scheme_onboarding_status')
    def get_scheme_onboarding_status(self, request, *args, **kwargs):

        record_list = UjjwalaV2Application.objects.filter(
            Q(status=UjjwalaV2ApplicationStatus.MATERIAL_DELIVERED) &
            (Q(scheme_onboarding_status='') | Q(scheme_onboarding_status=None))
        ).order_by("id")

        return JsonResponse([
            {
                'id': record.id,
                'consumer_id': record.consumer_id
            } for record in record_list
        ], safe=False)

    @action(methods=['post'], detail=False, url_path='update_scheme_onboarding_status')
    def update_scheme_onboarding_status(self, request, *args, **kwargs):
        application_obj = UjjwalaV2Application.objects.get(pk=request.data.get('id'))
        application_obj.scheme_onboarding_status = request.data.get('scheme_onboarding_status', '')
        return HttpResponse('OK')

    @action(methods=['post'], detail=False, url_path='schedule_whatsapp_message')
    def schedule_whatsapp_message(self, request, *args, **kwargs):
        #scheduler = django_rq.get_scheduler('default')
        inbound_call_user_id = 87
        #start_time = datetime.time(8, 0, 0)
        #end_time = datetime.time(19, 30, 0)

        contact_mobile = self.request.data['mobile']
        #current_time = datetime.datetime.now(pytz.timezone('Asia/Kolkata')).time()
        send_ujjwala_application_whatsapp_link_v2(contact_mobile, user_id=inbound_call_user_id)

        #if time_in_range(
        #    start_time, end_time, current_time
        #):
        #    date = datetime.date(1, 1, 1)
        #    datetime1 = datetime.datetime.combine(date, end_time)
        #    datetime2 = datetime.datetime.combine(date, current_time)

        #    time_difference = datetime1 - datetime2

        #    time_difference = time_difference + datetime.timedelta(seconds=random.randint(0, 60*60))
        #    scheduler.enqueue_in(
        #        time_difference,
        #        send_ujjwala_application_whatsapp_link_v2,
        #        contact_mobile=contact_mobile, user_id=inbound_call_user_id
        #    )
            # scheduler.enqueue_at(
            #     datetime.datetime(2022, 8, 20, 10, 48),
            #     send_ujjwala_application_whatsapp_link,
            #     contact_mobile=contact_mobile
            # )
        #else:
        #    send_ujjwala_application_whatsapp_link_v2(contact_mobile, user_id=inbound_call_user_id)

        return HttpResponse('OK')

    @action(methods=['get'], detail=True, url_path='get_social_media_details')
    def get_social_media_details(self, request, *args, **kwargs):
        application = UjjwalaV2Application.objects.get(pk=kwargs['pk'])
        response = {
            "id": application.id,
            "name": application.name,
            "social_media_photo_url": application.connection_disbursement.documents.filter(
                type=UjjwalaApplicationDocumentsEnum.SOCIAL_MEDIA_PHOTO
            ).first().link
        }
        return JsonResponse(response, safe=False)

    @action(methods=['post'], detail=False, url_path='whatsapp_link_upload_uid_for_ekyc')
    def send_link_upload_uid_for_ekyc(self, request, *args, **kwargs):
        application = UjjwalaV2Application.objects.get(pk=kwargs['pk'])

        result = send_upload_uid_for_ekyc_whatsapp_link(application.contact_mobile, application.id)
        if not result:
            return JsonResponse({"status": False}, safe=False)
        return JsonResponse({"status": True}, safe=False)


class UjjwalaPreInspectionAPIViewSet(viewsets.ViewSet):
    @action(methods=['get'], detail=False, url_path='preinspection_review_address')
    def preinspection_review_address(self, request: HttpRequest, *args, **kwargs):
        from django_fsm_log.models import StateLog

        preinspection_id = request.GET.get('preinspection_id')

        obj = PreInspection.objects.get(pk=preinspection_id)

        state_log = StateLog.objects.filter(source_state=PreInspectionStatusEnum.CHANGE_ADDRESS,
                             content_type_id=ContentType.objects.get(
                                 app_label='ujjwala', model='preinspection'
                             ),
                             object_id=preinspection_id).first()

        return JsonResponse({
            "application_id": obj.parent_id,
            "old_address_json": state_log.description if state_log else "",
            "address_json": obj.parent.address_json,
            "latitude": obj.parent.latitude,
            "longitude": obj.parent.longitude
        })

    @action(methods=['get'], detail=False, url_path='preinspection_review')
    def preinspection_review(self, request: HttpRequest, *args, **kwargs):
        preinspection_id = request.GET.get('preinspection_id')

        obj = PreInspection.objects.get(pk=preinspection_id)

        result = {
            "application_id": obj.parent_id,
            "kitchen_photo": obj.documents.get(type=UjjwalaApplicationDocumentsEnum.KITCHEN_PHOTO).link,
            "main_gate_photo": obj.documents.get(type=UjjwalaApplicationDocumentsEnum.MAIN_GATE).link,
            "latitude": obj.parent.latitude,
            "longitude": obj.parent.longitude,
            "accuracy": obj.parent.accuracy
        }
        safety_audio = obj.documents.filter(type=UjjwalaApplicationDocumentsEnum.SAFETY_AUDIO).first()
        result["safety_audio"] = safety_audio.link if safety_audio else ""

        return JsonResponse(result)


class UjjwalaApplicationOtpViewSet(viewsets.ViewSet):
    @action(methods=['get'], detail=False, url_path='send_whatsapp_otp')
    def send_whatsapp_otp(self, request: HttpRequest, *args, **kwargs):
        contact_mobile = request.GET.get('contact_mobile')
        result = send_whatsapp_contact_otp(
            request, contact_mobile
        )
        return JsonResponse({
            "reference_number": result
        })

    @action(methods=['post'], detail=False, url_path='verify_whatsapp_otp')
    def verify_whatsapp_otp(self, request: HttpRequest, *args, **kwargs):
        reference_number = request.data.get('reference_number', '')
        otp = request.data.get('otp', '')
        result = verify_whatsapp_contact_otp(reference_number, otp)
        return JsonResponse(result, safe=False)

    @action(methods=['get'], detail=False, url_path='send_sms_otp')
    def send_sms_otp(self, request: HttpRequest, *args, **kwargs):
        contact_mobile = request.GET.get('contact_mobile')
        result = send_sms_contact_otp(request, contact_mobile)
        return JsonResponse({
            "reference_number": result
        })

    @action(methods=['post'], detail=False, url_path='verify_sms_otp')
    def verify_sms_otp(self, request: HttpRequest, *args, **kwargs):
        reference_number = request.data.get('reference_number', '')
        otp = request.data.get('otp', '')
        result = verify_sms_contact_otp(reference_number, otp)
        return JsonResponse(result, safe=False)
