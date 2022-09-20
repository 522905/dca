from django.db import models

from reference_data.enums import TokenExcludeEnum


class TokensExcluded(models.Model):
	name = models.CharField(max_length=256)
	gender = models.CharField(max_length=32, choices=TokenExcludeEnum.choices, default=TokenExcludeEnum.MALE)
