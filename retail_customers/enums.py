from django.db import models


class RetailCustomerDocTypeEnum(models.TextChoices):
	PAN_PHOTO = 'PAN_PHOTO', 'PAN Photo',
	GST_PHOTO = 'GST_PHOTO', 'GST Photo'
	MCLICENSE_PHOTO = 'MCLICENSE_PHOTO', 'Mclicense Photo'
