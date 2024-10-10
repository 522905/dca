import base64

import requests
from django.contrib.sites.models import Site
from django.core.signing import Signer
from django.urls import reverse

from utils.global_functions import generate_tiny_url


def get_signed_data(data):
	signer = Signer()
	data_signed = signer.sign(data)
	data_signed_base64 = base64.urlsafe_b64encode(data_signed.encode('ascii'))
	data = data_signed_base64.decode('ascii')
	return data


def create_tiny_html_template_url_for_sms(data, host=""):
	url = reverse('html_template_view', kwargs={'data': data})
	url = url[1:]
	# req = requests.get(
	# 	"https://tinyurl.com/api-create.php",
	# 	params={'url': "{}/{}".format(host if host else Site.objects.get_current().domain, url)},
	# )
	short_url = generate_tiny_url("{}/{}".format(host if host else Site.objects.get_current().domain, url))
	# req.raise_for_status()
	return short_url
