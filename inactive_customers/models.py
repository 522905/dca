from django.db import models


# Create your models here.
class InactiveCustomer(models.Model):
	created_on = models.DateTimeField(auto_now_add=True)
	updated_on = models.DateTimeField(auto_now=True)
	distributor_code = models.CharField(max_length=10, null=True)
	distributor_name = models.CharField(max_length=25, null=True)
	consumer_id = models.CharField(max_length=25, null=True)
	consumer_number = models.CharField(max_length=12, null=True)
	consumer_name = models.CharField(max_length=50)
	order_type = models.CharField(max_length=10, null=True)
	inactive_type = models.CharField(max_length=15, default="DEACTIVATED")
