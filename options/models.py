from django.db import models


class Banner(models.Model):
	disabled = models.BooleanField(default=False)
	created_on = models.DateTimeField(auto_now_add=True)
	updated_on = models.DateTimeField(auto_now=True)
	name = models.CharField(max_length=48)
	valid_from = models.DateTimeField()
	valid_upto = models.DateTimeField()
	content = models.TextField()
