import io
import zipfile
from datetime import datetime

import magic
import requests
from django.conf import settings
from django.contrib import admin
from django.http import HttpResponse
from django.template import loader
from django.utils.safestring import mark_safe
from django_admin_listfilter_dropdown.filters import DropdownFilter
from django_fsm_log.admin import StateLogInline
from import_export.admin import ExportActionMixin
from rangefilter.filters import DateRangeFilter

from fsm_admin2_custom.admin import FSMTransitionCustomMixin
from .enums import ResidentialStatusEnum, UjjwalaApplicationDocumentsEnum, FamilyMemberRelationEnum, MaritalStatusEnum
from .models import UjjwalaV2Application, FamilyMembers, UjjwalaApplicationDocuments, UjjwalaV2ApplicationStatus


class UjjwalaApplicationDocumentsInline(admin.TabularInline):
	extra = 0
	model = UjjwalaApplicationDocuments
	fields = ('type', 'download_links', )
	readonly_fields = ('download_links', )
	# template = 'connection_app/admin/document-inline.html'


class FamilyMembersInline(admin.TabularInline):
	extra = 0
	model = FamilyMembers
	fields = ('name', 'relation', 'dob', 'uid_no', 'download_links', )
	readonly_fields = ('download_links', )


@admin.register(UjjwalaV2Application)
class UjjwalaV2Admin(ExportActionMixin, FSMTransitionCustomMixin, admin.ModelAdmin):
	list_display = (
		'id',
		'name',
		'address',
		'address_json',
		'contact_mobile',
		'referral_code',
		'robo_sdms_dedup',
		'status',
		'consumer_id'
	)

	search_fields = ('id', 'name', 'referral_code', 'contact_mobile', 'robo_sdms_dedup')
	ordering = ('id',)

	list_filter = (
		('created_on', DateRangeFilter),
		('updated_on', DateRangeFilter),
		('status', DropdownFilter),
		('version', DropdownFilter),
		('robo_sdms_dedup', DropdownFilter)
	)

	inlines = [
		FamilyMembersInline, UjjwalaApplicationDocumentsInline, StateLogInline
	]
	fsm_fields = ['status', 'pre_inspection_status']

	def has_change_permission(self, request, obj=None):
		if not obj:
			return True
		return obj.status == UjjwalaV2ApplicationStatus.EDIT_APPLICATION

	def get_readonly_fields(self, request, obj=None):
		readonly_fields = super().get_readonly_fields(request, obj)

		if obj and obj.status in (
				UjjwalaV2ApplicationStatus.EKYC_ACCEPTED, UjjwalaV2ApplicationStatus.DOCUMENTS_UPLOADED
		):
			readonly_fields = readonly_fields + ['download_legal_docs']

		return readonly_fields

	def download_legal_docs(self, obj=None):
		return mark_safe("""
			<input type="submit" value="Download Legal Docs" name="_download-legal-doc-pdf">
		""")

	def download_legal_documents_pdf(self, obj):
		attachments = []
		if obj.version in ('V2', 'V3'):
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
			uid_front_doc_file = requests.get("{}{}".format(settings.THUMBOR_URL, family_member.uid_front_link))
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

	def change_view(self, request, object_id, form_url='', extra_context=None):
		if "_download-legal-doc-pdf" in request.POST:
			obj = UjjwalaV2Application.objects.get(pk=object_id)
			return self.download_legal_documents_pdf(obj)
		return super().change_view(request, object_id, form_url=form_url, extra_context=extra_context)
