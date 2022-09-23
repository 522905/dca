import io
import random
import re
import string
import zipfile
import base64
from datetime import datetime, timedelta
from functools import wraps
from time import timezone

import magic
import requests
import track
from PyPDF2 import PdfFileMerger
from django.conf import settings
from django.contrib.contenttypes.models import ContentType
from django.core.signing import Signer
from django.db.models import Q, QuerySet
from django.http import HttpResponse, HttpResponseRedirect
from django.template import loader
from django.urls import reverse
from django_currentuser.middleware import get_current_user
from django_rq import job

from communication_log.models import CommunicationLog
from reference_data.models import TokensExcluded
from ujjwala.enums import UjjwalaApplicationDocumentsEnum, FamilyMemberRelationEnum, ResidentialStatusEnum, \
    MaritalStatusEnum, UjjwalaV2ApplicationStatus, PreInspectionStatusEnum, RoboSdmsDedeupStatusEnum, \
    PrintDocumentsTypeEnum
from datetime import datetime


COMPILED_REGEX_PATTERN_AADHAR_EXISTS = re.compile(
    """Aadhaar already exists for customer (?P<contact_name>.*?) of (?P<distributor_name>.*)\(SBL-EXL-00151\)"""
)

COMPILED_REGEX_PATTERN_BPC_1 = re.compile(
    "Available with (?P<omc>.*). Already exists with lpgid: (?P<consumer_id>.*) and distcode: (?P<distributor_name>.*)"
)

COMPILED_REGEX_PATTERN_BPC_2 = re.compile(
    "Available with (?P<omc>.*). Duplicate UID already exists (?:in|with) (?:New KYC Family with)?(?P<consumer_id>.*)"
)

COMPILED_REGEX_PATTERN_OTHERS = re.compile(
    "Available with (?P<omc>.*) LPGId : (?P<consumer_id>.*) DistName : (?P<distributor_name>.*)"
)

SMS_OTP_MESSAGE = \
"""
Dear Customer, 
Your Verification code for {{for}} is {{code}}
"""

PDF_COMPRESSION_OPTIONS = {
    "pageSize": "A4", "imageDpi": 150, "imageQuality": 80, "lowquality": True
}

VALID_CHARS_IN_NAME_PATTERN = r'^[A-Za-z. ]+$'
RELATION_VALIDATION_PATTERN = r'.(fathe|moth|husba).'


def valid_file_uploaded(url):
    res = requests.head(url, headers={"Tus-Resumable": "1.0.0"})
    header_info = res.headers
    upload_length = int(header_info['Upload-Length'])
    if upload_length == 0 or int(header_info['Upload-Offset']) == 0:
        return False, upload_length
    elif header_info['Upload-Length'] != header_info['Upload-Offset']:
        return False, upload_length
    else:
        return True, upload_length


def get_compressed_file_link_jpeg(url):
    res = requests.head(url, headers={"Tus-Resumable": "1.0.0"})
    header_info = res.headers

    if int(header_info['Upload-Length']) <= 499000:
        file_type = header_info['Upload-Metadata'].split(',')[0].split(' ')[1]
        if 'webp' not in base64.b64decode(file_type).decode():
            return url

    return f'http://dca.arungas.com:6988/unsafe/fit-in/1920x1080/filters:format(jpeg)/{url}'


def valid_file_size(file):
    return len(file.content) <= 499000


def download_pre_installation_documents(obj):
    attachments = []

    if obj.version != 'V1':
        # customer_signature_file = obj.documents.filter(
        #     type=UjjwalaApplicationDocumentsEnum.CUSTOMER_SIGNATURE
        # ).first().link

        pre_inspection_html_template = loader.get_template("ujjwala/forms/pre_inspection_form.html")
        pre_inspection_html = pre_inspection_html_template.render({
            'name': obj.name,
            # 'customer_signature_file': customer_signature_file,
            'date': datetime.now().strftime("%d-%m-%Y")
        })

        pre_inspection_pdf = requests.post(
            settings.HTML_TO_PDF_SERVER_URL,
            json={
                "content": pre_inspection_html,
                "options": PDF_COMPRESSION_OPTIONS
            }
        )
        attachments.append(('pre_installation_form.pdf', pre_inspection_pdf))

        if obj.version in ('V3', 'V4'):
            obj.address = ' '.join([obj.address_json.get(r, '') for r in obj.address_json])

    customer_docs = obj.documents.exclude(
        Q(type=UjjwalaApplicationDocumentsEnum.KITCHEN_PHOTO) | Q(type=UjjwalaApplicationDocumentsEnum.MAIN_GATE)
    ).all()

    for customer_doc in customer_docs:
        doc_file = requests.get("{}{}".format(settings.THUMBOR_URL, customer_doc.link))
        doc_file_bytes = io.BytesIO(doc_file.content)
        descriptor = magic.detect_from_content(doc_file_bytes.read(2048))
        file_extension = descriptor.mime_type.split('/')[-1]
        attachments.append(('{}.{}'.format(customer_doc.type, file_extension), doc_file))

    documents_zip = io.BytesIO()

    with zipfile.ZipFile(documents_zip, mode='w', compression=zipfile.ZIP_DEFLATED) as zf:
        for key, value in attachments:
            zf.writestr(key, value.content)

    # Grab ZIP file from in-memory, make response with correct MIME-type
    resp = HttpResponse(documents_zip.getvalue(), content_type="application/x-zip-compressed")
    # ..and correct content-disposition
    resp['Content-Disposition'] = 'attachment; filename=%s' % 'pre_inspection_{}_docs.zip'.format(obj.id)

    return resp


def download_ujjwala_documents(obj):
    attachments = []

    if obj.version != 'V1':
        customer_signature_file = obj.documents.filter(
            type=UjjwalaApplicationDocumentsEnum.CUSTOMER_SIGNATURE
        ).first().link

        self_doc = obj.family_members.filter(relation=FamilyMemberRelationEnum.SELF).first()

        relationship_name = ''

        if obj.residential_status == ResidentialStatusEnum.LIVING_WITH_FAMILY:
            if obj.marital_status == MaritalStatusEnum.MARRIED:
                relationship_name = obj.family_members.filter(relation=FamilyMemberRelationEnum.HUSBAND).first().name
            elif obj.marital_status == MaritalStatusEnum.UNMARRIED:
                relationship_name = obj.family_members.filter(relation=FamilyMemberRelationEnum.FATHER).first().name

        ujjwala_declaration_html_template = loader.get_template("ujjwala/forms/ujjwala_declaration_form.html")
        ujjwala_declaration_html = ujjwala_declaration_html_template.render({
            'app_id': obj.parent.parent_id,
            'name': obj.name,
            'uid': list(self_doc.uid_no),
            'age': '{}'.format(str(datetime.now().year - self_doc.dob.year)),
            'relation_name': relationship_name,
            'customer_signature_file': customer_signature_file,
            'date': datetime.now().strftime("%d-%m-%Y")
        })

        ujjwala_declaration_pdf = requests.post(
            settings.HTML_TO_PDF_SERVER_URL,
            json={
                "content": ujjwala_declaration_html,
                "options": PDF_COMPRESSION_OPTIONS
            }
        )
        attachments.append(('annexure_14_points.pdf', ujjwala_declaration_pdf))

        if obj.residential_status == ResidentialStatusEnum.LIVING_ALONE:
            occupancy_template_html = "ujjwala/forms/single_occupancy_form.html"
            occupancy_file_name = "single_occupancy"
        else:
            occupancy_template_html = "ujjwala/forms/family_occupancy_form.html"
            occupancy_file_name = "family_occupancy"

        if obj.version not in ('V1', 'V2'):
            obj.address = ' '.join([obj.address_json.get(r, '') for r in obj.address_json])

        occupancy_form_html_template = loader.get_template(occupancy_template_html)
        occupancy_form_html = occupancy_form_html_template.render({
            'obj': obj,
            'customer_signature_file': customer_signature_file
        })

        occupancy_form_pdf = requests.post(
            settings.HTML_TO_PDF_SERVER_URL,
            json={
                "content": occupancy_form_html,
                "options": PDF_COMPRESSION_OPTIONS
            }
        )

        attachments.append(('{}.pdf'.format(occupancy_file_name), occupancy_form_pdf))

    customer_docs = obj.documents.exclude(
        type=UjjwalaApplicationDocumentsEnum.CUSTOMER_SIGNATURE
    ).all()

    for customer_doc in customer_docs:
        doc_file = requests.get("{}{}".format(settings.THUMBOR_URL, customer_doc.link))
        doc_file_bytes = io.BytesIO(doc_file.content)
        descriptor = magic.detect_from_content(doc_file_bytes.read(2048))
        file_extension = descriptor.mime_type.split('/')[-1]
        attachments.append(('{}.{}'.format(customer_doc.type, file_extension), doc_file))

    family_members_doc = obj.family_members.all()

    for family_member in family_members_doc:

        uid_front_doc_file = requests.get(family_member.uid_front_link)
        if not valid_file_size(uid_front_doc_file):
            uid_front_doc_file = requests.get("{}{}".format(settings.THUMBOR_URL, family_member.uid_front_link))

        uid_back_doc_file = requests.get(family_member.uid_back_link)
        if not valid_file_size(uid_back_doc_file):
            uid_back_doc_file = requests.get("{}{}".format(settings.THUMBOR_URL, family_member.uid_back_link))

        uid_front_doc_file_bytes = io.BytesIO(uid_front_doc_file.content)
        uid_back_doc_file_bytes = io.BytesIO(uid_back_doc_file.content)

        uid_front_descriptor = magic.detect_from_content(uid_front_doc_file_bytes.read(2048))
        uid_back_descriptor = magic.detect_from_content(uid_back_doc_file_bytes.read(2048))

        uid_front_doc_file_extension = uid_front_descriptor.mime_type.split('/')[-1]
        uid_back_doc_file_extension = uid_back_descriptor.mime_type.split('/')[-1]

        attachments.append(
            ('{}_uid_front.{}'.format(family_member.relation, uid_front_doc_file_extension), uid_front_doc_file)
        )
        attachments.append(
            ('{}_uid_back.{}'.format(family_member.relation, uid_back_doc_file_extension), uid_back_doc_file)
        )

    documents_zip = io.BytesIO()

    with zipfile.ZipFile(documents_zip, mode='w', compression=zipfile.ZIP_DEFLATED) as zf:
        for key, value in attachments:
            zf.writestr(key, value.content)

    # Grab ZIP file from in-memory, make response with correct MIME-type
    resp = HttpResponse(documents_zip.getvalue(), content_type="application/x-zip-compressed")
    # ..and correct content-disposition
    resp['Content-Disposition'] = 'attachment; filename=%s' % 'ujjwala_{}_legal_docs.zip'.format(obj.id)

    return resp


def download_ujjwala_legal_docs_to_upload(obj, signature=True):
    attachments = []
    if obj.version == 'V1':
        signature = False
    if signature:
        customer_signature_file = obj.documents.filter(
            type=UjjwalaApplicationDocumentsEnum.CUSTOMER_SIGNATURE
        ).first().link
    else:
        customer_signature_file = None

    self_doc = obj.family_members.filter(relation=FamilyMemberRelationEnum.SELF).first()

    relationship_name = ''

    if obj.residential_status == ResidentialStatusEnum.LIVING_WITH_FAMILY:
        if obj.marital_status == MaritalStatusEnum.MARRIED:
            relationship_name = obj.family_members.filter(relation=FamilyMemberRelationEnum.HUSBAND).first().name
        elif obj.marital_status == MaritalStatusEnum.UNMARRIED:
            relationship_name = obj.family_members.filter(relation=FamilyMemberRelationEnum.FATHER).first().name

    ujjwala_declaration_html_template = loader.get_template("ujjwala/forms/ujjwala_declaration_form.html")
    ujjwala_declaration_html = ujjwala_declaration_html_template.render({
        'app_id': obj.id,
        'name': obj.name,
        'uid': list(self_doc.uid_no),
        'age': '{}'.format(str(datetime.now().year - self_doc.dob.year)),
        'relation_name': relationship_name,
        'customer_signature_file': customer_signature_file,
        'date': datetime.now().strftime("%d-%m-%Y")
    })

    ujjwala_declaration_pdf = requests.post(
        settings.HTML_TO_PDF_SERVER_URL,
        json={
            "content": ujjwala_declaration_html,
            "options": PDF_COMPRESSION_OPTIONS
        }
    )
    attachments.append(('annexure_14_points.pdf', ujjwala_declaration_pdf))

    if obj.residential_status == ResidentialStatusEnum.LIVING_ALONE:
        occupancy_template_html = "ujjwala/forms/single_occupancy_form.html"
        occupancy_file_name = "single_occupancy"
    else:
        occupancy_template_html = "ujjwala/forms/family_occupancy_form.html"
        occupancy_file_name = "family_occupancy"

    if obj.version not in ('V1', 'V2'):
        obj.address = ' '.join([obj.address_json.get(r, '') for r in obj.address_json])

    occupancy_form_html_template = loader.get_template(occupancy_template_html)
    occupancy_form_html = occupancy_form_html_template.render({
        'obj': obj,
        'customer_signature_file': customer_signature_file
    })

    occupancy_form_pdf = requests.post(
        settings.HTML_TO_PDF_SERVER_URL,
        json={
            "content": occupancy_form_html,
            "options": PDF_COMPRESSION_OPTIONS
        }
    )

    attachments.append(('{}.pdf'.format(occupancy_file_name), occupancy_form_pdf))

    # customer_docs = obj.documents.exclude(
    #     type=UjjwalaApplicationDocumentsEnum.CUSTOMER_SIGNATURE
    # ).all()
    #
    # for customer_doc in customer_docs:
    #     doc_file = requests.get("{}{}".format(settings.THUMBOR_URL, customer_doc.link))
    #     doc_file_bytes = io.BytesIO(doc_file.content)
    #     descriptor = magic.detect_from_content(doc_file_bytes.read(2048))
    #     file_extension = descriptor.mime_type.split('/')[-1]
    #     attachments.append(('{}.{}'.format(customer_doc.type, file_extension), doc_file))

    family_members_doc = obj.family_members.all()
    #.exclude(relation=FamilyMemberRelationEnum.SELF)

    for family_member in family_members_doc:
        uid_front_doc_file = get_compressed_file_link_jpeg(family_member.uid_front_link)
        uid_front_doc_file = requests.get(uid_front_doc_file)

        # uid_back_doc_file = requests.get(family_member.uid_back_link)
        # if not valid_file_size(uid_back_doc_file):
        #     uid_back_doc_file = requests.get("{}{}".format(settings.THUMBOR_URL, family_member.uid_back_link))

        uid_front_doc_file_bytes = io.BytesIO(uid_front_doc_file.content)
        # uid_back_doc_file_bytes = io.BytesIO(uid_back_doc_file.content)

        uid_front_descriptor = magic.detect_from_content(uid_front_doc_file_bytes.read(2048))
        # uid_back_descriptor = magic.detect_from_content(uid_back_doc_file_bytes.read(2048))

        uid_front_doc_file_extension = uid_front_descriptor.mime_type.split('/')[-1]
        # uid_back_doc_file_extension = uid_back_descriptor.mime_type.split('/')[-1]

        attachments.append(
            ('{}_uid_front.{}'.format(family_member.relation, uid_front_doc_file_extension), uid_front_doc_file)
        )
        # attachments.append(
        #     ('{}_uid_back.{}'.format(family_member.relation, uid_back_doc_file_extension), uid_back_doc_file)
        # )

    documents_zip = io.BytesIO()

    with zipfile.ZipFile(documents_zip, mode='w', compression=zipfile.ZIP_DEFLATED) as zf:
        for key, value in attachments:
            zf.writestr(key, value.content)

    # Grab ZIP file from in-memory, make response with correct MIME-type
    resp = HttpResponse(documents_zip.getvalue(), content_type="application/x-zip-compressed")
    # ..and correct content-disposition
    resp['Content-Disposition'] = 'attachment; filename=%s' % 'ujjwala_{}_legal_docs.zip'.format(obj.id)

    return resp


def download_ujjwala_physical_legal_docs(obj):
    attachments = []

    self_doc = obj.family_members.filter(relation=FamilyMemberRelationEnum.SELF).first()

    from ujjwala.models import PreInspection

    pre_inspection = PreInspection.objects.exclude(
        status=PreInspectionStatusEnum.REJECTED
    ).get(parent_id=obj.id)

    relationship_name = ''

    if obj.residential_status == ResidentialStatusEnum.LIVING_WITH_FAMILY:
        if obj.marital_status == MaritalStatusEnum.MARRIED:
            relationship_name = obj.family_members.filter(relation=FamilyMemberRelationEnum.HUSBAND).first().name
        elif obj.marital_status == MaritalStatusEnum.UNMARRIED:
            relationship_name = obj.family_members.filter(relation=FamilyMemberRelationEnum.FATHER).first().name

    ujjwala_declaration_html_template = loader.get_template("ujjwala/forms/ujjwala_declaration_form.html")
    ujjwala_declaration_html = ujjwala_declaration_html_template.render({
        'app_id': obj.id,
        'name': obj.name,
        'uid': list(self_doc.uid_no),
        'age': '{}'.format(str(datetime.now().year - self_doc.dob.year)),
        'relation_name': relationship_name,
        # 'customer_signature_file': customer_signature_file,
        'customer_signature_file': '',
        'date': datetime.now().strftime("%d-%m-%Y")
    })

    ujjwala_declaration_pdf = requests.post(
        settings.HTML_TO_PDF_SERVER_URL,
        json={
            "content": ujjwala_declaration_html,
            "options": PDF_COMPRESSION_OPTIONS
        }
    )
    attachments.append(('annexure_14_points.pdf', ujjwala_declaration_pdf))

    if obj.residential_status == ResidentialStatusEnum.LIVING_ALONE:
        occupancy_template_html = "ujjwala/forms/single_occupancy_form.html"
        occupancy_file_name = "single_occupancy"
    else:
        occupancy_template_html = "ujjwala/forms/family_occupancy_form.html"
        occupancy_file_name = "family_occupancy"

    if obj.version not in ('V1', 'V2'):
        obj.address = ' '.join([obj.address_json.get(r, '') for r in obj.address_json])

    occupancy_form_html_template = loader.get_template(occupancy_template_html)
    occupancy_form_html = occupancy_form_html_template.render({
        'obj': obj,
        # 'customer_signature_file': customer_signature_file
        'customer_signature_file': ''
    })

    occupancy_form_pdf = requests.post(
        settings.HTML_TO_PDF_SERVER_URL,
        json={
            "content": occupancy_form_html,
            "options": PDF_COMPRESSION_OPTIONS
        }
    )

    attachments.append(('{}.pdf'.format(occupancy_file_name), occupancy_form_pdf))
    ujjwala_pre_inspection_html_template = loader.get_template("ujjwala/forms/pre_inspection_form.html")
    ujjwala_pre_inspection_html = ujjwala_pre_inspection_html_template.render({
        'obj': pre_inspection
    })

    ujjwala_pre_inspection_pdf = requests.post(
        settings.HTML_TO_PDF_SERVER_URL,
        json={
            "content": ujjwala_pre_inspection_html,
            "options": PDF_COMPRESSION_OPTIONS
        }
    )
    attachments.append(('pre_inspection.pdf', ujjwala_pre_inspection_pdf))

    merger = PdfFileMerger()
    temp_files = []
    for key, value in attachments:
        file = io.BytesIO()
        file.write(value.content)
        temp_files.append(file)
        merger.append(file, import_bookmarks=False)

    myio = io.BytesIO()
    merger.write(myio)
    merger.close()

    [f.close() for f in temp_files]

    myio.seek(0)

    resp = HttpResponse(myio.getvalue(), content_type="application/pdf")
    resp['Content-Disposition'] = 'attachment; filename=%s' % 'ujjwala_physical_{}_legal_docs.pdf'.format(obj.id)
    return resp


def get_salutation(family_member):
    if family_member.relation in ('HUSBAND', 'FATHER'):
        return 'Mr.'
    if family_member.relation == 'MOTHER':
        return 'Mrs.'
    if family_member.relation == 'SELF':
        if family_member.parent.marital_status == 'MARRIED':
            return 'Mrs.'
        else:
            return 'Miss'
    return ''


def is_ekyc_required(application):
    if application.status == UjjwalaV2ApplicationStatus.DOCUMENTS_UPLOADED:
        return True
    if application.status == UjjwalaV2ApplicationStatus.EKYC_ACCEPTED and not application.consumer_id:
        return True
    return False


def get_existing_duplicate_applications_detail(all_applications):
    applications = all_applications.exclude(
        status__in=(
            UjjwalaV2ApplicationStatus.APPLICATION_REJECTED,
            UjjwalaV2ApplicationStatus.OMC_REJECTED,
            UjjwalaV2ApplicationStatus.EKYC_REJECTED
        )
    )
    if not applications.exists():
        applications = all_applications

    return_data = {
        "applications": [
            {
                "id": application.id,
                "name": application.name,
                "status": application.status
            } for application in applications
        ]
    }

    if applications.count() > 1:
        return {
            "msg": "MULTIPLE_APPLICATIONS",
            "ekyc_required": True,
            "data": return_data
        }

    elif applications.count() == 1:
        application = applications.first()
        return {
            "msg": application.status,
            "ekyc_required": is_ekyc_required(application),
            "data": return_data
        }


def id_generator(size=6, chars=string.ascii_uppercase + string.digits):
    return ''.join(random.choice(chars) for _ in range(size))


def __get_ref_no__():
    return 'PI{}{}'.format(
        datetime.now().strftime('%y%m%d'),
        id_generator(4, chars=string.ascii_uppercase)
    ).upper()


def get_ujjwala_legal_docs_temp_path(obj):
    attachments = []

    if obj.version != 'V1':
        # customer_signature_file = obj.documents.filter(
        #     type=UjjwalaApplicationDocumentsEnum.CUSTOMER_SIGNATURE
        # ).first().link

        self_doc = obj.family_members.filter(relation=FamilyMemberRelationEnum.SELF).first()

        from ujjwala.models import PreInspection
        pre_inspection = PreInspection.objects.get(
            parent_id=obj.id, status=PreInspectionStatusEnum.SUBMITTED
        )

        relationship_name = ''

        if obj.residential_status == ResidentialStatusEnum.LIVING_WITH_FAMILY:
            if obj.marital_status == MaritalStatusEnum.MARRIED:
                relationship_name = obj.family_members.filter(relation=FamilyMemberRelationEnum.HUSBAND).first().name
            elif obj.marital_status == MaritalStatusEnum.UNMARRIED:
                relationship_name = obj.family_members.filter(relation=FamilyMemberRelationEnum.FATHER).first().name

        ujjwala_declaration_html_template = loader.get_template("ujjwala/forms/ujjwala_declaration_form.html")
        ujjwala_declaration_html = ujjwala_declaration_html_template.render({
            'app_id': obj.parent.parent_id,
            'name': obj.name,
            'uid': list(self_doc.uid_no),
            'age': '{}'.format(str(datetime.now().year - self_doc.dob.year)),
            'relation_name': relationship_name,
            # 'customer_signature_file': customer_signature_file,
            'customer_signature_file': '',
            'date': datetime.now().strftime("%d-%m-%Y")
        })

        ujjwala_declaration_pdf = requests.post(
            settings.HTML_TO_PDF_SERVER_URL,
            json={
                "content": ujjwala_declaration_html,
                "options": PDF_COMPRESSION_OPTIONS
            }
        )
        attachments.append(('annexure_14_points.pdf', ujjwala_declaration_pdf))

        if obj.residential_status == ResidentialStatusEnum.LIVING_ALONE:
            occupancy_template_html = "ujjwala/forms/single_occupancy_form.html"
            occupancy_file_name = "single_occupancy"
        else:
            occupancy_template_html = "ujjwala/forms/family_occupancy_form.html"
            occupancy_file_name = "family_occupancy"

        if obj.version not in ('V1', 'V2'):
            obj.address = ' '.join([obj.address_json.get(r, '') for r in obj.address_json])

        occupancy_form_html_template = loader.get_template(occupancy_template_html)
        occupancy_form_html = occupancy_form_html_template.render({
            'obj': obj,
            # 'customer_signature_file': customer_signature_file
            'customer_signature_file': ''
        })

        occupancy_form_pdf = requests.post(
            settings.HTML_TO_PDF_SERVER_URL,
            json={
                "content": occupancy_form_html,
                "options": PDF_COMPRESSION_OPTIONS
            }
        )

        attachments.append(('{}.pdf'.format(occupancy_file_name), occupancy_form_pdf))
        ujjwala_pre_inspection_html_template = loader.get_template("ujjwala/forms/pre_inspection_form.html")
        ujjwala_pre_inspection_html = ujjwala_pre_inspection_html_template.render({
            'obj': pre_inspection
        })

        ujjwala_pre_inspection_pdf = requests.post(
            settings.HTML_TO_PDF_SERVER_URL,
            json={
                "content": ujjwala_pre_inspection_html,
                "options": PDF_COMPRESSION_OPTIONS
            }
        )
        attachments.append(('pre_inspection.pdf', ujjwala_pre_inspection_pdf))

    # documents_zip = io.BytesIO()

    # with zipfile.ZipFile(documents_zip, mode='w', compression=zipfile.ZIP_DEFLATED) as zf:
    #     for key, value in attachments:
    #         zf.writestr(key, value.content)
    #
    # # Grab ZIP file from in-memory, make response with correct MIME-type
    # resp = HttpResponse(documents_zip.getvalue(), content_type="application/x-zip-compressed")
    # # ..and correct content-disposition
    # resp['Content-Disposition'] = 'attachment; filename=%s' % 'ujjwala_{}_legal_docs.zip'.format(obj.id)

    return attachments


def get_ujjwala_legal_documents_physical(iterable):
    """Merge pdfs in memory"""
    merger = PdfFileMerger()
    for pdf_fileobj in iterable:
        merger.append(pdf_fileobj)

    myio = io.BytesIO()
    merger.write(myio)
    merger.close()

    myio.seek(0)
    return myio


def process_family_uid_result(result):
    result = result.replace("BusinessError: ", "")
    if 'already exists' in result:
        m = COMPILED_REGEX_PATTERN_AADHAR_EXISTS.match(result)
        result_dict = m.groupdict()

        contact_name = result_dict.get('contact_name').split('(')
        result_dict['contact_name'] = contact_name[0]
        result_dict['consumer_id'] = contact_name[1].split(')')[0] if len(contact_name) > 1 else ''
        return result_dict
    return {
        'alert': result
    }
    # {distributor_name}    Get Attribute    xpath=//input[@aria-labelledby="EPIC_Distributor_Name_Label"]    value
    # {relationship_status}    Get Attribute    xpath=//input[@aria-labelledby="EPIC_Relationship_Status_Label"]    value
    # {contact_name}    Get Attribute    xpath=//input[@aria-labelledby="EPICContactName_Label"]    value
    # {consumer_id}    Get Attribute    xpath=//input[@aria-labelledby="EPICConsumerId_Label"]    value
    # {phone_number}    Get Attribute    xpath=//input[@aria-labelledby="EPIC_Phone_Number_Label"]    value
    # {contact_address}    Get Attribute    xpath=//textarea[@aria-labelledby="EPIC_Contact_Address_Label"]    value

    # return result_dict


def process_omc_dedupe_result(omc_dedup_result):
    # Get result set sorted by HPCL, BPCL then IOCL
    for key, value in sorted(omc_dedup_result.items(), key=lambda x: {'hpcl': 0, 'bpcl': 1, 'iocl': 2}.get(x[0])):
        if not "not available with" in value.lower():
            if key == 'bpcl':
                m = COMPILED_REGEX_PATTERN_BPC_1.match(value)
                if m:
                    result_dict = m.groupdict()
                    result_dict.update({
                        'distributor_name': "{} Id {}".format(result_dict['omc'], result_dict['distributor_name'])
                    })
                    return result_dict

                m = COMPILED_REGEX_PATTERN_BPC_2.match(value)
                if m:
                    result_dict = m.groupdict()
                    result_dict.update({
                        'distributor_name': "BPCL Distributor"
                    })
                    return result_dict
            else:
                m = COMPILED_REGEX_PATTERN_OTHERS.match(value)
                if m:
                    result_dict = m.groupdict()
                    return result_dict
                elif key == 'hpcl' and 'invalid response (p)' in value.lower():
                    return {'consumer_id': 'IdNotAvaliable', 'distributor_name': key, 'contact_address': ''}
    return {}


def is_application_ready_for_disbursement(application):
    if application.status == UjjwalaV2ApplicationStatus.NIC_CLEARED and \
            application.pre_inspection.status == PreInspectionStatusEnum.ACCEPTED:
        application.transition_ready_for_disbursement()
        application.save()


def send_whatsapp_contact_otp(request, contact_mobile):
    from otp.models import Otp

    ref_no = None

    while True:
        ref_no = __get_ref_no__()
        try:
            Otp.objects.get(reference_number=ref_no)
        except Otp.DoesNotExist:
            break

    otp = id_generator(4, chars=string.digits)
    valid_till = datetime.now() + timedelta(minutes=5)
    closed = False

    otp_obj = Otp.objects.create(
        reference_number=ref_no,
        mobile=contact_mobile,
        otp=otp,
        valid_till=valid_till,
        closed=closed,
        extra={
            "contact_mobile": contact_mobile
        }
    )

    body_text = {
        "countryCode": "+91",
        "phoneNumber": otp_obj.mobile,
        "type": "Template",
        "traits": {
            "name": otp_obj.mobile,
        },
        # "callbackData": "some_callback_data",
        "template": {
            "name": "ujjwala_application_whatsapp_otp_02082022",
            "languageCode": "hi",
            "headerValues": [
            ],
            "bodyValues": [
                request.build_absolute_uri(
                    reverse('ujjwala:ujjwala_application_display_otp', kwargs={'ref_no': otp_obj.reference_number})
                )
            ]
        }
    }

    data = track.client.post(
        api_key=settings.INTERAKT_API_KEY,
        path="/v1/public/message/",
        body=body_text
    ).json()

    if data.get('result', ''):
        CommunicationLog.objects.create(
            channel_subscriber=contact_mobile,
            event="ujjwala_application_whatsapp_contact_otp", channel="whatsapp",
            message_id=data.get('id')
        )
        return ref_no


def verify_whatsapp_contact_otp(reference_number, otp):
    from otp.models import Otp

    obj = Otp.objects.filter(reference_number=reference_number).first()
    if obj:
        if otp == obj.otp:
            signer = Signer()
            value = signer.sign(obj.mobile)
            return {
                "verified": True,
                "signed_value": value
            }
    return {
        "verified": False,
    }


# Send OTP SMS
def send_sms_contact_otp(contact_mobile):
    from otp.models import Otp

    ref_no = None

    while True:
        ref_no = __get_ref_no__()
        try:
            Otp.objects.get(reference_number=ref_no)
        except Otp.DoesNotExist:
            break

    otp = id_generator(4, chars=string.digits)
    valid_till = datetime.now() + timedelta(minutes=5)
    closed = False

    otp_obj = Otp.objects.create(
        reference_number=ref_no,
        mobile=contact_mobile,
        otp=otp,
        valid_till=valid_till,
        closed=closed,
        extra={
            "contact_mobile": contact_mobile
        }
    )

    context = {
        "for": "Phone Number Verification: {}".format(contact_mobile),
        "code": otp,
    }

    message = SMS_OTP_MESSAGE.format(**context)

    data = requests.post("https://4r198.api.infobip.com/sms/2/text/advanced", json={
        "messages": [
            {
                "from": "ARUNGS",
                "destinations": [
                    {
                        "to": "+91{}".format(contact_mobile)
                    }
                ],

                "text": message,
                "flash": False,

                "regional": {
                    "indiaDlt": {
                        "principalEntityId": "1101546710000030317",
                        "contentTemplateId": "1107161183026272363"
                    }
                },
                "notifyUrl": "https://dca.arungas.com/commlog/infobip/webhook/",
                "notifyContentType": "application/json",
                # "callbackData": "DLR callback data",
                # "validityPeriod": 720
            }
        ]
    }, headers={
        'Authorization': 'App 140a3abf6dd9134f5defb703a54dfcf0-e3df520b-f144-4282-a174-aa3765c7b438'
    })

    if data.get('result', ''):
        CommunicationLog.objects.create(
            channel_subscriber=contact_mobile,
            event="ujjwala_application_whatsapp_contact_otp", channel="whatsapp",
            message_id=data.get('id')
        )
        return ref_no


def verify_sms_contact_otp(reference_number, otp):
    from otp.models import Otp

    obj = Otp.objects.filter(reference_number=reference_number).first()
    if obj:
        if otp == obj.otp:
            signer = Signer()
            value = signer.sign(obj.mobile)
            return {
                "verified": True,
                "signed_value": value
            }
    return {
        "verified": False,
    }


def get_signed_share_data(contact_mobile, user_id):
    data = {
        'contact_mobile': contact_mobile,
        'user': user_id,
        'creation': datetime.now()
    }
    signer = Signer()
    data_signed = signer.sign(data)
    data_signed_base64 = base64.urlsafe_b64encode(data_signed.encode('ascii'))
    data = data_signed_base64.decode('ascii')
    return data


def send_ujjwala_application_whatsapp_link_v1(contact_mobile, user_id):
    data = get_signed_share_data(contact_mobile, user_id)
    url = reverse('ujjwala:ujjwala_application_link', kwargs={'data': data})
    url = url[1:]
    body_text = {
        "countryCode": "+91",
        "phoneNumber": contact_mobile,
        "type": "Template",
        "traits": {
            "name": contact_mobile,
        },
        # "callbackData": "some_callback_data",
        "template": {
            "name": "ujjwala_application_shared_link",
            "languageCode": "hi",
            "headerValues": [
            ],
            "bodyValues": [
                "https://dca.arungas.com/{}".format(url)
            ],
            "buttonValues": {
                "0": [
                    url
                ]
            }
        }
    }

    data = track.client.post(
        api_key=settings.INTERAKT_API_KEY,
        path="/v1/public/message/",
        body=body_text
    ).json()

    if data.get('result', ''):
        CommunicationLog.objects.create(
            channel_subscriber=contact_mobile,
            event="ujjwala_application_shared_link", channel="whatsapp",
            message_id=data.get('id')
        )
        return True
    return False


def send_ujjwala_application_whatsapp_link_v2(contact_mobile, user_id):
    data = get_signed_share_data(contact_mobile, user_id)
    url = reverse('ujjwala:ujjwala_application_link', kwargs={'data': data})
    url = url[1:]

    body_text = {
        "countryCode": "+91",
        "phoneNumber": contact_mobile,
        "type": "Template",
        "traits": {
            "name": contact_mobile,
        },
        "template": {
            "name": "ujjwala_application_shared_link_20082022",
             "languageCode": "hi",
            "headerValues": [
            ],
            "bodyValues": [],
            "buttonValues": {
                "0": [
                    url
                ]
            }
        }
    }

    data = track.client.post(
        api_key=settings.INTERAKT_API_KEY,
        path="/v1/public/message/",
        body=body_text
    ).json()

    if data.get('result', ''):
        CommunicationLog.objects.create(
            channel_subscriber=contact_mobile,
            event="ujjwala_application_shared_link", channel="whatsapp",
            message_id=data.get('id')
        )
        return True
    return False


def find_ujjwala_application_using_contact(contact_mobile):
    return True


def match_name(name):
    """
    Matches given name against pattern
    params:
        name
    """
    return re.match(VALID_CHARS_IN_NAME_PATTERN, name)


def get_valid_tokens(tokens, gender):
    valid_tokens = []
    for token in tokens:
        if not TokensExcluded.objects.filter(name=token.lower(), gender=gender).exists():
            valid_tokens.append(token)
    return valid_tokens


def get_gender(relation):
    if relation in (
            FamilyMemberRelationEnum.SELF,
            FamilyMemberRelationEnum.MOTHER,
            FamilyMemberRelationEnum.DAUGHTER
    ):
        return "Female"
    else:
        return "Male"


def is_valid_name(name, gender):
    """
    Validates given name
    """
    name = name.lower()
    if len(name) <= 3:
        return False, "Name Length"

    tokens = name.strip().split(" ")

    tokens = get_valid_tokens(tokens, gender)

    if len(tokens) > 2:
        return False, "Name Tokens Count Exceeds"

    for token in tokens:
        if len(token) <= 3:
            return False, "Token: {} Length less than equal to 3".format(token)

        if re.match(RELATION_VALIDATION_PATTERN, token):
            return False, "Wrong Name: {}".format(token)

        if not re.match(VALID_CHARS_IN_NAME_PATTERN, token):
            return False, "Wrong Character In Name: {}".format(token)

    return True, "No Error In Name"


def application_needs_to_be_audited(data):
    reason = []

    result, message = is_valid_name(data.get('name'), 'FEMALE')

    if not result:
        reason.append("Self Member {}".format(message))

    family_members = data.get('family_members')

    for fm in family_members:
        result, message = is_valid_name(fm['name'], get_gender(fm['relation']).upper())

        if not result:
            reason.append("{} Member {}".format(fm['relation'], message))

        if fm.get('ocr_processed') == 'no':
            reason.append(
                "Family Member: {} having UID {} ocr could not be processed.".format(
                    fm['name'], fm['uid_no']
                )
            )
    return '\n'.join(reason)


def application_needs_to_be_audited_by_id(obj):
    reason = []

    result, message = is_valid_name(obj.name, 'FEMALE')

    if not result:
        reason.append("Self Member {}".format(message))

    family_members = obj.family_members

    for fm in family_members.all():
        result, message = is_valid_name(fm.name, fm.get_gender().upper())

        if not result:
            reason.append("{} Member {}".format(fm.relation, message))

    return '\n'.join(reason)


def ujjwala_application_reject_reason_log(application_id):
    from django_fsm_log.models import StateLog

    description = StateLog.objects.filter(
        transition='application_rejected', object_id=application_id
    ).first()

    if description:
        return description.description


def is_pre_inspection_applicable(application_id):
    from ujjwala.models import UjjwalaV2Application

    application = UjjwalaV2Application.objects.filter(pk=application_id).first()

    if application.status == UjjwalaV2ApplicationStatus.APPLICATION_REJECTED:
        return False

    if application.status == UjjwalaV2ApplicationStatus.OMC_REJECTED:
        return False

    if application.robo_sdms_dedup == RoboSdmsDedeupStatusEnum.PROCESSED_AND_UNIQUE:
        return True

    return False


def time_in_range(start, end, x):
    """Return true if x is in the range [start, end]"""
    if start <= end:
        return start <= x <= end
    else:
        return start <= x or x <= end


@job
def send_ujjwala_welcome_whatsapp_link(contact_mobile):
    body_text = {
        "countryCode": "+91",
        "phoneNumber": contact_mobile,
        "type": "Template",
        "traits": {
            "name": contact_mobile,
        },
        "template": {
            "name": "ujjwala_welcome_link_check_self_eligibility_v3",
            "languageCode": "hi",
        }
    }

    data = track.client.post(
        api_key=settings.INTERAKT_API_KEY,
        path="/v1/public/message/",
        body=body_text
    ).json()

    if data.get('result', ''):
        CommunicationLog.objects.create(
            channel_subscriber=contact_mobile,
            event="ujjwala_application_welcome_link", channel="whatsapp",
            message_id=data.get('id')
        )
        return True
    return False


def fsm_custom_audit_points_description(func=None):
    @wraps(func)
    def wrapped(instance, *args, **kwargs):
        kwargs['description'] = instance.audit_points
        return func(instance, *args, **kwargs)
    return wrapped


def download_audit_document(application, documents_type):
    attachments = []
    documents_list = []
    form_template = loader.get_template("ujjwala/extra/audit_document_template.html")
    for document_type in documents_type:
        if document_type == PrintDocumentsTypeEnum.FORM_ABC:
            documents_list.append({
                'img_url': application.connection_disbursement.documents.filter(
                    type="LEGAL_DOC_PRE_INSPECTION"
                ).first().link,
                'alt_text': "Form A",
                'file_name': 'form_a'
            })

            documents_list.append({
                'img_url': application.connection_disbursement.documents.filter(
                    type="LEGAL_DOC_FAMILY_OCCUPANCY"
                ).first().link,
                'alt_text': "Form B",
                'file_name': 'form_b'
            })

            documents_list.append({
                'img_url': application.connection_disbursement.documents.filter(
                    type="LEGAL_DOC_ANNEXURE_14_POINTS"
                ).first().link,
                'alt_text': "Form C",
                'file_name': 'form_c'
            })

        if document_type == PrintDocumentsTypeEnum.AADHAR:
            for fm in application.family_members.all():
                documents_list.append({
                    'info': "{} {}".format(fm.name, fm.relation),
                    'img_url': fm.uid_front_link,
                    'alt_text': "Uid Front",
                    'file_name': 'uid_front_{}'.format(fm.uid_no)
                })

        if document_type == PrintDocumentsTypeEnum.BANK_DETAILS:
            documents_list.append({
                'info': "{} {}".format(application.bank_account_number, application.ifsc_code),
                'img_url': application.documents.filter(
                    type=UjjwalaApplicationDocumentsEnum.BANK_DETAIL
                ).first().link,
                'alt_text': "Bank Details",
                'file_name': 'bank_{}'.format(application.bank_account_number)
            })

    for document in documents_list:
        form_template_html = form_template.render(document)
        form_pdf = requests.post(
            settings.HTML_TO_PDF_SERVER_URL,
            json={
                "content": form_template_html,
                "options": PDF_COMPRESSION_OPTIONS
            }
        )
        attachments.append(('{}.pdf'.format(document.get('file_name')), form_pdf))

    merger = PdfFileMerger()
    temp_files = []
    for key, value in attachments:
        file = io.BytesIO()
        file.write(value.content)
        temp_files.append(file)
        merger.append(file, import_bookmarks=False)

    myio = io.BytesIO()
    merger.write(myio)
    merger.close()

    [f.close() for f in temp_files]

    myio.seek(0)
    return {
        'filename': 'ujjwala_id_{}_audit_docs.pdf'.format(application.id),
        'content': myio.getvalue()
    }
    # resp = HttpResponse(myio.getvalue(), content_type="application/pdf")
    # resp['Content-Disposition'] = 'attachment; filename=%s' % 'ujjwala_id_{}_audit_docs.pdf'.format(application.id)
    # return resp


def download_audit_documents_for_ids(application_ids, documents_type):
    from ujjwala.models import UjjwalaV2Application

    application_id_list = application_ids.split(",")
    application_list = UjjwalaV2Application.objects.filter(id__in=application_id_list)

    documents_to_zip = []

    for application in application_list:
        document = download_audit_document(application, documents_type)
        documents_to_zip.append(document)

    documents_zip = io.BytesIO()

    with zipfile.ZipFile(documents_zip, mode='w', compression=zipfile.ZIP_DEFLATED) as zf:
        for document in documents_to_zip:
            zf.writestr(document.get('filename'), data=document.get('content'))

    # Grab ZIP file from in-memory, make response with correct MIME-type
    resp = HttpResponse(documents_zip.getvalue(), content_type="application/x-zip-compressed")
    resp['Content-Disposition'] = 'attachment; filename=%s' % 'ujjwala_audit_docs.zip'
    return resp
