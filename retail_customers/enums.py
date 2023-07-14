from django.db import models


class RetailCustomerDocTypeEnum(models.TextChoices):
	SHOP_PHOTO = 'SHOP_PHOTO', 'Shop Photo'
	PAN_PHOTO = 'PAN_PHOTO', 'PAN Photo'
	GST_PHOTO = 'GST_PHOTO', 'GST Photo'
	MCLICENSE_PHOTO = 'MCLICENSE_PHOTO', 'Mclicense Photo'

