import base64
import io
import datetime
from functools import wraps

import magic
import requests
from django.conf import settings
from django.core.signing import Signer


from domestic_app.utils import get_minio_public_url


def move_file_to_minio_bucket(file_url, bucket_name, file_name):
	from connection_app.models import minio_client

	doc_file = requests.get(file_url)
	# Converting PDF file to Bytes IO Stream and Uploading To minio
	doc_file_bytes = io.BytesIO(doc_file.content)
	descriptor = magic.detect_from_content(doc_file_bytes.read(2048))
	file_extension = descriptor.mime_type.split('/')[-1]

	doc_file_name = "{}.{}".format(file_name, file_extension)

	doc_file_bytes.seek(0)

	minio_client.put_object(
		bucket_name,
		doc_file_name,
		doc_file_bytes, doc_file_bytes.getbuffer().nbytes,
		content_type=descriptor.mime_type
	)
	return get_minio_public_url(settings.MINIO_BUCKET_NAME, file_name)


def upload_file_to_minio_bucket(file, bucket_name, file_name, content_type=None):
	doc_file_bytes = io.BytesIO(file.content)
	return upload_file_type_obj_to_minio_bucket(doc_file_bytes, bucket_name, file_name, content_type)


def upload_file_type_obj_to_minio_bucket(file, bucket_name, file_name, content_type=None):
	from connection_app.models import minio_client

	if content_type:
		file_extension = content_type.split('/')[-1]
	else:
		descriptor = magic.detect_from_content(file.read(2048))
		file_extension = descriptor.mime_type.split('/')[-1]
		content_type = descriptor.mime_type

	doc_file_name = "{}.{}".format(file_name, file_extension)

	file.seek(0)

	minio_client.put_object(
		bucket_name,
		doc_file_name,
		file, file.getbuffer().nbytes,
		content_type=content_type
	)
	return get_minio_public_url(bucket_name, doc_file_name)


def old_address_to_description(function):
	@wraps(function)
	def wrapper(*args, **kwargs):
		kwargs['description'] = args[0].address_json or {'old_address': args[0].address}
		return function(*args, **kwargs)

	wrapper.__name__ = function.__name__
	wrapper.__doc__ = function.__doc__
	return wrapper


def old_walk_in_to_description(function):
	@wraps(function)
	def wrapper(*args, **kwargs):
		kwargs['description'] = "{} Walked In: {}".format(kwargs['description'], args[0].walk_in_date)
		return function(*args, **kwargs)

	wrapper.__name__ = function.__name__
	wrapper.__doc__ = function.__doc__
	return wrapper


def sign_data_base64(data):
	"""
	Sign Base64 Give Data
	param
		data
	"""
	signer = Signer()
	data_signed = signer.sign(data)
	data_signed_base64 = base64.urlsafe_b64encode(data_signed.encode('ascii'))
	data = data_signed_base64.decode('ascii')
	return data


def unsign_data_base64(data):
	"""
	Unsign Base64 Give Data
	param
		data
	"""
	signer = Signer()
	data = base64.urlsafe_b64decode(data)
	data = eval(signer.unsign(data.decode('ascii')))
	return data


def generate_tiny_url(link):
	"""
	Generate a tinyurl from a long url
	"""
	req = requests.get(
		"https://tinyurl.com/api-create.php",
		params={'url': link},
	)
	short_url = req.text

	short_url = short_url.replace("tinyurl.com/", "arungas.com/s?")
	return short_url
