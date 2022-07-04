import io
from functools import wraps

import magic
import requests
from django.conf import settings

from connection_app.models import minio_client
from domestic_app.utils import get_minio_public_url


def move_file_to_minio_bucket(file_url, bucket_name, file_name):
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


def upload_file_to_minio_bucket(file, bucket_name, file_name):
    doc_file_bytes = io.BytesIO(file.content)
    return upload_file_type_obj_to_minio_bucket(doc_file_bytes, bucket_name, file_name)


def upload_file_type_obj_to_minio_bucket(file, bucket_name, file_name):
    descriptor = magic.detect_from_content(file.read(2048))
    file_extension = descriptor.mime_type.split('/')[-1]

    doc_file_name = "{}.{}".format(file_name, file_extension)

    file.seek(0)

    minio_client.put_object(
        bucket_name,
        doc_file_name,
        file, file.getbuffer().nbytes,
        content_type=descriptor.mime_type
    )
    return get_minio_public_url(bucket_name, doc_file_name)


def old_address_to_description(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        kwargs['description'] = args[0].address_json or {'old_address': args[0].address}
        return func(*args, **kwargs)

    wrapper.__name__ = func.__name__
    wrapper.__doc__ = func.__doc__
    return wrapper
