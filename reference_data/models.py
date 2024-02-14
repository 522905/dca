from django.db import models
from django_comments.models import Comment
from django_comments_xtd.models import XtdComment

from reference_data.enums import TokenExcludeEnum, CommentTypeEnum


class TokensExcluded(models.Model):
	name = models.CharField(max_length=256)
	gender = models.CharField(max_length=32, choices=TokenExcludeEnum.choices, default=TokenExcludeEnum.MALE)


class IFSCodeList(models.Model):
	old_ifscode = models.CharField(max_length=32)
	new_ifscode = models.CharField(max_length=32)
	main_branch = models.BooleanField(default=False)


class RTGSList(models.Model):
	bank_name = models.CharField(max_length=255)
	ifscode = models.CharField(max_length=12)
	address = models.TextField()


class CommentX(XtdComment):
	comment_type = models.CharField(max_length=52, choices=CommentTypeEnum.choices, default=CommentTypeEnum.OTHERS)
