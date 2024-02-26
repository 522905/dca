import datetime
import json
from functools import partial

import django_rq
import requests
from django.contrib.contenttypes.models import ContentType
from django.db import transaction

from ujjwala.enums import PreInspectionStatusEnum, ConnectionDisbursementStatusEnum, UjjwalaApplicationDocumentsEnum, \
	PreInspectionRejectionReasonsEnum, product_quantity_map
from ujjwala.models import PreInspectionDocuments
from ujjwala.ujjwala_functions import re_create_legal_docs, download_ujjwala_physical_legal_docs
from ujjwala.vici_functions import add_lead_to_vicidial_list, delete_lead_from_vicidial_list
from utils.global_functions import upload_file_to_minio_bucket

VICIDIAL_LIST = 1201


def preinspection_update_family_members(preinspection_id, family_members):
	from ujjwala.models import PreInspection

	pi_obj = PreInspection.objects.get(pk=preinspection_id)
	fm_list = pi_obj.parent.family_members.all()

	for family_member in family_members:
		fm_obj = fm_list.get(relation=family_member['relation'])
		fm_obj.name = family_member['name']
		fm_obj.dob = family_member['dob']
		fm_obj.uid_no = family_member['uid_no']
		fm_obj.uid_front_link = family_member['uid_front_link']
		fm_obj.uid_back_link = family_member['uid_back_link']
		fm_obj.save()


def preinspection_update_in_dca(preinspection_id, action, rejected_reasons=None):
	from ujjwala.models import PreInspection

	pi_obj = PreInspection.objects.get(pk=preinspection_id)

	if action == 'PREINSPECTION_ACCEPT':
		pi_obj.pre_inspection_review(review_status='ACCEPTED', rejected_reasons=[])
	else:
		if not rejected_reasons:
			rejected_reasons = [PreInspectionRejectionReasonsEnum.CONDITION_LOCATION_MISMATCH]
		pi_obj.pre_inspection_review(rejected_reasons=rejected_reasons)
	pi_obj.save()


def preinspection_create_legal_docs(preinspection_id):
	from ujjwala.models import PreInspection, ConnectionDisbursement

	pi_obj = PreInspection.objects.get(pk=preinspection_id)

	ci_obj = ConnectionDisbursement.objects.get_or_create(
		parent=pi_obj.parent
	)[0]
	ci_obj.mechanic = pi_obj.mechanic
	ci_obj.pending_quantity = product_quantity_map.get(pi_obj.parent.product, 0)
	ci_obj.save()

	# Bucket Name: ujjwaladocuments
	physical_legal_document = download_ujjwala_physical_legal_docs(pi_obj.parent)
	upload_url = upload_file_to_minio_bucket(
		physical_legal_document,
		"ujjwaladocuments",
		"ujjwala_{}_physical_legal_document".format(pi_obj.parent_id)
	)

	if PreInspectionDocuments.objects.filter(
		parent=pi_obj, type=UjjwalaApplicationDocumentsEnum.PHYSICAL_LEGAL_DOCUMENT
	).count() > 1:
		PreInspectionDocuments.objects.filter(
			parent=pi_obj, type=UjjwalaApplicationDocumentsEnum.PHYSICAL_LEGAL_DOCUMENT
		).delete()

	pi_doc_obj = PreInspectionDocuments.objects.get_or_create(
		parent=pi_obj, type=UjjwalaApplicationDocumentsEnum.PHYSICAL_LEGAL_DOCUMENT
	)[0]
	pi_doc_obj.link = upload_url
	pi_doc_obj.save()

	pi_obj.parent.event_legal_documents_upload_channel_whatsapp()
	create_job_function = partial(
		django_rq.enqueue,
		"ujjwala.jobs.is_application_ready_for_disbursement",
		args=(pi_obj.parent.id,)
	)
	transaction.on_commit(create_job_function)


def preinspection_add_lead_to_vicidial(preinspection_id, process_instance_id):
	from ujjwala.models import PreInspection

	obj = PreInspection.objects.get(pk=preinspection_id)
	add_lead_to_vicidial_list(VICIDIAL_LIST, obj.parent.contact_mobile, obj.parent.name, obj.parent_id)

	res = requests.post(
		"http://192.168.168.3/vicidial/non_agent_api.php?source=ujjwala&user=6666&pass=C00lerMaster101"
		"&custom_fields=Y&function=add_lead&phone_number={}&phone_code=1&list_id={}"
		"&first_name={}&last_name={}&process_instance_id={}".format(
			obj.parent.contact_mobile,
			VICIDIAL_LIST,
			obj.parent.name, obj.parent_id, process_instance_id)
	)
	res.raise_for_status()
	obj.parent.event_whatsapp_camunda_update_address(process_instance_id)
	return res.text


def preinspection_delete_lead_from_vicidial(preinspection_id, contact_mobile):
	return delete_lead_from_vicidial_list(VICIDIAL_LIST, contact_mobile)


def review_address_add_lead_to_vicidial(list_id, contact_mobile, name, application_id, process_instance_id):
	from ujjwala.models import UjjwalaV2Application

	application_obj = UjjwalaV2Application.objects.get(id=application_id)

	res = requests.post(
		"http://192.168.168.3/vicidial/non_agent_api.php?source=ujjwala&user=6666&pass=C00lerMaster101"
		"&custom_fields=Y&function=add_lead&phone_number={}&phone_code=1&list_id={}"
		"&first_name={}&last_name={}&process_instance_id={}".format(
			contact_mobile,
			list_id,
			name, application_id, process_instance_id)
	)
	res.raise_for_status()
	application_obj.event_whatsapp_camunda_update_address(process_instance_id)
	return res.text


def review_address_delete_lead_from_vicidial(list_id, contact_mobile):
	return delete_lead_from_vicidial_list(list_id, contact_mobile)


def review_address_update_in_dca(application_id, address_json, agent=''):
	from ujjwala.models import UjjwalaV2Application, ConnectionDisbursement
	from django_comments_xtd.models import XtdComment

	application = UjjwalaV2Application.objects.get(pk=application_id)

	if agent:
		comment = "Old Addr: {} Filled By Agent {}".format(json.dumps(application.address_json), agent)
	else:
		comment = "Old Addr: {}".format(json.dumps(application.address_json))

	XtdComment.objects.create(content_type=ContentType.objects.get(
		app_label='ujjwala', model='ujjwalav2application'
	), object_pk=application_id, site_id=1,	comment=comment)

	application.address_json = address_json
	application.address_verified = True
	application.address_verified_on = datetime.datetime.now()
	application.address_verified_by = agent
	application.save()

	ci_obj: ConnectionDisbursement = ConnectionDisbursement.objects.filter(parent_id=application_id).first()
	if ci_obj.status in (
	ConnectionDisbursementStatusEnum.LEGAL_DOCUMENTS_ACCEPTED, ConnectionDisbursementStatusEnum.LEGAL_DOCUMENTS_REVIEW):
		ci_obj.documents.all().delete()
		ci_obj.status = ConnectionDisbursementStatusEnum.LEGAL_DOCUMENTS_PENDING
		ci_obj.save()
	re_create_legal_docs(application)
	application.event_legal_documents_reupload_channel_whatsapp("Address Updated")


def variables_to_update_for_preinspection(task):
	from ujjwala.models import PreInspection
	variables = {}

	preinspection_id = task.get_variable('preinspection_id')
	if preinspection_id:
		pi_obj = PreInspection.objects.get(pk=preinspection_id)

		kitchen_photo = task.get_variable('kitchen_photo')

		if kitchen_photo:
			variables["kitchen_photo"] = {"value": pi_obj.documents.get(type=UjjwalaApplicationDocumentsEnum.KITCHEN_PHOTO).link}

		main_gate_photo = task.get_variable('kitchen_photo')
		if main_gate_photo:
			variables["main_gate_photo"] = {"value": pi_obj.documents.get(type=UjjwalaApplicationDocumentsEnum.MAIN_GATE).link}
	return variables
