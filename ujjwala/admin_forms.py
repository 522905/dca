from django import forms
from django.core.exceptions import ValidationError
from ujjwala.models import DisbursementDrive


class DisbursementDriveAdminForm(forms.ModelForm):
	class Meta:
		model = DisbursementDrive
		exclude = ['created_on', 'updated_on']

	def clean(self):
		data = self.cleaned_data

		if self.instance:
			instance_id = self.instance.id
		else:
			instance_id = None

		disbursement_drive_exist = DisbursementDrive.objects.filter(
			manager=data['manager'], status='ACTIVE'
		).exclude(id=instance_id).first()

		if disbursement_drive_exist:
			raise ValidationError(
				"Manager already exist in another active campaign id: {}".format(disbursement_drive_exist.id)
			)

		disbursement_drive_exist = DisbursementDrive.objects.filter(
			team_members__in=data['team_members'], status='ACTIVE'
		).exclude(id=instance_id).first()

		if disbursement_drive_exist:
			raise ValidationError(
				"Team Member(s) exist in another active campaign id: {}".format(disbursement_drive_exist.id)
			)

		return data
