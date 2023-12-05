from django.db import models

from reference_data.enums import TokenExcludeEnum


class TokensExcluded(models.Model):
	name = models.CharField(max_length=256)
	gender = models.CharField(max_length=32, choices=TokenExcludeEnum.choices, default=TokenExcludeEnum.MALE)


class IFSCodeList(models.Model):
	old_ifscode = models.CharField(max_length=32)
	new_ifscode = models.CharField(max_length=32)
	main_branch = models.BooleanField(default=False)
