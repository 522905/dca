import io
import os
import uuid

import magic
import requests
from minio import Minio

from communication_log.jobs import move_files_to_minio_processing
from domestic_app import settings

minio_api_client = Minio(
	settings.MINIO_API_ENDPOINT,
	access_key=settings.MINIO_CREDENTIAL.get("access_key"),
	secret_key=settings.MINIO_CREDENTIAL.get("secret_key"),
	secure=False
)


def compress_connection_app_minio_docs():
	from connection_app.models import ConnectionApplication

	for connection_application in ConnectionApplication.objects.exclude(status='NOT_INTERESTED').filter(id__gte=2157).order_by("id"):
		print("Processing Application Id: {}".format(connection_application.id))
		move_files_to_minio_processing(connection_application.id)


	# from connection_app.models import ConnectionApplicationDocuments
	#
	# for doc in ConnectionApplicationDocuments.objects.all():
	# 	if not "tus." in doc.link:
	# 		print(doc.link)
	# 		file_name = doc.link.split("/")[-1]
	# 		file_extension = file_name.split(".")[:-1]
	# 		if file_extension == 'pdf':
	# 			continue
	# 		# file_name = "7200000022695529_uid_back.jpeg" # Test File Name
	#
	# 		# Test Bucket Name Domestic Connection
	# 		# bucket_name = "testfiles" # Test Bucket Name
	#
	# 		# Production Bucket Name Domestic Connection
	# 		bucket_name = settings.MINIO_BUCKET_NAME
	# 		minio_file_obj = minio_api_client.get_object(bucket_name, file_name)
	#
	# 		file_url = doc.link
	# 		# file = requests.get("{}".format(file_url))
	# 		#
	# 		print("File To Be Compressed: {} Original Size: {}".format(file_url, len(minio_file_obj.data)))
	# 		if len(minio_file_obj.data) <= 512000:
	# 			print("Valid File Size")
	# 			continue
	#
	# 		response = requests.get("{}{}".format(settings.THUMBOR_URL_INTERNAL, file_url))
	# 		if response.status_code != 200:
	# 			print("Invalid Status Code, Skipping")
	# 			continue
	#
	# 		doc_file_bytes = io.BytesIO(response.content)
	# 		descriptor = magic.detect_from_content(doc_file_bytes.read(2048))
	# 		# file_extension = descriptor.mime_type.split('/')[-1]
	#
	# 		doc_file_bytes.seek(0)
	#
	# 		minio_output_result = minio_api_client.put_object(
	# 			bucket_name,
	# 			file_name,
	# 			doc_file_bytes, doc_file_bytes.getbuffer().nbytes,
	# 			content_type=descriptor.mime_type
	# 		)
	#
	# 		print(minio_output_result)

	# for doc in ConnectionApplicationDocuments.objects.all():
	# 	if not "tus." in doc.link:
	# 		print(doc.link)
			# file_name = doc.link.split("/")[-1]

	# file_name = "7200000022695529_uid_back.jpeg"  # Test File Name
	# bucket_name = "testbucket"  # Test Bucket Name
	# # bucket_name = settings.MINIO_BUCKET_NAME # Production Bucket Name
	# minio_file_obj = minio_api_client.get_object(bucket_name, file_name)
	#
	# file_url = "https://files.dca.arungas.com/testbucket/7200000022695529_uid_back.jpeg"
	# # file = requests.get("{}".format(file_url))
	# #
	# print("File To Be Compressed: {} Original Size: {}".format(file_url, len(minio_file_obj.data)))
	# if len(minio_file_obj.data) <= 512000:
	# 	print("Valid File Size")
	#
	# response = requests.get("{}{}".format(settings.THUMBOR_URL_INTERNAL, file_url))
	# if response.status_code != 200:
	# 	print("Invalid Status Code, Skipping")
	#
	# doc_file_bytes = io.BytesIO(response.content)
	# descriptor = magic.detect_from_content(doc_file_bytes.read(2048))
	# # file_extension = descriptor.mime_type.split('/')[-1]
	#
	# doc_file_bytes.seek(0)
	#
	# minio_output_result = minio_api_client.put_object(
	# 	bucket_name,
	# 	file_name,
	# 	doc_file_bytes, doc_file_bytes.getbuffer().nbytes,
	# 	content_type=descriptor.mime_type
	# )

	# print(minio_output_result)
