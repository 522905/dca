from django.db import models


class TokenExcludeEnum(models.TextChoices):
	FEMALE = 'FEMALE', 'Female'
	MALE = 'MALE', 'Male'
