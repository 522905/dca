import base64
import io
import random
import re
import string
import zipfile
from datetime import datetime
from datetime import timedelta
from functools import wraps
from time import timezone

import django_rq
import magic
import requests
import track
from PyPDF2 import PdfFileMerger
from django.conf import settings
from django.contrib.contenttypes.models import ContentType
from django.core.signing import Signer
from django.db.models import Q
from django.http import HttpResponse
from django.template import loader
from django.urls import reverse
from django.utils.timezone import now
from django_fsm_log.models import StateLog
from django_rq import job

from communication_log.models import CommunicationLog
from reference_data.models import TokensExcluded
from ujjwala.communication_functions import send_whatsapp_message, send_sms
from ujjwala.enums import UjjwalaApplicationDocumentsEnum, FamilyMemberRelationEnum, ResidentialStatusEnum, \
	MaritalStatusEnum, UjjwalaV2ApplicationStatus, PreInspectionStatusEnum, RoboSdmsDedeupStatusEnum, \
	PrintDocumentsTypeEnum, DisbursementDriveStatusEnum
from utils.global_functions import upload_file_to_minio_bucket, sign_data_base64
from utils.qrcode import generate_base64_qr_code

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
RELATION_VALIDATION_PATTERN = r'.(fathe|moth|husba|government|india).'
GOV_OF_INDIA_FUZZY_REGEX = r'.*g.*of*.i.*'


def valid_file_uploaded(url):
	res = requests.head(url, headers={"Tus-Resumable": "1.0.0"})
	header_info = res.headers
	if 'Upload-Length' not in header_info: return True, 0
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

	if 'Upload-Length' not in header_info:
		return f'{settings.THUMBOR_LOCAL_URL}/unsafe/fit-in/1920x1080/filters:format(jpeg)/{url}'

	if int(header_info.get('Upload-Length', 0)) <= 499000:
		file_type = header_info['Upload-Metadata'].split(',')[0].split(' ')[1]
		if 'webp' not in base64.b64decode(file_type).decode():
			return url

	return f'{settings.THUMBOR_LOCAL_URL}/unsafe/fit-in/1920x1080/filters:format(jpeg)/{url}'


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
			'date': datetime.now().strftime("%d-%m-%Y"),
			'qr_code': generate_base64_qr_code("{},{}".format(obj.parent.parent_id, "FORM_C")),
			'obj': obj.parent.parent
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
			'customer_signature_file': customer_signature_file,
			'qr_code': generate_base64_qr_code("{},{}".format(obj.parent.parent_id, "FORM_B"))
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
		'obj': obj,
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
		'obj': obj,
		'app_id': obj.id,
		'name': obj.name,
		'uid': list(self_doc.uid_no),
		'age': '{}'.format(str(datetime.now().year - self_doc.dob.year)),
		'relation_name': relationship_name,
		# 'customer_signature_file': customer_signature_file,
		'customer_signature_file': '',
		'date': datetime.now().strftime("%d-%m-%Y"),
		'qr_code': generate_base64_qr_code("{},{}".format(obj.id, "LEGAL_DOC_ANNEXURE_14_POINTS"))
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
		'customer_signature_file': '',
		'qr_code': generate_base64_qr_code("{},{}".format(obj.id, "LEGAL_DOC_FAMILY_OCCUPANCY"))
	})

	occupancy_form_pdf = requests.post(
		settings.HTML_TO_PDF_SERVER_URL,
		json={
			"content": occupancy_form_html,
			"options": PDF_COMPRESSION_OPTIONS
		}
	)

	attachments.append(('{}.pdf'.format(occupancy_file_name), occupancy_form_pdf))

	mech = pre_inspection.mechanic or pre_inspection.referral_user or pre_inspection.parent.filled_by
	ujjwala_pre_inspection_html_template = loader.get_template("ujjwala/forms/pre_inspection_form.html")
	ujjwala_pre_inspection_html = ujjwala_pre_inspection_html_template.render({
		'obj': pre_inspection,
		'qr_code': generate_base64_qr_code("{},{}".format(obj.id, "LEGAL_DOC_PRE_INSPECTION")),
		'mech_name': f'{mech.first_name}' if mech else 'Abdul Sammad'
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


def re_create_legal_docs(application):
	from ujjwala.jobs import upload_recreated_physical_document_url

	physical_legal_document = download_ujjwala_physical_legal_docs(application)
	upload_url = upload_file_to_minio_bucket(
		physical_legal_document,
		"ujjwaladocuments",
		"ujjwala_{}_physical_legal_document".format(application.id)
	)

	django_rq.enqueue(upload_recreated_physical_document_url, args=(application.pre_inspection.id, upload_url,))
	return physical_legal_document


def re_create_legal_docs_pdf(application):
	document = re_create_legal_docs(application)
	resp = HttpResponse(document, content_type="application/pdf")
	resp['Content-Disposition'] = 'attachment; filename=%s' % 'ujjwala_physical_{}_legal_docs.pdf'.format(
		application.id)
	return resp


def download_installation_form(obj):

	self_doc = obj.family_members.filter(relation=FamilyMemberRelationEnum.SELF).first()

	installation_form_html_template = loader.get_template("ujjwala/forms/installation_form.html")
	installation_html = installation_form_html_template.render({
		'app_id': obj.id,
		'name': obj.name,
		'uid_no': self_doc.uid_no,
		'qr_code': generate_base64_qr_code("{},{}".format(obj.id, "INSTALLATION_DOCUMENT")),
		'obj': obj
	})

	installation_form_pdf = requests.post(
		settings.HTML_TO_PDF_SERVER_URL,
		json={
			"content": installation_html,
			"options": PDF_COMPRESSION_OPTIONS
		}
	)

	# merger = PdfFileMerger()
	# temp_files = []
	# for key, value in attachments:
	#     file = io.BytesIO()
	#     file.write(value.content)
	#     temp_files.append(file)
	#     merger.append(file, import_bookmarks=False)
	#
	# myio = io.BytesIO()
	# merger.write(myio)
	# merger.close()
	#
	# [f.close() for f in temp_files]
	#
	# myio.seek(0)

	resp = HttpResponse(installation_form_pdf.content, content_type="application/pdf")
	resp['Content-Disposition'] = 'attachment; filename=%s' % 'ujjwala_installation_{}_doc.pdf'.format(obj.id)
	return resp


def download_installation_form_with_signature(obj):

	customer_signature_file = obj.documents.filter(
		type=UjjwalaApplicationDocumentsEnum.CUSTOMER_SIGNATURE
	).first()

	if customer_signature_file:
		customer_signature_file = customer_signature_file.link
	else:
		customer_signature_file = ''

	self_doc = obj.family_members.filter(relation=FamilyMemberRelationEnum.SELF).first()

	installation_form_html_template = loader.get_template("ujjwala/forms/signed_installation_form.html")
	installation_html = installation_form_html_template.render({
		'app_id': obj.id,
		'name': obj.name,
		'uid_no': self_doc.uid_no,
		'qr_code': generate_base64_qr_code("{},{}".format(obj.id, "INSTALLATION_DOCUMENT")),
		'customer_signature_file': customer_signature_file
	})

	installation_form_pdf = requests.post(
		settings.HTML_TO_PDF_SERVER_URL,
		json={
			"content": installation_html,
			"options": PDF_COMPRESSION_OPTIONS
		}
	)
	return installation_form_pdf

	# resp = HttpResponse(installation_form_pdf.content, content_type="application/pdf")
	# resp['Content-Disposition'] = 'attachment; filename=%s' % 'ujjwala_signed_installation_{}_doc.pdf'.format(obj.id)
	# return resp


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
			'obj': obj,
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


def send_whatsapp_contact_otp(request, contact_mobile):
	from otp.models import Otp

	ref_no = None

	while True:
		ref_no = __get_ref_no__()
		try:
			Otp.objects.get(reference_number=ref_no)
		except Otp.DoesNotExist:
			break

	otp_obj = Otp.objects.filter(mobile=contact_mobile,
								 transition='{}-New-Form'.format(contact_mobile)).order_by('-created_on').first()

	if otp_obj and now() < otp_obj.valid_till:
		otp = otp_obj.otp
		ref_no = otp_obj.reference_number
	else:
		otp = id_generator(4, chars=string.digits)
		valid_till = datetime.now() + timedelta(minutes=30)
		closed = False

		otp_obj = Otp.objects.create(
			reference_number=ref_no,
			mobile=contact_mobile,
			otp=otp,
			valid_till=valid_till,
			closed=closed,
			extra={
				"contact_mobile": contact_mobile
			},
			transition='{}-New-Form'.format(contact_mobile)
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


def send_ujjwala_application_pos_list(contact_mobile, template_name="ujjwala_form_fill_areas"):
	"""
	Function Working Changed Due To Closure of Public Form Filling
	"""
	# data = get_signed_share_data(contact_mobile, user_id)
	# url = reverse('ujjwala:ujjwala_application_link', kwargs={'data': data})
	# url = url[1:]

	body_text = {
		"countryCode": "+91",
		"phoneNumber": contact_mobile,
		"type": "Template",
		"traits": {
			"name": contact_mobile,
		},
		"template": {
			# "name": "ujjwala_application_shared_link_20082022",
			"name": template_name,
			#"name": "votercard3122022",
			"languageCode": "hi",
			"headerValues": [
			],
			"bodyValues": [],
			# "buttonValues": {
			# 	"0": [
			# 		"https://dca.arungas.com/"
			# 	]
			# }
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
			event="ujjwala_pos_list_link", channel="whatsapp",
			message_id=data.get('id')
		)
		return True
	return False


def send_pos_list_for_ekyc(contact_mobile):
	return send_ujjwala_application_pos_list(contact_mobile, template_name="pos_list_ekyc_static_url")


def send_ujjwala_application_whatsapp_link_v2(contact_mobile, user_id, share_link=False):
	"""
	Function Working Changed Due To Closure of Public Form Filling
	"""
	if not share_link:
		return send_ujjwala_application_pos_list(contact_mobile, template_name="ujjwala_form_fill_areas")

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


def send_upload_uid_for_ekyc_whatsapp_link(contact_mobile, pk):
	url = reverse('ujjwala:pre_inspection_form_view', kwargs={'pk': pk})
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
			event="ujjwala_application_upload_uid_for_ekyc", channel="whatsapp",
			message_id=data.get('id')
		)
		return True
	return False


def send_offer_whatsapp_link(contact_mobile):

	body_text = {
		"countryCode": "+91",
		"phoneNumber": contact_mobile,
		"type": "Template",
		"traits": {
			"name": contact_mobile,
		},
		"template": {
			"name": "offer_template",
			 "languageCode": "en",
			"headerValues": [
			],
			"bodyValues": [
				"https://www.arungas.com/public/offer/offer.html",
			],
			"buttonValues": {
				"0": [
					"https://www.arungas.com/public/offer/offer.html"
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
			event="01615201005_offer", channel="whatsapp",
			message_id=data.get('id')
		)
		return True
	return False


def send_ujjwala_self_pre_inspection_share_link(contact_mobile, user_id, username, application):
	data = sign_data_base64({
		'user_id': user_id,
		'username': username,
		'creation': datetime.now(),
		'pre_inspection_id': application.pre_inspection.id
	})

	url = reverse('ujjwala:shared_self_pre_inspection_link_view', kwargs={'data': data})
	url = url[1:]

	req = requests.get(
		"https://tinyurl.com/api-create.php",
		# params={'url': "https://dca.arungas.com/{}".format(url)},
		params={'url': "http://0.0.0.0:60610/{}".format(url)},
		# params={'url': "https://dca.arungas.com/{}".format(url)},
	)

	short_url = req.text

	body_text = {
		"countryCode": "+91",
		"phoneNumber": contact_mobile,
		"type": "Template",
		"traits": {
			"name": application.name,
		},
		# "callbackData": "some_callback_data",
		"template": {
			"name": "ujjwala_self_pre_inspection_share_link_14102022",
			"languageCode": "hi",
			"headerValues": [
				"https://arungas.com/public/ujjwala_stickers.pdf"
			],
			"bodyValues": [
				application.name,
				"https://arungas.com/public/self_pre_inspection_help_file.pdf"
			],
			"buttonValues": {
				"0": [
					url
				]
			}
		}
	}

	ujjwala_pre_inspection_content_type = ContentType.objects.get(
		app_label='ujjwala', model='preinspection'
	)
	data = track.client.post(
		api_key=settings.INTERAKT_API_KEY,
		path="/v1/public/message/",
		body=body_text
	).json()

	if data.get('result', ''):
		CommunicationLog.objects.create(
			content_type=ujjwala_pre_inspection_content_type,
			object_id=application.pre_inspection.id,
			channel_subscriber=contact_mobile,
			event="pre_inspection_type_self_share", channel="whatsapp",
			message_id=data.get('id')
		)
		return True
	return False


def send_ujjwala_share_on_social_media_link(contact_mobile, application):
	url = reverse('ujjwala:share_on_social_media', kwargs={'pk': application.connection_disbursement.id})
	url = url[1:]
	#url = request.build_absolute_uri(url)
	req = requests.get(
		"https://tinyurl.com/api-create.php",
		params={'url': "https://dca.arungas.com/{}".format(url)},
		# params={'url': url},
		# params={'url': "https://dca.arungas.com/{}".format(url)},
	)

	short_url = req.text

	body_text = {
		"countryCode": "+91",
		"phoneNumber": contact_mobile,
		"type": "Template",
		"traits": {
			"name": application.name,
		},
		# "callbackData": "some_callback_data",
		"template": {
			"name": "ujjwala_share_on_social_media",
			"languageCode": "hi",
			"headerValues": [],
			"bodyValues": [
				short_url
			],
			"buttonValues": {
				"0": [
					url
				]
			}
		}
	}

	ujjwala_connection_disbursement_content_type = ContentType.objects.get(
		app_label='ujjwala', model='connectiondisbursement'
	)
	data = track.client.post(
		api_key=settings.INTERAKT_API_KEY,
		path="/v1/public/message/",
		body=body_text
	).json()

	if data.get('result', ''):
		CommunicationLog.objects.create(
			content_type=ujjwala_connection_disbursement_content_type,
			object_id=application.connection_disbursement.id,
			channel_subscriber=contact_mobile,
			event="walk_in_social_media_share_link", channel="whatsapp",
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

	if re.match(GOV_OF_INDIA_FUZZY_REGEX, name, flags=re.IGNORECASE):
		return False, "Name Might Be Gov Of India"

	return True, "No Error In Name"


def application_needs_to_be_audited(data):
	from difflib import SequenceMatcher

	reason = []

	result, message = is_valid_name(data.get('name'), 'FEMALE')

	if not result:
		reason.append("Self Member {}".format(message))

	family_members = data.get('family_members')

	for fm in family_members:
		seq_match = SequenceMatcher(None, data.get('contact_mobile'), fm['uid_no'])
		match = seq_match.find_longest_match(0, len(data.get('contact_mobile')), 0, len(fm['uid_no']))
		if match.size >= 6:
			matched_str = data.get('contact_mobile')[match.a: match.a + match.size]
			reason.append(
				"Relation {} Contact Mobile Number Digits {} Found In UID {}".format(fm['relation'],
				                                                                     matched_str,
				                                                                     fm['uid_no'])
			)

		seq_match = SequenceMatcher(None, data.get('uid_linked_mobile'), fm['uid_no'])
		match = seq_match.find_longest_match(0, len(data.get('uid_linked_mobile')), 0, len(fm['uid_no']))
		if match.size >= 6:
			matched_str = data.get('uid_linked_mobile')[match.a: match.a + match.size]
			reason.append(
				"Relation {} UID Linked Mobile Number Digits {} Found In UID {}".format(fm['relation'],
				                                                                     matched_str,
				                                                                     fm['uid_no'])
			)

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
	from difflib import SequenceMatcher

	reason = []

	# result, message = is_valid_name(obj.name, 'FEMALE')

	# if not result:
	#    reason.append("Self Member {}".format(message))

	family_members = obj.family_members

	for fm in family_members.all():
		seq_match = SequenceMatcher(None, obj.contact_mobile, fm.uid_no)
		match = seq_match.find_longest_match(0, len(obj.contact_mobile), 0, len(fm.uid_no))
		if match.size >= 6:
			matched_str = obj.contact_mobile[match.a: match.a + match.size]
			reason.append(
				"Relation {} Contact Mobile Number Digits {} Found In UID {}".format(fm.relation,
				                                                                     matched_str,
				                                                                     fm.uid_no)
			)

		seq_match = SequenceMatcher(None, obj.uid_linked_mobile, fm.uid_no)
		match = seq_match.find_longest_match(0, len(obj.uid_linked_mobile), 0, len(fm.uid_no))
		if match.size >= 6:
			matched_str = obj.uid_linked_mobile[match.a: match.a + match.size]
			reason.append(
				"Relation {} UID Linked Mobile Number Digits {} Found In UID {}".format(fm.relation,
				                                                                        matched_str,
				                                                                        fm.uid_no)
			)
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


def ujjwala_application_state_logs(application_id, content_type_id):
	from django_fsm_log.models import StateLog

	return StateLog.objects.filter(
		object_id=application_id, content_type_id=content_type_id
	).order_by('-id')


def is_pre_inspection_applicable(application_id):
	from ujjwala.models import UjjwalaV2Application

	application = UjjwalaV2Application.objects.filter(pk=application_id).first()

	if application.status == UjjwalaV2ApplicationStatus.APPLICATION_REJECTED:
		return False

	if application.status == UjjwalaV2ApplicationStatus.OMC_REJECTED:
		return False

	if application.robo_sdms_dedup in (
		RoboSdmsDedeupStatusEnum.PROCESSED_AND_UNIQUE, RoboSdmsDedeupStatusEnum.NOT_PROCESSED):
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
				documents_list.append({
					'info': "{} {}".format(fm.name, fm.relation),
					'img_url': fm.uid_back_link,
					'alt_text': "Uid Back",
					'file_name': 'uid_back_{}'.format(fm.uid_no)
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


def is_member_of_second_cylinder_delivery(user):
	return user.has_perm('ujjwala.second_cylinder_delivery')


def is_member_of_reviewer_group(user):
	return user.has_perm('ujjwala.is_part_of_reviewer_group')


def is_front_end_staff(user):
	return user.has_perm('ujjwala.is_front_end_staff')


def can_resolve_service_request(user):
	return user.has_perm('service_request.can_resolve_service_request')


def is_member_of_disbursement_drive(user):
	from ujjwala.models import DisbursementDrive

	disbursement_drive = DisbursementDrive.objects.filter(
		status=DisbursementDriveStatusEnum.ACTIVE, team_members=user
	).first()

	if disbursement_drive:
		return True
	else:
		return False


def get_current_user_disbursement_drive(user):
	from ujjwala.models import DisbursementDrive

	disbursement_drive = DisbursementDrive.objects.filter(
		team_members=user, status=DisbursementDriveStatusEnum.ACTIVE
	).first()

	return disbursement_drive


def send_otp_using_channel(template, mobile, otp_generated_for, application_id, channel='whatsapp'):
	from otp.models import Otp

	content_type, pk, transition = otp_generated_for.split(":")
	content_type = ContentType.objects.get(app_label='ujjwala', model=content_type)

	otp_obj = Otp.objects.filter(
		mobile=mobile, content_type=content_type, object_id=application_id, transition=transition
	).first()

#    if otp_obj and datetime.now().astimezone(pytz.timezone("Asia/Kolkata")) < otp_obj.valid_till.astimezone(pytz.timezone("Asia/Kolkata")):
	if otp_obj and now() < otp_obj.valid_till:
		otp = otp_obj.otp
	else:
		ref_no = None
		while True:
			ref_no = __get_ref_no__()
			try:
				Otp.objects.get(reference_number=ref_no)
			except Otp.DoesNotExist:
				break
		otp = id_generator(4, chars=string.digits)
		valid_till = datetime.now() + timedelta(minutes=180)
		closed = False

		otp_obj = Otp.objects.create(
			reference_number=ref_no,
			mobile=mobile,
			otp=otp,
			valid_till=valid_till,
			closed=closed,
			content_type=content_type,
			object_id=application_id,
			transition=transition,
			extra={
				"application_id": application_id
			}
		)

	message_id = None

	if channel == "whatsapp":
		result, response = send_whatsapp_message(
			otp_obj.mobile, template, [otp]
		)
		if result:
			message_id = response.get('id')
	elif channel == "sms":
		context = {
			"otp_for": 'otp_generated_for',
			"otp": otp,
		}

		message = settings.GENERIC_SMS_OTP_TEMPLATE.format(**context)
		result, response = send_sms(otp_obj.mobile, message, settings.GENERIC_SMS_OTP_TEMPLATE_ID)
		if result:
			messages = response['messages']
			message_id = messages[0].get('messageId')

	from ujjwala.models import UjjwalaV2Application

	CommunicationLog.objects.create(
		content_type=ContentType.objects.get_for_model(UjjwalaV2Application),
		object_id=application_id,
		event=otp_generated_for, channel=channel,
		channel_subscriber=mobile,
		message_id=message_id
	)
	return otp_obj


def omc_nic_status_update(application, request):
	if not request.data.get('omc_status'):
		return HttpResponse('No Data, Skip Update')

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
	return application


def num_there(s):
	return any(i.isdigit() for i in s)


def fetch_payment_profile_variables(application_id, force_main_branch=False):
	from ujjwala.models import UjjwalaV2Application
	from reference_data.models import IFSCodeList, RTGSList

	application = UjjwalaV2Application.objects.get(pk=application_id)

	old_ifscode = application.ifsc_code.strip().replace(" ", "")

	bank_code = old_ifscode[:4]

	new_ifscode = None

	if num_there(bank_code):
		return {
			"status": False,
			"reason": f"Invalid IFSCode: {old_ifscode}. Manually Correct."
		}

	if not force_main_branch:
		res = requests.get(f"https://ifsc.razorpay.com/{old_ifscode}")
		if res.status_code == 200:
			new_ifscode = old_ifscode

	if not new_ifscode:
		ifscodelist_obj: IFSCodeList = IFSCodeList.objects.filter(old_ifscode=old_ifscode).first()
		if ifscodelist_obj:
			new_ifscode = ifscodelist_obj.new_ifscode
		else:
			if old_ifscode[:4] in ['SBIN', 'UBIN', 'IDIB', 'PUNB', 'CNRB', 'BARB']:
				rtgs_ifscode = RTGSList.objects.filter(ifscode__istartswith=old_ifscode[:4]).first()
			else:
				merged_bank_code = IFSCodeList.objects.filter(
					old_ifscode__istartswith=old_ifscode[:4]
				).first()

				rtgs_ifscode = RTGSList.objects.filter(
					ifscode__istartswith=merged_bank_code.new_ifscode[:4] if merged_bank_code else old_ifscode[:4]
				).first()
			new_ifscode = rtgs_ifscode.ifscode if rtgs_ifscode else None

	if not new_ifscode:
		return {
			"status": False,
			"reason": f"No Matching IFSCode Found Against Existing IFSCode: {old_ifscode}"
		}

	return {
		"status": True,
		"bank_account": application.bank_account_number,
		"ifscode": new_ifscode,
		"first_name": application.name
	}


def get_last_valid_status_for_application(application_id):
	from ujjwala.models import UjjwalaV2Application

	application = UjjwalaV2Application.objects.get(pk=application_id)

	if application.status == application.last_execution_state or not application.last_execution_state:
		state_log = StateLog.objects.filter(object_id=application_id,
		                                    content_type=ContentType.objects.get(app_label='ujjwala',
		                                                                         model='ujjwalav2application')).exclude(
			source_state='AUDIT_APPLICATION').exclude(source_state='ON_HOLD').order_by('-id').first()
		return state_log.source_state
	else:
		return application.last_execution_state


def get_review_to_target_status(application_id):
	from ujjwala.models import UjjwalaV2Application

	application = UjjwalaV2Application.objects.get(pk=application_id)

	if application.last_execution_state in ['ADDRESS_CHANGE', 'REVIEW_ADDRESS']:
	# if application.status == application.last_execution_state or not application.last_execution_state:
		state_log = StateLog.objects.filter(object_id=application_id,
		                                    content_type=ContentType.objects.get(app_label='ujjwala',
		                                                                         model='ujjwalav2application')).exclude(
			source_state='REVIEW_ADDRESS').exclude(source_state='ADDRESS_CHANGE').order_by('-id').first()
		return state_log.source_state
	else:
		return application.last_execution_state

	# if not application.last_execution_state:
	# 	state_log = StateLog.objects.filter(
	# 		object_id=application_id,
	# 	    content_type=ContentType.objects.get(app_label='ujjwala', model='ujjwalav2application')
	# 	).exclude(state=application.status).order_by(
	# 		'-id').first()
	# 	return state_log.source_state
	#
	# if application.status == application.last_execution_state:
	# 	state_log = StateLog.objects.filter(
	# 		object_id=application_id,
	# 	    content_type=ContentType.objects.get(app_label='ujjwala', model='ujjwalav2application')
	# 	).exclude(state__in=[application.status, 'ON_HOLD']).order_by(
	# 		'-id').first()
	# 	return state_log.state
	# else:
	# 	return application.last_execution_state


def get_data_for_new_relation(application_id):
	from ujjwala.models import UjjwalaV2Application

	record = UjjwalaV2Application.objects.get(pk=application_id)

	try:
		address = record.get_address_for_sdms_upload()
	except:
		raise Exception("Address Error")

	pi_status = 'NA'
	try:
		pi_status = record.pre_inspection.status
	except:
		pass

	self_fm = record.family_members.get(relation=FamilyMemberRelationEnum.SELF)
	self_name_split = record.name.split(" ")
	data = {
		"id": record.id,
		"First Name": self_name_split[0].title(),
		"Last Name": ' '.join(self_name_split[1:]).title() if len(self_name_split) > 1 else '.',
		"Salutation": get_salutation(self_fm),
		"Gender": "Female",
		"DOB": self_fm.dob.strftime('%Y-%m-%d'),
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
			"address": address['addr_str'].strip().replace('\\', '/'),
			"landmark": f'DcaId-{record.id} ' + record.address_json.get('landmark', 'NA'),
			"pincode": address['pincode']
		},
		"bank": {
			"account": record.bank_account_number,
			"ifsc": record.ifsc_code
		},
		"extras": {
			"pi_status": pi_status
		}
	}
	return data
