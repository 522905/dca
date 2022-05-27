from django.conf import settings


def get_minio_public_url(bucket_name, file_name):
	file_url = "{}/{}/{}".format(settings.MINIO_PUBLIC_URL, bucket_name, file_name)
	return file_url
