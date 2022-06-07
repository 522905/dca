from django.db import models


class OtpChannels(models.TextChoices):
	SMS = 'SMS'
	VOICE = 'VOICE'
	WHATSAPP = 'WHATSAPP'
