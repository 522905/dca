import requests
from django.conf import settings
from django.db import models
from django.template import loader
from django.utils.safestring import mark_safe
from django_currentuser.middleware import get_current_user
from django_fsm import transition, FSMField, GET_STATE
from django_fsm_log.decorators import fsm_log_description, fsm_log_by

from connection_app.enums import ApplicationTypeEnum, ItemCodeEnum, ConnectionTypeEnum, \
	ConnectionApplicationProcessType, ConnectionApplicationLeadStatus, ConnectionApplicationDocumentsEnum, \
	ConnectionApplicationLeadCommunicationMode
from connection_app.forms import ConnectionVerificationResult, BackOfficeForm, FrontOfficeForm, SubmitLead


class ConnectionApplication(models.Model):
	created_on = models.DateTimeField(auto_now_add=True)
	updated_on = models.DateTimeField(auto_now=True)
	name = models.CharField(max_length=255, null=True)
	mobile = models.CharField(max_length=10)
	address = models.TextField()
	application_type = models.CharField(max_length=25, choices=ApplicationTypeEnum.choices)
	item_code = models.CharField(max_length=25, choices=ItemCodeEnum.choices)
	connection_type = models.CharField(max_length=25, choices=ConnectionTypeEnum.choices)
	referral_code = models.CharField(max_length=16, null=True, blank=True)
	status = FSMField(default=ConnectionApplicationLeadStatus.DRAFT, choices=ConnectionApplicationLeadStatus.choices)
	applicant_remarks = models.TextField(null=True, blank=True)
	required_by = models.DateField(null=True, blank=True)
	consumer_id = models.CharField(max_length=25, null=True, blank=True)
	process_type = models.CharField(
		max_length=25, choices=ConnectionApplicationProcessType.choices, null=True, blank=True
	)
	communication_mode = models.CharField(
		max_length=25, choices=ConnectionApplicationLeadCommunicationMode.choices, null=True, blank=True
	)

	def lead_details_in_html(self):
		template = loader.get_template("connection_app/application_details_template.html")
		html = template.render({'obj': self})
		return mark_safe(html)

	lead_details_in_html.short_description = 'Lead Details'

	@fsm_log_description
	@fsm_log_by
	@transition(
		field=status,
		source=ConnectionApplicationLeadStatus.DRAFT,
		target=ConnectionApplicationLeadStatus.SUBMITTED,
		custom=dict(
			short_description='Submit Application', admin=True
		),
		# conditions=[can_close]
	)
	def submit(self, *args, **kwargs):
		# Function To Check Preferred Communication
		# and update in Communication Mode and send proper message using mode
		pass


	@fsm_log_description
	@fsm_log_by
	@transition(
		field=status,
		source=ConnectionApplicationLeadStatus.SUBMITTED,
		target=GET_STATE(
			lambda self, **kwargs: \
			ConnectionApplicationLeadStatus.BACK_OFFICE \
			if kwargs.get("required") else ConnectionApplicationLeadStatus.NOT_INTERESTED,
			states=[
				ConnectionApplicationLeadStatus.BACK_OFFICE,
				ConnectionApplicationLeadStatus.NOT_INTERESTED
			]
		),
		custom=dict(short_description='Application Confirmation', admin=True, form=ConnectionVerificationResult),
	)
	def confirm_application(self, *args, **kwargs):
		if kwargs.get("required"):
			self.required_by = kwargs.get("required_by")
			self.applicant_remarks = kwargs.get("applicant_remarks")


	@fsm_log_description
	@fsm_log_by
	@transition(
		field=status,
		source=ConnectionApplicationLeadStatus.BACK_OFFICE,
		target=ConnectionApplicationLeadStatus.FRONT_OFFICE,
		custom=dict(short_description='Back Office Processing', admin=True, form=BackOfficeForm),
	)
	def front_office_process(self, *args, **kwargs):
		self.consumer_id = kwargs.get("consumer_id")
		self.process_type = kwargs.get("process_type")


	@fsm_log_description
	@fsm_log_by
	@transition(
		field=status,
		source=ConnectionApplicationLeadStatus.FRONT_OFFICE,
		target=GET_STATE(
			lambda self, **kwargs: \
			ConnectionApplicationLeadStatus.COMPLETED \
			if kwargs.get("verified") else ConnectionApplicationLeadStatus.BACK_OFFICE,
			states=[
				ConnectionApplicationLeadStatus.COMPLETED,
				ConnectionApplicationLeadStatus.BACK_OFFICE
			]
		),
		custom=dict(short_description='Front Office Processing', admin=True, form=FrontOfficeForm),
	)
	def application_completed(self, *args, **kwargs):
		if kwargs.get("verified"):
			self.remarks = kwargs.get("remarks")


class ConnectionApplicationDocuments(models.Model):
	parent = models.ForeignKey(ConnectionApplication, on_delete=models.CASCADE, related_name='documents', null=True)
	type = models.CharField(max_length=25, choices=ConnectionApplicationDocumentsEnum.choices)
	link = models.URLField()
