import io
from functools import wraps

import django_rq
import magic
import requests
from django.conf import settings
from django.db import close_old_connections
from minio import Minio

from domestic_app.utils import get_minio_public_url
from sdms.services import IoclOmcDedup
from ujjwala.enums import RoboSdmsDedeupStatusEnum, PreInspectionStatusEnum, PreInspectionTypeEnum, \
    UjjwalaV2ApplicationStatus, UjjwalaApplicationDocumentsEnum
from ujjwala.forms import ApplicationRejected
from ujjwala.management.commands.ujjwala_file_worker import upload_compressed_file_to_tus
from ujjwala.models import ConnectionDisbursementInvitation, ConnectionDisbursement, PreInspection
from ujjwala.ujjwala_functions import application_needs_to_be_audited, application_needs_to_be_audited_by_id

dedup_portal = IoclOmcDedup('305948', 'Ludhiana@123')

minio_api_client = Minio(
    settings.MINIO_API_ENDPOINT,
    access_key=settings.MINIO_CREDENTIAL.get("access_key"),
    secret_key=settings.MINIO_CREDENTIAL.get("secret_key"),
    secure=False
)

OMC_DEDUP_VERSION = 'V2'


def ensure_db_connection(func):
    @wraps(func)
    def run(*args, **kwargs):
        close_old_connections()
        return func(*args, **kwargs)
    return run


def move_file_to_minio(file_url_to_move, new_file_name, bucket_name, delete_src=True):
    """
    Move given file to minio
    params:
        file_url_to_move: url of file to move
        new_file_name: new name for the file to move
        bucket_name: bucket name where file needs to move
        delete_src: file source file
    Returns New File Url
    """
    print("Moving File Name: {}".format(file_url_to_move))
    doc_file = requests.get(file_url_to_move)

    doc_file_bytes = io.BytesIO(doc_file.content)
    descriptor = magic.detect_from_content(doc_file_bytes.read(2048))
    file_extension = descriptor.mime_type.split('/')[-1]

    if file_extension in ('plain', 'x-empty'):
        return file_url_to_move

    doc_file_name = "{}.{}".format(new_file_name, file_extension)
    doc_file_bytes.seek(0)

    minio_output_result = minio_api_client.put_object(
        bucket_name,
        doc_file_name,
        doc_file_bytes, doc_file_bytes.getbuffer().nbytes,
        content_type=descriptor.mime_type
    )
    # print(minio_output_result.location)

    # Deleting existing file to clear space
    if delete_src:
        del_req = requests.delete(file_url_to_move, headers={"Tus-Resumable": "1.0.0"})

    new_file_url = get_minio_public_url(bucket_name, doc_file_name)
    print("New File Url: {}".format(new_file_url))
    return new_file_url


def do_primary_omc_dedupe_check_v2(id):
    """
    {
        "TRANSACID": "20230923121515-56592777",
        "CON_STATE": null,
        "CDP_ID": null,
        "KYC_ID": null,
        "CONSUMER_NO": null,
        "LPG_ID": null,
        "OMC_CODE": "3",
        "DEDUP_RESULT": "Reject",
        "DEMO_RESULT": null,
        "COUNTERPART": [
            {
                "CON_STATE": "Consumer",
                "CDP_ID": "1328115271",
                "KYC_ID": null,
                "LPG_ID": "10000000111494923",
                "OMC_CODE": "1",
                "DEDUP_TYP": "A",
                "DEDUP_GRPID": "1",
                "SUSPFLAG": null,
                "DISTR_CODE": "188177",
                "DISTR_NAME": "MANASWINI BHARATGAS GRAMIN VITRAK",
                "DISTR_ADDR1": "AT/PO ERABANGA",
                "DISTR_ADDR2": "PS GOP VIA BIRATUNG",
                "DISTR_ADDR3": null,
                "CONS_NAME": "KUNTALA BARAL",
                "CONS_NO": "111494923",
                "CONS_ADDR1": "- W/O-PABITRA MOHAN BARAL",
                "CONS_ADDR2": "AT-KHANDASAHI PO-RAHANGA",
                "CONS_ADDR3": "PURI Odisha",
                "LANDMARK": "PS-GOP",
                "VILL_TOWN": "409424",
                "PIN_CODE": "752110",
                "KYC_DATE": "20210821000000",
                "SV_DATE": null,
                "SEED_DATE": null,
                "INSTL_DATE": "20210907183500",
                "PPAC_DISTCODE": "2222",
                "PPAC_STATCODE": null,
                "CONS_STATUS": "1A",
                "RATION_CARD": null,
                "RELATIONCODE": "F",
                "FAM_MEMBRNAME": "PABITRA MOHAN BARAL",
                "ERROR_CODE": "ZZM_MSGCLS-015",
                "ERROR_MSG": "Duplicate Aadhaar found in CDP"
            }
        ]
    }
    """
    from ujjwala.models import UjjwalaV2Application, PreInspection

    application = UjjwalaV2Application.objects.get(pk=id)
    omc_dedupe_check_passed = True
    iocl_investigation_required = False
    invalid_result = ''

    for fm in application.family_members.all():
        if fm.uid_no in ('999999999999', '666666666666'):
            continue

        resp = dedup_portal.omc_aadhar_dedup(fm.uid_no)
        print(resp)
        counterpart = {}
        if resp.get('DEDUP_RESULT', '') == 'Reject':
            omc_dedupe_check_passed = False
            counterpart = resp.get('COUNTERPART', [])
            if counterpart:
                counterpart = counterpart[0]

                fm.uid_check_result = {
                    "consumer_id": counterpart.get('CONS_NO'),
                    "contact_name": counterpart.get('CONS_NAME'),
                    "phone_number": "",
                    "contact_address": f"{counterpart.get('CONS_ADDR1')} {counterpart.get('CONS_ADDR2')} {counterpart.get('CONS_ADDR3')} {counterpart.get('LANDMARK')} {counterpart.get('VILL_TOWN')}  {counterpart.get('PIN_CODE')} ",
                    "distributor_name": counterpart.get('DISTR_NAME'),
                    "relationship_status": counterpart.get('DEDUP_TYP'),
                    "reason": counterpart.get('ERROR_MSG')
                }
                fm.save()
                invalid_result = invalid_result + "{} {} {} {}<br>".format(
                    fm.relation,
                    fm.uid_check_result.get('distributor_name', ''), fm.uid_check_result.get('consumer_id', ''),
                    fm.uid_check_result.get('contact_address', '')
                )
            else:
                invalid_result = invalid_result + "{} <br>".format(fm.relation)
            print(resp)
        elif resp.get('DEDUP_RESULT', '') == 'Clear':
            print(resp)
            continue
        elif resp.get('ERRORS', []):
            print(resp)
            error = resp.get('ERRORS', [])[0]
            if error['ERROR_CODE'] == '0':
                print(resp)
                continue

        else:
            raise Exception("Technical Error")

        if fm.relation == 'SELF' and counterpart.get('DISTR_CODE') == '305948':
            iocl_investigation_required = True

    if omc_dedupe_check_passed:
        application.robo_sdms_dedup = RoboSdmsDedeupStatusEnum.PROCESSED_AND_UNIQUE
        try:
            obj, created = PreInspection.objects.get_or_create(
                parent_id=application.id,
                status=PreInspectionStatusEnum.KITCHEN_PHOTO,
                type=PreInspectionTypeEnum.SELF
            )
            # application.event_invite_for_ekyc_channel_whatsapp()
            application.event_whatsapp_pre_inspection_type_self(obj.id)
        except:
            pass
    else:
        if iocl_investigation_required:
            application.status = RoboSdmsDedeupStatusEnum.IOCL_INVESTIGATION_REQUIRED
        else:
            form = ApplicationRejected(data={
                'rejected_reason': 'CONNECTION_ALREADY_EXIST',
                'description': invalid_result
            })
            form.is_valid()
            application.robo_sdms_dedup = RoboSdmsDedeupStatusEnum.PROCESSED_AND_DUPLICATE
            # if application.status == 'DOCUMENTS_UPLOADED':
            application.application_rejected(**form.cleaned_data)
            application.event_ioc_dedupe_reject_channel_whatsapp()
    application.save()
    print(application)


@ensure_db_connection
def do_primary_omc_dedupe_check(id):
    if OMC_DEDUP_VERSION == 'V2':
        return do_primary_omc_dedupe_check_v2(id)

    from ujjwala.models import UjjwalaV2Application, PreInspection

    application = UjjwalaV2Application.objects.get(pk=id)
    omc_dedupe_check_passed = True
    iocl_investigation_required = False

    for fm in application.family_members.all():

        if fm.uid_no in ('999999999999', '666666666666'):
            continue

        resp = dedup_portal.omc_aadhar_dedup(fm.uid_no)
        print(resp)

        for omc, status in resp.items():
            if status not in ('Present', 'Not Present'):
                raise Exception(status)

            if status != 'Present':
                continue
            omc_dedupe_check_passed = False

            if fm.relation == 'SELF' and omc == 'IOCL':
                iocl_investigation_required = True

            fm.uid_check_result = {
                'distributor_name': omc,
                'consumer_id': 'NotAvail-CheckWithDistributor',
                'contact_address': ''
            }
            fm.save()

    if omc_dedupe_check_passed:
        application.robo_sdms_dedup = RoboSdmsDedeupStatusEnum.PROCESSED_AND_UNIQUE
        try:
            obj, created = PreInspection.objects.get_or_create(
                parent_id=application.id,
                status=PreInspectionStatusEnum.KITCHEN_PHOTO,
                type=PreInspectionTypeEnum.SELF
            )
            # application.event_invite_for_ekyc_channel_whatsapp()
            application.event_whatsapp_pre_inspection_type_self(obj.id)
        except:
            pass
        application.save()
    else:
        if iocl_investigation_required:
            application.robo_sdms_dedup = RoboSdmsDedeupStatusEnum.IOCL_INVESTIGATION_REQUIRED
        else:
            application.robo_sdms_dedup = RoboSdmsDedeupStatusEnum.ENRICH_REJECTION_DETAILS
    application.save()


def compress_application_documents(application_id):
    """
    Compress Application Documents
    Params:
        application_id: Ujjwala Application Object Id
    """
    from ujjwala.models import UjjwalaV2Application

    application = UjjwalaV2Application.objects.filter(id=application_id).first()
    if not application:
        print("No application with id {} exists".format(application_id))

    print("Application Documents Compressing".format(application_id))

    for customer_doc in application.documents.all():
        print("Customer Doc {} {}".format(customer_doc.type, customer_doc.link))
        if not customer_doc.link:
            print("No url exist for document")
            continue
        success, upload_url, file_size = upload_compressed_file_to_tus(customer_doc.link)
        if success and not customer_doc.link == upload_url:
            customer_doc.link = upload_url
            customer_doc.compressed = True

        customer_doc.file_size = file_size
        customer_doc.save()

    print("Application Documents Family Member Compressing".format(application_id))
    for family_member in application.family_members.all():
        print("UID Front {}".format(family_member.uid_front_link))
        if not family_member.uid_front_link:
            print("No url exist for document")
            continue

        success, upload_url, file_size = upload_compressed_file_to_tus(family_member.uid_front_link)
        if success and not family_member.uid_front_link == upload_url:
            family_member.uid_front_link = upload_url
            family_member.uid_front_compressed = True

        family_member.uid_front_file_size = file_size
        family_member.save()

        print("UID Back {}".format(family_member.uid_back_link))
        if not family_member.uid_back_link:
            print("No url exist for document")
            continue

        success, upload_url, file_size = upload_compressed_file_to_tus(family_member.uid_back_link)
        if success and not family_member.uid_back_link == upload_url:
            family_member.uid_back_link = upload_url
            family_member.uid_back_compressed = True

        family_member.uid_back_file_size = file_size
        family_member.save()


def compress_pre_inspection_documents(parent_id):
    """
    Compress Pre Inspection Documents
    Params:
        parent_id = Pre Inspection Object Id
    """
    from ujjwala.models import PreInspectionDocuments

    docs = PreInspectionDocuments.objects.filter(parent_id=parent_id, compressed=False)
    for customer_doc in docs:
        print("PreInspection Doc {} {} {}".format(customer_doc.parent_id, customer_doc.type, customer_doc.link))
        if not customer_doc.link:
            print("No url exist for document")
            continue
        if customer_doc.type in (
            UjjwalaApplicationDocumentsEnum.PHYSICAL_LEGAL_DOCUMENT,
            UjjwalaApplicationDocumentsEnum.INSTALLATION_DOCUMENT,
            UjjwalaApplicationDocumentsEnum.SAFETY_AUDIO,
            UjjwalaApplicationDocumentsEnum.SV,
        ):
            continue
        success, upload_url, file_size = upload_compressed_file_to_tus(customer_doc.link)
        customer_doc.file_size = file_size
        if success and not customer_doc.link == upload_url:
            customer_doc.link = upload_url
            customer_doc.compressed = True
        customer_doc.save()


def compress_connection_disbursement_documents(parent_id):
    """
    Compress Connection Disbursement Documents
    Params:
        parent_id: Connection Disbursement Object Id
    """
    from ujjwala.models import ConnectionDisbursementDocuments

    docs = ConnectionDisbursementDocuments.objects.filter(parent_id=parent_id, compressed=False)
    for customer_doc in docs:
        print("Disb Doc {} {} {}".format(customer_doc.parent_id, customer_doc.type, customer_doc.link))
        if not customer_doc.link:
            print("No url exist for document")
            continue
        if customer_doc.type in (
            UjjwalaApplicationDocumentsEnum.INSTALLATION_DOCUMENT,
            UjjwalaApplicationDocumentsEnum.PHYSICAL_LEGAL_DOCUMENT,
            UjjwalaApplicationDocumentsEnum.SAFETY_AUDIO,
            UjjwalaApplicationDocumentsEnum.SV,
        ):
            continue
        success, upload_url, file_size = upload_compressed_file_to_tus(customer_doc.link)
        customer_doc.file_size = file_size
        if success and not customer_doc.link == upload_url:
            customer_doc.link = upload_url
            customer_doc.compressed = True
        customer_doc.save()


def move_ujjwala_application_files_to_minio(application_id):
    """
    Moves Ujjwala Application Files To Minio
    Params:
        application_id: Ujjwala Application Id
    """
    from ujjwala.models import UjjwalaV2Application

    obj = UjjwalaV2Application.objects.get(id=application_id)

    for doc in obj.documents.all():
        if not doc.link:
            print("No url exist for document")
            continue

        if not doc.link.find("tus") == -1:
            new_file_url = move_file_to_minio(
                doc.link,
                "ujjwala_app_{}_{}".format(obj.id, doc.type.lower()),
                settings.MINIO_UJJWALA_BUCKET_NAME
            )

            if not doc.link == new_file_url:
                # Saving Link of Original File
                doc.original_link = doc.link
                doc.link = new_file_url
                doc.save()
            else:
                print("File Could Not Moved {}".format(doc.link))
        else:
            print("Already moved {}".format(doc.link))

    for fm in obj.family_members.all():
        if not fm.uid_front_link:
            print("No url exist for document")
            continue
        if not fm.uid_front_link.find("tus") == -1:
            new_file_url = move_file_to_minio(
                fm.uid_front_link,
                "ujjwala_app_{}_{}_uid_front".format(obj.id, fm.relation),
                settings.MINIO_UJJWALA_BUCKET_NAME
            )
            if not fm.uid_front_link == new_file_url:
                # Saving Link of Original File
                fm.uid_original_front_link = fm.uid_front_link
                fm.uid_front_link = new_file_url
                fm.save()
            else:
                print("File Could Not Moved {}".format(fm.uid_front_link))
        else:
            print("Already moved {}".format(fm.uid_front_link))

        if not fm.uid_back_link:
            print("No url exist for document")
            continue
        if not fm.uid_back_link.find("tus") == -1:
            new_file_url = move_file_to_minio(
                fm.uid_back_link,
                "ujjwala_app_{}_{}_uid_back".format(obj.id, fm.relation),
                settings.MINIO_UJJWALA_BUCKET_NAME
            )
            if not fm.uid_back_link == new_file_url:
                # Saving Link of Original File
                fm.uid_original_back_link = fm.uid_back_link
                fm.uid_back_link = new_file_url
                fm.save()
            else:
                print("File Could Not Moved {}".format(fm.uid_back_link))
        else:
            print("Already moved {}".format(fm.uid_back_link))


def move_pre_inspection_files_to_minio(parent_id):
    """
    Move Pre Inspection Documents To MinIO
    Params:
        parent_id: Ujjwala Application Id
    """
    from ujjwala.models import PreInspection

    pi_obj = PreInspection.objects.filter(parent_id=parent_id).first()

    if not pi_obj:
        return

    for doc in pi_obj.documents.all():
        if not doc.link:
            print("No url exist for document")
            continue

        print(doc.link)
        if not doc.link.find("tus") == -1:
            print("Moving File: {}".format(doc.link))
            new_file_url = move_file_to_minio(
                doc.link,
                "ujjwala_app_{}_pi_{}_{}".format(
                    pi_obj.parent_id, pi_obj.id, doc.type.lower()
                ),
                settings.MINIO_UJJWALA_BUCKET_NAME
            )

            if not doc.link == new_file_url:
                # Saving Link of Original File
                doc.original_link = doc.link
                doc.link = new_file_url
                doc.save()
            else:
                print("File Could Not Moved {}".format(doc.link))
        else:
            print("Already moved {}".format(doc.link))


def move_connection_disbursement_files_to_minio(parent_id):
    """
    Move Connection Disbursement Files To MinIO
    Params:
        parent_id: Ujjwala Application Id
    """
    from ujjwala.models import ConnectionDisbursement

    cd_obj = ConnectionDisbursement.objects.filter(parent_id=parent_id).first()

    if not cd_obj:
        return

    for doc in cd_obj.documents.all():
        if not doc.link:
            print("No url exist for document")
            continue
        if not doc.link.find("tus") == -1:
            print("Moving File: {}".format(doc.link))
            new_file_url = move_file_to_minio(
                doc.link,
                "ujjwala_app_{}_cd_{}_{}".format(
                    cd_obj.parent_id, cd_obj.parent_id, doc.type.lower()
                ),
                settings.MINIO_UJJWALA_BUCKET_NAME
            )

            if not doc.link == new_file_url:
                # Saving Link of Original File
                doc.original_link = doc.link
                doc.link = new_file_url
                doc.save()
            else:
                print("File Could Not Moved {}".format(doc.link))
        else:
            print("Already moved {}".format(doc.link))


def move_sv_files_to_minio(parent_id, application_id):
    """
    Move Connection Disbursement Files To MinIO
    Params:
        parent_id: Connection Disbursement Object Id
    """

    invitation_obj = ConnectionDisbursementInvitation.objects.filter(parent_id=parent_id).first()

    if not invitation_obj:
        print("No Invitation Exist")
        return

    if not invitation_obj.sv_link:
        print("No url exist for document")
        return

    if not invitation_obj.sv_link.find("tus") == -1:
        new_file_url = move_file_to_minio(
            invitation_obj.sv_link,
            "sv_{}".format(
                application_id
            ),
            settings.MINIO_UJJWALA_BUCKET_NAME
        )

        if not invitation_obj.sv_link == new_file_url:
            # Saving Link of Original File
            invitation_obj.sv_link = new_file_url
            invitation_obj.save()
        else:
            print("File Could Not Moved {}".format(invitation_obj.sv_link))
    else:
        print("Already moved {}".format(invitation_obj.sv_link))


def compress_and_move_all_ujjwala_docs_to_minio(application_id):

    compress_application_documents(application_id)
    move_ujjwala_application_files_to_minio(application_id)

    pi_obj = PreInspection.objects.filter(parent_id=application_id)
    if pi_obj:
        pi_obj = pi_obj.first()

        print("Compressing Pre Inspection Documents")
        compress_pre_inspection_documents(pi_obj.id)

        print("Moving Pre Inspection Documents")
        move_pre_inspection_files_to_minio(application_id)
    else:
        print("No Pre Inspection Exist")

    cd_obj = ConnectionDisbursement.objects.filter(parent_id=application_id)
    if cd_obj:
        cd_obj = cd_obj.first()

        print("Compressing Connection Disbursement Documents")
        compress_connection_disbursement_documents(cd_obj.id)

        print("Moving Connection Disbursement Documents")
        move_connection_disbursement_files_to_minio(application_id)

        print("Moving SV To MinIO")
        move_sv_files_to_minio(cd_obj.id, application_id)
    else:
        print("No Connection Disbursement Exist")


@ensure_db_connection
def compress_and_move_ujjwala_application_docs_to_minio(application_id):
    result = django_rq.enqueue(compress_application_documents, args=(application_id,))
    move_result = django_rq.enqueue(
    	move_ujjwala_application_files_to_minio,
    	args=(application_id,),
    	depends_on=result
    )
    print(move_result)
    # django_rq.enqueue(
    #     delete_files,
    #     args=(application_id,),
    #     depends_on=move_result
    # )


@ensure_db_connection
def compress_and_move_cd_docs_to_minio(application_id):
    result = django_rq.enqueue(compress_connection_disbursement_documents, args=(application_id,))
    django_rq.enqueue(
    	move_connection_disbursement_files_to_minio,
    	args=(application_id,),
    	depends_on=result
    )


@ensure_db_connection
def compress_and_move_pi_docs_to_minio(application_id):
    result = django_rq.enqueue(compress_pre_inspection_documents, args=(application_id,))
    move_result = django_rq.enqueue(
    	move_connection_disbursement_files_to_minio,
    	args=(application_id,),
    	depends_on=result
    )


@ensure_db_connection
def compress_and_move_all_docs_to_minio(application_id):
    django_rq.enqueue(
        "ujjwala.jobs.compress_and_move_ujjwala_application_docs_to_minio",
        args=(application_id,)
    )

    django_rq.enqueue(
        "ujjwala.jobs.move_pre_inspection_files_to_minio",
        args=(application_id,)
    )

    django_rq.enqueue(
        "ujjwala.jobs.move_connection_disbursement_files_to_minio",
        args=(application_id,)
    )


@ensure_db_connection
def is_application_ready_for_disbursement(parent_id):
    from ujjwala.models import UjjwalaV2Application, PreInspection

    application_id = parent_id

    application = UjjwalaV2Application.objects.get(id=application_id)
    pre_inspection = PreInspection.objects.filter(parent=application)

    if pre_inspection.exists():
        pre_inspection = pre_inspection.first()
        if application.status == UjjwalaV2ApplicationStatus.NIC_CLEARED and \
                pre_inspection.status == PreInspectionStatusEnum.ACCEPTED:
            application.transition_ready_for_disbursement()
            application.save()
    else:
        obj = PreInspection.objects.create(
            parent_id=application.id,
            status=PreInspectionStatusEnum.KITCHEN_PHOTO,
            type=PreInspectionTypeEnum.SELF
        )
        obj.parent.event_whatsapp_pre_inspection_type_self(obj.pk)


def enqueue_dedupe_and_audit_jobs(application_id, data):
    dedupe_job = django_rq.enqueue("ujjwala.jobs.do_primary_omc_dedupe_check", args=(application_id,))

    django_rq.enqueue(
        move_application_for_audit,
        args=(application_id, data,),
        depends_on=dedupe_job
    )


def move_application_for_audit(application_id, data):
    from ujjwala.models import UjjwalaV2Application

    application = UjjwalaV2Application.objects.get(pk=application_id)

    if not application.robo_sdms_dedup == RoboSdmsDedeupStatusEnum.PROCESSED_AND_UNIQUE:
        return False

    move_to_audit = application_needs_to_be_audited(data)
    if move_to_audit:
        application.transition_audit_application(audit_points=move_to_audit)
        application.save()


def move_application_for_audit_by_id(application_id):
    from ujjwala.models import UjjwalaV2Application

    obj = UjjwalaV2Application.objects.get(id=application_id)
    move_to_audit = application_needs_to_be_audited_by_id(obj)
    if move_to_audit:
        application = UjjwalaV2Application.objects.get(pk=application_id)
        application.transition_audit_application(audit_points=move_to_audit)
        application.save()
