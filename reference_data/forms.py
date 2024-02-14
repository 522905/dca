from django import forms
from django.utils.translation import ugettext_lazy as _

from django_comments_xtd.forms import XtdCommentForm
from django_comments_xtd.models import TmpXtdComment

from reference_data.enums import CommentTypeEnum


class CommentXForm(XtdCommentForm):
    comment_type = forms.ChoiceField(
		label="Comment Type",
		required=True,
		help_text="Please select comment type",
		choices=CommentTypeEnum.choices
	)

    def get_comment_create_data(self):
        data = super(CommentXForm, self).get_comment_create_data()
        data.update({'comment_type': self.cleaned_data['comment_type']})
        return data
