from django.db import models

from retail_customers.enums import RetailCustomerDocTypeEnum


class RetailCustomer(models.Model):
	created_on = models.DateTimeField(auto_now_add=True)
	updated_on = models.DateTimeField(auto_now=True)
	shop_name = models.CharField(max_length=128)
	shop_type = models.CharField(max_length=128)
	mobile_number = models.CharField(max_length=10)
	whatsapp_number = models.CharField(max_length=10)
	referral_code = models.CharField(max_length=16, null=True, blank=True)


class RetailCustomerAddress(models.Model):
	parent = models.ForeignKey(RetailCustomer, on_delete=models.CASCADE, related_name='addresses', null=True)
	created_on = models.DateTimeField(auto_now_add=True)
	updated_on = models.DateTimeField(auto_now=True)
	title = models.CharField(max_length=128, null=True)
	floor = models.CharField(max_length=32)
	street_no = models.IntegerField()
	landmark = models.CharField(max_length=128)
	locality = models.CharField(max_length=128)
	city = models.CharField(max_length=48)
	pincode = models.CharField(max_length=10)
	latitude = models.CharField(max_length=32, null=True, blank=True)
	longitude = models.CharField(max_length=32, null=True, blank=True)
	accuracy = models.CharField(max_length=24, null=True, blank=True)


class RetailCustomerDocuments(models.Model):
	parent = models.ForeignKey(RetailCustomer, on_delete=models.CASCADE, related_name='documents', null=True)
	type = models.CharField(max_length=25, choices=RetailCustomerDocTypeEnum.choices)
	link = models.URLField()
