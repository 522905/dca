import base64
import io
import math
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
from django.contrib.auth.models import User
from django.contrib.contenttypes.models import ContentType
from django.core.signing import Signer
from django.db.models import Q
from django.http import HttpResponse
from django.template import loader
from django.urls import reverse
from django.utils.timezone import now
from django_currentuser.middleware import get_current_user
from django_fsm_log.models import StateLog
from django_rq import job
from shapely import Point, Polygon

from communication_log.models import CommunicationLog
from reference_data.models import TokensExcluded
from ujjwala.communication_functions import send_whatsapp_message, send_sms
from ujjwala.enums import UjjwalaApplicationDocumentsEnum, FamilyMemberRelationEnum, ResidentialStatusEnum, \
	MaritalStatusEnum, UjjwalaV2ApplicationStatus, PreInspectionStatusEnum, RoboSdmsDedeupStatusEnum, \
	PrintDocumentsTypeEnum, DisbursementDriveStatusEnum, ChangeCylinderTypeRequestStatusEnum
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

		if uid_front_doc_file_extension not in ('jpg', 'jpeg'):
			uid_front_doc_file_extension = 'jpg'

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
	).filter(parent_id=obj.id).first()

	if not pre_inspection:
		raise Exception("No Pre-Inspection Submitted.")

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


def download_change_cylinder_type_form(obj):
	installation_form_html_template = loader.get_template("ujjwala/forms/change_cylinder_form.html")
	user = get_current_user()
	organization = user.organizations_organization.first()
	installation_html = installation_form_html_template.render({
		'obj': obj,
		"user": user,
		"organization": organization,
		"service_location": organization.service_locations.first() if organization else None,
		"request_obj": obj.changecylindertyperequest_set.first()
	})

	change_cylinder_request_form = requests.post(
		settings.HTML_TO_PDF_SERVER_URL,
		json={
			"content": installation_html,
			"options": PDF_COMPRESSION_OPTIONS
		}
	)
	return change_cylinder_request_form.content


def upload_form_e_document_and_whatsapp(application_id, phone_number):
	from ujjwala.models import UjjwalaV2Application

	obj = UjjwalaV2Application.objects.filter(id=application_id).first()
	if not obj:
		return HttpResponse("Application Id {} does not exist".format(application_id))

	document = download_change_cylinder_type_form(obj)
	resp = HttpResponse(document, content_type="application/pdf")
	resp['Content-Disposition'] = 'attachment; filename=%s' % 'change_cylinder_form_{}.pdf'.format(
		obj.id)

	upload_url = upload_file_to_minio_bucket(
		resp,
		"ujjwaladocuments",
		"ujjwala_{}_form_e".format(obj.id)
	)
	obj.connection_disbursement.documents.create(type=UjjwalaApplicationDocumentsEnum.FORM_E, link=upload_url)

	# Send Whatsapp Message With Created Form
	# phone_number = data.get('new_phone_number') if data.get('change_phone_number') else obj.contact_mobile
	obj.event_send_form_e(phone_number)
	return True


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


def can_review_disbursement_form_abc_permission(user):
	return user.has_perm('ujjwala.can_review_disbursement_form_abc')


def can_initiate_change_cylinder_type_request(user):
	return user.has_perm('ujjwala.can_initiate_change_cylinder_type_request')


def can_process_change_cylinder_request(user):
	return user.has_perm('ujjwala.can_process_change_cylinder_request')


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


def get_area_tag(preinspection_id):
	from ujjwala.models import PreInspection

	service_areas = [
		{
			"type": "Feature",
			"properties": {
				"area_name": "bhamian_mundian"
			},
			"geometry": {
				"coordinates": [
					[
						[
							75.87724599918107,
							30.916478899997756
						],
						[
							75.87989940498397,
							30.91050723411678
						],
						[
							75.89797544846398,
							30.903460905122333
						],
						[
							75.91053684097758,
							30.900684657359655
						],
						[
							75.92883880381962,
							30.89209714840598
						],
						[
							75.93197074546774,
							30.890039777417428
						],
						[
							75.94633374456875,
							30.883365348322823
						],
						[
							75.95052228287273,
							30.88209055305687
						],
						[
							75.95619406840166,
							30.899204371162085
						],
						[
							75.95335817563719,
							30.919768307280933
						],
						[
							75.94722031823444,
							30.931996476029703
						],
						[
							75.92929106473969,
							30.926377013187416
						],
						[
							75.92226671650985,
							30.922488908006514
						],
						[
							75.917186239737,
							30.922174099865494
						],
						[
							75.91412420228824,
							30.919961917879675
						],
						[
							75.90707924727086,
							30.919622744522066
						],
						[
							75.90422109231716,
							30.918477244456636
						],
						[
							75.89495881909136,
							30.916919267351624
						],
						[
							75.87724599918107,
							30.916478899997756
						]
					]
				],
				"type": "Polygon"
			},
			"id": 0
		},
		{
			"type": "Feature",
			"properties": {
				"area_name": "dandi_swami"
			},
			"geometry": {
				"coordinates": [
					[
						[
							75.81819304397689,
							30.897502352909285
						],
						[
							75.82160738960928,
							30.898407925897686
						],
						[
							75.82663578969311,
							30.90021904485863
						],
						[
							75.83327824412243,
							30.902456262153123
						],
						[
							75.83644427380463,
							30.902616061388144
						],
						[
							75.83967238249934,
							30.90389444566142
						],
						[
							75.84606652087624,
							30.906557691394994
						],
						[
							75.84991541970561,
							30.908315392983596
						],
						[
							75.84910839253229,
							30.909220863022114
						],
						[
							75.84724602213066,
							30.912203527260488
						],
						[
							75.84581820482384,
							30.914387204627957
						],
						[
							75.84538365173034,
							30.917156674968595
						],
						[
							75.844017913436,
							30.920778169063084
						],
						[
							75.84209346402065,
							30.923227925560397
						],
						[
							75.84110019980739,
							30.924133254474313
						],
						[
							75.83867911828602,
							30.926689431032614
						],
						[
							75.83731337999174,
							30.927541474702835
						],
						[
							75.83458190340303,
							30.92386698215391
						],
						[
							75.83253329596275,
							30.921630265395805
						],
						[
							75.82930518726684,
							30.92051188740257
						],
						[
							75.82663578969311,
							30.91955326728656
						],
						[
							75.82440094521169,
							30.91816857682592
						],
						[
							75.8213590735557,
							30.917529482161285
						],
						[
							75.81943462414159,
							30.91742296596867
						],
						[
							75.81924838710171,
							30.91294917879391
						],
						[
							75.81962086118153,
							30.9097534884543
						],
						[
							75.82005541427503,
							30.905598931467708
						],
						[
							75.82080036243596,
							30.902882392852987
						],
						[
							75.8208624414496,
							30.9020833962349
						],
						[
							75.81850343894078,
							30.901444194139117
						],
						[
							75.81651691051303,
							30.90107132427879
						],
						[
							75.81688938459405,
							30.89957983031428
						],
						[
							75.81819304397689,
							30.897502352909285
						]
					]
				],
				"type": "Polygon"
			},
			"id": 1
		},
		{
			"type": "Feature",
			"properties": {
				"area_name": "hambra_to_ayali_road"
			},
			"geometry": {
				"coordinates": [
					[
						[
							75.81816976688657,
							30.89745810185687
						],
						[
							75.81696196187488,
							30.89974679692955
						],
						[
							75.81671033583052,
							30.90108544227219
						],
						[
							75.8186730189733,
							30.901689985646186
						],
						[
							75.82083700295226,
							30.902078618656745
						],
						[
							75.82088732816032,
							30.90276951788971
						],
						[
							75.82018277523733,
							30.905748963711005
						],
						[
							75.81983049877687,
							30.909030564816305
						],
						[
							75.81927692148014,
							30.912873349384355
						],
						[
							75.81922659627006,
							30.915334377535387
						],
						[
							75.81937757189624,
							30.917493122040682
						],
						[
							75.81681098624873,
							30.91680232909826
						],
						[
							75.8126339939189,
							30.91641375587676
						],
						[
							75.80684659490888,
							30.916715979630126
						],
						[
							75.80241797653468,
							30.91714772619298
						],
						[
							75.79622797585415,
							30.918097561773166
						],
						[
							75.78908179620623,
							30.919220082572465
						],
						[
							75.78701846264534,
							30.919608644396348
						],
						[
							75.78324407198613,
							30.9201698975768
						],
						[
							75.78012390904175,
							30.920299417073764
						],
						[
							75.7755443150414,
							30.920731147464224
						],
						[
							75.77151829833988,
							30.920817493309002
						],
						[
							75.76784455809681,
							30.921162875906973
						],
						[
							75.76432179348188,
							30.918356606203517
						],
						[
							75.76040419565823,
							30.912696816086076
						],
						[
							75.7633152893062,
							30.90884788339568
						],
						[
							75.77926959574225,
							30.903042051307523
						],
						[
							75.7898230280147,
							30.898940471426897
						],
						[
							75.79907280100647,
							30.895477962019257
						],
						[
							75.8062118875443,
							30.89308076677075
						],
						[
							75.8119852357865,
							30.89542469166541
						],
						[
							75.81816976688657,
							30.89745810185687
						]
					]
				],
				"type": "Polygon"
			},
			"id": 2
		},
		{
			"type": "Feature",
			"properties": {
				"area_name": "sherpur_kalan"
			},
			"geometry": {
				"coordinates": [
					[
						[
							75.87981595698756,
							30.91061808434199
						],
						[
							75.87786273796425,
							30.907349617210897
						],
						[
							75.8755472813298,
							30.903004327682538
						],
						[
							75.87294421797807,
							30.898690925865367
						],
						[
							75.87000876623549,
							30.894348474198736
						],
						[
							75.8733475747719,
							30.892230052675146
						],
						[
							75.87877780601752,
							30.88924626363267
						],
						[
							75.88248605064015,
							30.887375777712094
						],
						[
							75.88341857789891,
							30.886909389052846
						],
						[
							75.88415568907499,
							30.886618951214444
						],
						[
							75.88557118739192,
							30.885577319794166
						],
						[
							75.88840218402999,
							30.884252544886294
						],
						[
							75.89244693561267,
							30.882060163917103
						],
						[
							75.90124604431992,
							30.87791886297441
						],
						[
							75.90429734814415,
							30.875969953534593
						],
						[
							75.9064261647672,
							30.875178197752007
						],
						[
							75.91338029906652,
							30.8850442256838
						],
						[
							75.9157219973516,
							30.888515364248747
						],
						[
							75.91756697175813,
							30.891742801279307
						],
						[
							75.92005059115075,
							30.896187960999995
						],
						[
							75.91735409009607,
							30.897527557710873
						],
						[
							75.91309645685138,
							30.899476028559192
						],
						[
							75.91047091634985,
							30.900815579263835
						],
						[
							75.90671000698364,
							30.901546235384956
						],
						[
							75.90287813706308,
							30.902337773222015
						],
						[
							75.89911722769685,
							30.903129304514664
						],
						[
							75.89791089827781,
							30.90337285128804
						],
						[
							75.89450479168121,
							30.9047732332086
						],
						[
							75.88073844419009,
							30.91013102704774
						],
						[
							75.87981595698756,
							30.91061808434199
						]
					]
				],
				"type": "Polygon"
			},
			"id": 3
		},
		{
			"type": "Feature",
			"properties": {
				"area_name": "tajpur_to_rahon"
			},
			"geometry": {
				"coordinates": [
					[
						[
							75.87012591266318,
							30.931158535454784
						],
						[
							75.87716748925993,
							30.91659577689964
						],
						[
							75.89464480234383,
							30.91698439311603
						],
						[
							75.90396021195413,
							30.91846151747519
						],
						[
							75.9069517412243,
							30.91965822047237
						],
						[
							75.91419415423175,
							30.92010357351903
						],
						[
							75.91711685856362,
							30.922175799735612
						],
						[
							75.92220961894685,
							30.92247897606459
						],
						[
							75.92894279920053,
							30.926222211155018
						],
						[
							75.94704863444491,
							30.9320334579674
						],
						[
							75.94276790609095,
							30.93731329210995
						],
						[
							75.93637335638141,
							30.95494368640165
						],
						[
							75.92150752126722,
							30.961455300811522
						],
						[
							75.91541145938538,
							30.959162529472692
						],
						[
							75.90526956010262,
							30.95318127823603
						],
						[
							75.89029136350047,
							30.94639703472521
						],
						[
							75.87784195333762,
							30.93766578306372
						],
						[
							75.87343278723813,
							30.933939464696607
						],
						[
							75.87012591266318,
							30.931158535454784
						]
					]
				],
				"type": "Polygon"
			},
			"id": 4
		},
		{
			"type": "Feature",
			"properties": {
				"area_name": "rahon_to_noorwala"
			},
			"geometry": {
				"coordinates": [
					[
						[
							75.86962840346308,
							30.931063949322635
						],
						[
							75.87270510601812,
							30.933505135115865
						],
						[
							75.88039686240859,
							30.939508867436217
						],
						[
							75.89024231058815,
							30.94643578232578
						],
						[
							75.89508811711369,
							30.948480775486175
						],
						[
							75.90101076953522,
							30.95144923606739
						],
						[
							75.90524123554911,
							30.953296231659778
						],
						[
							75.91047162989472,
							30.956198581159455
						],
						[
							75.90839485567,
							30.95870508476122
						],
						[
							75.90524123554911,
							30.963981719444575
						],
						[
							75.89970317094921,
							30.970511151215746
						],
						[
							75.89101148622694,
							30.976710400421382
						],
						[
							75.87770474767217,
							30.976776347716367
						],
						[
							75.87239743576379,
							30.974336267443476
						],
						[
							75.866782453598,
							30.961541312141463
						],
						[
							75.86132130656094,
							30.954021827301617
						],
						[
							75.85901377964319,
							30.949668170785785
						],
						[
							75.85870610938889,
							30.943401195693085
						],
						[
							75.85686008785405,
							30.935352477527317
						],
						[
							75.85786001618581,
							30.935088573654483
						],
						[
							75.86709012385384,
							30.932581450524253
						],
						[
							75.86962840346308,
							30.931063949322635
						]
					]
				],
				"type": "Polygon"
			},
			"id": 5
		},
		{
			"type": "Feature",
			"properties": {
				"area_name": "noorwala_to_metro"
			},
			"geometry": {
				"coordinates": [
					[
						[
							75.82269217111917,
							30.955351082694932
						],
						[
							75.82847998526191,
							30.947702186840544
						],
						[
							75.83550126799173,
							30.938831955812446
						],
						[
							75.83777844076855,
							30.936471847438284
						],
						[
							75.84280719732033,
							30.93687876683215
						],
						[
							75.84726666067448,
							30.93687876683215
						],
						[
							75.85144147743364,
							30.936553231456102
						],
						[
							75.85438282560384,
							30.936146310675696
						],
						[
							75.85665999838076,
							30.93533246392016
						],
						[
							75.85789346696976,
							30.939483009936566
						],
						[
							75.85903205335723,
							30.944284397152273
						],
						[
							75.85893717115948,
							30.946807063261843
						],
						[
							75.85903205335723,
							30.949736527427092
						],
						[
							75.85998087534935,
							30.951363968710623
						],
						[
							75.86187851932974,
							30.954618768111914
						],
						[
							75.8641556921066,
							30.957954822411395
						],
						[
							75.86671751148228,
							30.96145348588749
						],
						[
							75.86747656907326,
							30.96332481141502
						],
						[
							75.86899468425915,
							30.966823278166515
						],
						[
							75.8705127994431,
							30.96991483976926
						],
						[
							75.8664328648835,
							30.97015890615822
						],
						[
							75.85893717115948,
							30.970077550764827
						],
						[
							75.85172612403053,
							30.967718214188537
						],
						[
							75.84641272088388,
							30.967799571592423
						],
						[
							75.84185837532817,
							30.968125000516295
						],
						[
							75.83730402977443,
							30.966579203250433
						],
						[
							75.8320855088254,
							30.962755281440707
						],
						[
							75.8265823412815,
							30.95941939481075
						],
						[
							75.82269217111917,
							30.955351082694932
						]
					]
				],
				"type": "Polygon"
			},
			"id": 6
		},
		{
			"type": "Feature",
			"properties": {
				"area_name": "mangli_nichi"
			},
			"geometry": {
				"coordinates": [
					[
						[
							75.92005058647621,
							30.896187940547875
						],
						[
							75.91643159821757,
							30.889794152609383
						],
						[
							75.91408989993394,
							30.88620126539439
						],
						[
							75.91004514835132,
							30.880476726002357
						],
						[
							75.90628423898514,
							30.87517817729544
						],
						[
							75.90770345006621,
							30.874630034844586
						],
						[
							75.91032899056637,
							30.873229212114765
						],
						[
							75.91437374214902,
							30.87152383506792
						],
						[
							75.91728312486708,
							30.86981842767581
						],
						[
							75.92146979755734,
							30.86756480707929
						],
						[
							75.92452110138296,
							30.865493865763654
						],
						[
							75.92913353739866,
							30.862935582370284
						],
						[
							75.93410077618381,
							30.85964626055683
						],
						[
							75.93984858106407,
							30.85635682590207
						],
						[
							75.9452415831748,
							30.8530063598037
						],
						[
							75.94815096589286,
							30.851666140591362
						],
						[
							75.95262148079956,
							30.848559196758615
						],
						[
							75.95602758739474,
							30.84673153573175
						],
						[
							75.95950465454581,
							30.84466014447564
						],
						[
							75.96397516945251,
							30.847645370597306
						],
						[
							75.96731031549461,
							30.850569583670662
						],
						[
							75.97029065876578,
							30.853371870884374
						],
						[
							75.97199371206341,
							30.855077570841843
						],
						[
							75.97390964702299,
							30.858915284828996
						],
						[
							75.97554173976752,
							30.862326457214962
						],
						[
							75.97866400414762,
							30.8688438955419
						],
						[
							75.97312908092798,
							30.869513887447823
						],
						[
							75.96447189333102,
							30.874508224985235
						],
						[
							75.95446645520468,
							30.879745909117915
						],
						[
							75.94992497974351,
							30.882121043610596
						],
						[
							75.94460293818875,
							30.884191625638024
						],
						[
							75.93857129109199,
							30.886810238815244
						],
						[
							75.9342426972928,
							30.8887589277429
						],
						[
							75.93062370903417,
							30.8911338387679
						],
						[
							75.92828201074909,
							30.892412612618656
						],
						[
							75.92551454913996,
							30.89375226214706
						],
						[
							75.92005058647621,
							30.896187940547875
						]
					]
				],
				"type": "Polygon"
			},
			"id": 7
		},
		{
			"type": "Feature",
			"properties": {
				"area_name": "ludhiana_central"
			},
			"geometry": {
				"coordinates": [
					[
						[
							75.86988799820244,
							30.930856618506226
						],
						[
							75.86718603813179,
							30.932645214935135
						],
						[
							75.8616074088736,
							30.934023510157303
						],
						[
							75.85659708052552,
							30.935476936148532
						],
						[
							75.85345353556198,
							30.936262142580432
						],
						[
							75.84991174622928,
							30.936670366231795
						],
						[
							75.84204460856131,
							30.936921463980667
						],
						[
							75.8378342846585,
							30.93657224684428
						],
						[
							75.84404575844914,
							30.927898239056745
						],
						[
							75.84272213874839,
							30.92774553028306
						],
						[
							75.84002276576604,
							30.92790338551019
						],
						[
							75.83873690159189,
							30.92790338551019
						],
						[
							75.83794879129115,
							30.927334077097925
						],
						[
							75.84068643759673,
							30.924416318288692
						],
						[
							75.84184786330417,
							30.92352673996939
						],
						[
							75.84350704288346,
							30.92132055003387
						],
						[
							75.84450255063197,
							30.919434573134367
						],
						[
							75.84553953786946,
							30.916765674360462
						],
						[
							75.84591285327454,
							30.914559328491734
						],
						[
							75.84699132000085,
							30.91274439294324
						],
						[
							75.84757203285375,
							30.911178538532965
						],
						[
							75.8483186636656,
							30.910110895835388
						],
						[
							75.84902381498685,
							30.909256773100907
						],
						[
							75.8502681996705,
							30.907868807398273
						],
						[
							75.85320100627172,
							30.905722478010162
						],
						[
							75.85420477451288,
							30.902947312761967
						],
						[
							75.85665843021383,
							30.900937660113115
						],
						[
							75.86375526686894,
							30.89708016631515
						],
						[
							75.86991079864663,
							30.89427892608667
						],
						[
							75.87256783539999,
							30.897947349599747
						],
						[
							75.87655373372101,
							30.904560838197938
						],
						[
							75.87999894954663,
							30.910538200556473
						],
						[
							75.87534171824547,
							30.920945878684343
						],
						[
							75.86988799820244,
							30.930856618506226
						]
					]
				],
				"type": "Polygon"
			},
			"id": 8
		},
		{
			"type": "Feature",
			"properties": {
				"area_name": "metro_to_railway"
			},
			"geometry": {
				"coordinates": [
					[
						[
							75.83753919802496,
							30.927381860056144
						],
						[
							75.83911749184588,
							30.927988774800312
						],
						[
							75.84009712249329,
							30.927755346508803
						],
						[
							75.84227407948768,
							30.927755346508803
						],
						[
							75.84407006900699,
							30.927755346508803
						],
						[
							75.84124002491507,
							30.931723549979324
						],
						[
							75.83802901334923,
							30.936391813810445
						],
						[
							75.83509012140703,
							30.93942606306061
						],
						[
							75.83274989263822,
							30.942600251497794
						],
						[
							75.82594690203157,
							30.95109535481791
						],
						[
							75.82268146654053,
							30.955389295484622
						],
						[
							75.81234092081803,
							30.9520755104475
						],
						[
							75.81299400791667,
							30.951002006138623
						],
						[
							75.8202868138466,
							30.944327339157013
						],
						[
							75.83051851171871,
							30.934151075618587
						],
						[
							75.83753919802496,
							30.927381860056144
						]
					]
				],
				"type": "Polygon"
			},
			"id": 9
		},
		{
			"type": "Feature",
			"properties": {
				"area_name": "railway_to_jassian"
			},
			"geometry": {
				"coordinates": [
					[
						[
							75.81229183023015,
							30.951964518903893
						],
						[
							75.80039265713833,
							30.94148893563053
						],
						[
							75.7903917957058,
							30.935015754774142
						],
						[
							75.78978989200792,
							30.933903753209293
						],
						[
							75.79150300253224,
							30.932632878441353
						],
						[
							75.79469772215487,
							30.931719426767913
						],
						[
							75.80085565998132,
							30.930091078227022
						],
						[
							75.80247616993631,
							30.929733632153173
						],
						[
							75.80326327477101,
							30.92961448316501
						],
						[
							75.80317067420168,
							30.92508671159885
						],
						[
							75.80622649297302,
							30.924490936223123
						],
						[
							75.81034721828524,
							30.922981621995348
						],
						[
							75.81349563762413,
							30.921829760902483
						],
						[
							75.81645885582614,
							30.920558725667902
						],
						[
							75.81844976805658,
							30.919605438158612
						],
						[
							75.81942207402815,
							30.91742078511831
						],
						[
							75.82136668597306,
							30.91753994929769
						],
						[
							75.8242836038913,
							30.918175489081932
						],
						[
							75.8260430146994,
							30.919208232225998
						],
						[
							75.82766352465256,
							30.919962922087592
						],
						[
							75.82993223858918,
							30.920757326036878
						],
						[
							75.83247875423197,
							30.92179004130685
						],
						[
							75.83349736048726,
							30.923100779247605
						],
						[
							75.83511787044225,
							30.924490936223123
						],
						[
							75.83678468068103,
							30.92639740436151
						],
						[
							75.83724768352587,
							30.927588927648173
						],
						[
							75.8326176550851,
							30.932156296048632
						],
						[
							75.82817282778112,
							30.936644019442326
						],
						[
							75.82423730360759,
							30.940257873641073
						],
						[
							75.82062588142392,
							30.94407014315931
						],
						[
							75.81812566606484,
							30.946293896820023
						],
						[
							75.81497724672604,
							30.949113224385954
						],
						[
							75.81229183023015,
							30.951964518903893
						]
					]
				],
				"type": "Polygon"
			},
			"id": 10
		},
		{
			"type": "Feature",
			"properties": {
				"area_name": "ferozepur_to_gill_road"
			},
			"geometry": {
				"coordinates": [
					[
						[
							75.8060961960424,
							30.893120129817802
						],
						[
							75.80832595246594,
							30.891827274322196
						],
						[
							75.81784761502854,
							30.888517484719543
						],
						[
							75.82815270552436,
							30.884276649633946
						],
						[
							75.83960280607553,
							30.88003562679654
						],
						[
							75.84526759266322,
							30.877397822778534
						],
						[
							75.84978736919646,
							30.873984086253074
						],
						[
							75.8547289915395,
							30.86943224838754
						],
						[
							75.85828454907968,
							30.866276870279293
						],
						[
							75.8593692954465,
							30.866276870279293
						],
						[
							75.85906797701168,
							30.87227717238696
						],
						[
							75.85894744963673,
							30.877915044976135
						],
						[
							75.85858586751453,
							30.885311016967037
						],
						[
							75.85864613120191,
							30.888207186080308
						],
						[
							75.85834481276595,
							30.89229270431082
						],
						[
							75.85834481276595,
							30.899997827612864
						],
						[
							75.8565369021533,
							30.90092860589813
						],
						[
							75.85490978260066,
							30.902169629536488
						],
						[
							75.85406609098123,
							30.90341063708499
						],
						[
							75.85322239936178,
							30.90578918991487
						],
						[
							75.85201712562,
							30.906616498783762
						],
						[
							75.84990789657141,
							30.90827109506688
						],
						[
							75.8416517714368,
							30.904858458890104
						],
						[
							75.83930148763952,
							30.904031134826354
						],
						[
							75.83646909434518,
							30.902686717970212
						],
						[
							75.83345590998962,
							30.902531591733492
						],
						[
							75.83068378038266,
							30.901755956778032
						],
						[
							75.82718848653118,
							30.900514927777806
						],
						[
							75.82315081949511,
							30.898963618902613
						],
						[
							75.81766682396739,
							30.89725715010664
						],
						[
							75.8118815100049,
							30.89549893832411
						],
						[
							75.8060961960424,
							30.893120129817802
						]
					]
				],
				"type": "Polygon"
			},
			"id": 11
		},
		{
			"type": "Feature",
			"properties": {
				"area_name": "jassian_to_hambra_road"
			},
			"geometry": {
				"coordinates": [
					[
						[
							75.78981596649257,
							30.933950512957196
						],
						[
							75.78581853071867,
							30.9316889093477
						],
						[
							75.77986490296718,
							30.930156824894482
						],
						[
							75.77629272631737,
							30.93001091080906
						],
						[
							75.77204013506699,
							30.929208379360333
						],
						[
							75.76940352849232,
							30.92709258234497
						],
						[
							75.7679576474676,
							30.921109730575893
						],
						[
							75.7745066379924,
							30.920598981989954
						],
						[
							75.78148088764283,
							30.920234159901867
						],
						[
							75.78743451539268,
							30.919577476636746
						],
						[
							75.79279278036913,
							30.918482994510228
						],
						[
							75.79993713366889,
							30.9175344332058
						],
						[
							75.80563560594388,
							30.916731797063093
						],
						[
							75.81286501106916,
							30.91651289512845
						],
						[
							75.81686244684471,
							30.916731797063093
						],
						[
							75.81949905341938,
							30.91738849986247
						],
						[
							75.81839337969495,
							30.919723406640927
						],
						[
							75.81431089209386,
							30.921474549324685
						],
						[
							75.81124902639351,
							30.92264195997079
						],
						[
							75.80886757529359,
							30.923517508605443
						],
						[
							75.80623096871889,
							30.924466010580772
						],
						[
							75.80316910301855,
							30.925195621084896
						],
						[
							75.80308405119305,
							30.929646124621755
						],
						[
							75.80019228914364,
							30.93037569560549
						],
						[
							75.7972154752687,
							30.930959348383823
						],
						[
							75.7933030913187,
							30.932053687741785
						],
						[
							75.79117679569345,
							30.932783240354794
						],
						[
							75.78981596649257,
							30.933950512957196
						]
					]
				],
				"type": "Polygon"
			},
			"id": 12
		},
		{
			"type": "Feature",
			"properties": {
				"area_name": "ludhiana_bypass_dhandari"
			},
			"geometry": {
				"coordinates": [
					[
						[
							75.89948161327032,
							30.829299853169104
						],
						[
							75.9062611733903,
							30.824096804272514
						],
						[
							75.92023817474752,
							30.830263841011558
						],
						[
							75.93295945465954,
							30.840863741573898
						],
						[
							75.94167910897905,
							30.855278126044915
						],
						[
							75.92891197410157,
							30.863043987550412
						],
						[
							75.9169499564727,
							30.870052149616967
						],
						[
							75.90935502464629,
							30.873963459138494
						],
						[
							75.9000512331568,
							30.878037570145054
						],
						[
							75.88543098939044,
							30.886022325226023
						],
						[
							75.86967150584744,
							30.894332281826607
						],
						[
							75.85770948822045,
							30.900197699394226
						],
						[
							75.85903860129014,
							30.879178290187056
						],
						[
							75.85903860129014,
							30.864836821963692
						],
						[
							75.87878542404022,
							30.848211071598755
						],
						[
							75.89948161327032,
							30.829299853169104
						]
					]
				],
				"type": "Polygon"
			},
			"id": 13
		},
		{
			"type": "Feature",
			"properties": {
				"area_name": "dhandra_gill_road"
			},
			"geometry": {
				"coordinates": [
					[
						[
							75.86029249918184,
							30.850737337298597
						],
						[
							75.87535226005207,
							30.850958975277464
						],
						[
							75.86975863458565,
							30.855982632085983
						],
						[
							75.85882955098342,
							30.864625660987315
						],
						[
							75.85900166253543,
							30.866250758886395
						],
						[
							75.85125664265897,
							30.872159973554858
						],
						[
							75.84557696141735,
							30.877256378582544
						],
						[
							75.84402795744202,
							30.874228112619463
						],
						[
							75.84316739967835,
							30.872381562017708
						],
						[
							75.84282317657252,
							30.870978159765684
						],
						[
							75.84308134390147,
							30.86935314201108
						],
						[
							75.84222078613783,
							30.867432630963975
						],
						[
							75.84075783793935,
							30.864551792246772
						],
						[
							75.8390367224103,
							30.86211409186842
						],
						[
							75.83228672244982,
							30.858069151733865
						],
						[
							75.82949528820188,
							30.848409726638394
						],
						[
							75.83836979014336,
							30.848742271191412
						],
						[
							75.85061122433662,
							30.85029386748394
						],
						[
							75.85829170237918,
							30.85029396270602
						],
						[
							75.86029249918184,
							30.850737337298597
						]
					]
				],
				"type": "Polygon"
			},
			"id": 14
		},
		{
			"type": "Feature",
			"properties": {
				"area_name": "phullanwal"
			},
			"geometry": {
				"coordinates": [
					[
						[
							75.82380484998794,
							30.88604519388855
						],
						[
							75.8201905073795,
							30.881983236601016
						],
						[
							75.81786700141572,
							30.8788812623298
						],
						[
							75.81537138390158,
							30.874301973903883
						],
						[
							75.8129618221626,
							30.87127361457938
						],
						[
							75.80857297756563,
							30.867801962999764
						],
						[
							75.82957058700649,
							30.848225404419054
						],
						[
							75.83223831607438,
							30.858198867612884
						],
						[
							75.83938094551613,
							30.862261833049075
						],
						[
							75.84316739967835,
							30.869500872036355
						],
						[
							75.84290923234943,
							30.87075656805814
						],
						[
							75.84290923234943,
							30.871716795091373
						],
						[
							75.84445823632473,
							30.87481900129795
						],
						[
							75.8457490729694,
							30.87718251957604
						],
						[
							75.84308134390147,
							30.878659688896164
						],
						[
							75.83800405309461,
							30.88065383135384
						],
						[
							75.83266859495711,
							30.882647932306938
						],
						[
							75.82664469060964,
							30.885306669011328
						],
						[
							75.82380484998794,
							30.88604519388855
						]
					]
				],
				"type": "Polygon"
			},
			"id": 15
		},
		{
			"type": "Feature",
			"properties": {
				"area_name": "ayali_to_tharike"
			},
			"geometry": {
				"coordinates": [
					[
						[
							75.80822876627911,
							30.86787583967177
						],
						[
							75.8117570523884,
							30.870608851235744
						],
						[
							75.81408055835215,
							30.872159984822247
						],
						[
							75.81519928344474,
							30.87385881661349
						],
						[
							75.81640406431421,
							30.87629621832039
						],
						[
							75.81812517984159,
							30.87910284651832
						],
						[
							75.82122318779221,
							30.882869507783965
						],
						[
							75.82371880530803,
							30.88611905732928
						],
						[
							75.8068518731335,
							30.89283936685308
						],
						[
							75.79747179350659,
							30.89608857815152
						],
						[
							75.78542398481,
							30.900592984156063
						],
						[
							75.77397856654983,
							30.90502334068954
						],
						[
							75.76322159449964,
							30.90878898251691
						],
						[
							75.76029569810109,
							30.912849802749662
						],
						[
							75.75539051884627,
							30.90302970562415
						],
						[
							75.75160406468494,
							30.8953869186112
						],
						[
							75.75504629574047,
							30.888334596088797
						],
						[
							75.76218892518213,
							30.88205707925927
						],
						[
							75.76872916418921,
							30.879545990823516
						],
						[
							75.77647418406394,
							30.871716806359544
						],
						[
							75.77793713226413,
							30.871199762229168
						],
						[
							75.78258414418829,
							30.870682715309513
						],
						[
							75.78869410431432,
							30.87083044328557
						],
						[
							75.79833235127023,
							30.87127362584684
						],
						[
							75.8034096420771,
							30.8703872586743
						],
						[
							75.80822876627911,
							30.86787583967177
						]
					]
				],
				"type": "Polygon"
			},
			"id": 16
		}
	]

	pi_obj = PreInspection.objects.get(pk=preinspection_id)
	point = Point(pi_obj.longitude, pi_obj.latitude)

	area_name = 'mix_area'
	for service_area in service_areas:
		polygon = Polygon(service_area.get('geometry').get('coordinates')[0])

		if polygon.contains(point):
			area_name = service_area['properties']['area_name']

	return area_name


def get_circles_intersect(x1, y1, r1, x2, y2, r2):
	d = math.sqrt((x1 - x2) * (x1 - x2) + (y1 - y2) * (y1 - y2))

	if d <= r1 - r2:
		print("Circle B is inside A")
		return True
	elif d <= r2 - r1:
		print("Circle A is inside B")
		return True
	elif d < r1 + r2:
		print("Circle intersect to each other")
		return True
	elif d == r1 + r2:
		print("Circle touch to each other")
		return True
	else:
		print("Circle not touch to each other")
		return False


def evaluate_change_cylinder_type_requests():
	from ujjwala.models import ChangeCylinderTypeRequest

	for cctr_obj in ChangeCylinderTypeRequest.objects.filter(status=ChangeCylinderTypeRequestStatusEnum.DRAFTED):
		if cctr_obj.parent.customer_profile.salesorder_set.count() == 4:
			cctr_obj.transition_change_cylinder_type_request_scheduled()
