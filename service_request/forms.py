from django import forms


class ServiceRequestReviewForm(forms.Form):
	review_status = forms.ChoiceField(
		label="Select Review Status ?",
		required=True,
		help_text="",
		choices=[
			('', '-- Select Review Status --'),
			('ACCEPTED', 'Accepted'),
			('REJECTED', 'Rejected')
		]
	)
	rejected_reason = forms.CharField(
		widget=forms.TextInput, max_length=255, label='Rejected Reason', required=False
	)
	description = forms.CharField(
		widget=forms.Textarea, label='Remarks', required=False
	)

	def clean(self):
		data = super(ServiceRequestReviewForm, self).clean()
		if data.get('review_status', '') == 'REJECTED' and not data['rejected_reason']:
			raise forms.ValidationError("Please enter a reason for rejection.")
		data.update({
			'description': '{} - {}: {}'.format(
				data.get('review_status'), data.get('rejected_reason'), data.get('description', '')
			)
		})
		return data
