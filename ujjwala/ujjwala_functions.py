import io
import zipfile
from datetime import datetime
from functools import wraps

import magic
import requests
from django.conf import settings
from django.db.models import Q
from django.http import HttpResponse, HttpResponseRedirect
from django.template import loader

from ujjwala.enums import UjjwalaApplicationDocumentsEnum, FamilyMemberRelationEnum, ResidentialStatusEnum, \
    MaritalStatusEnum


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
                "options": {"pageSize": "A4"}
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
                "options": {"pageSize": "A4"}
            }
        )
        attachments.append(('annexure_14_points.pdf', ujjwala_declaration_pdf))

        if obj.residential_status == ResidentialStatusEnum.LIVING_ALONE:
            occupancy_template_html = "ujjwala/forms/single_occupancy_form.html"
            occupancy_file_name = "single_occupancy"
        else:
            occupancy_template_html = "ujjwala/forms/family_occupancy_form.html"
            occupancy_file_name = "family_occupancy"

        if obj.version == 'V3':
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
                "options": {"pageSize": "A4"}
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
