from django.db import models


class TokenExcludeEnum(models.TextChoices):
	FEMALE = 'FEMALE', 'Female'
	MALE = 'MALE', 'Male'


class CommentTypeEnum(models.TextChoices):
	ADDRESS_CHANGE = 'ADDRESS_CHANGE', 'Address Change'
	OTHERS = 'OTHERS', 'Others'


class ProductUnitEnum(models.TextChoices):
	NOS = 'NOS', 'Nos'


class SDMSServiceRequestEnum(models.TextChoices):
	ADDRESS_UPDATE = 'ADDRESS UPDATE', 'Address Update'
