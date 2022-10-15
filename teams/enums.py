from django.db import models


class UserProfileTypeEnum(models.TextChoices):
	DELIVERY_BOY = 'DELIVERY_BOY', 'Delivery Boy'
	POS = 'POS', 'Point Of Sale'
	STAFF = 'STAFF', 'Staff'
	MANAGER = 'MANAGER', 'Manager'
	VOLUNTEER = 'VOLUNTEER', 'Volunteer'

