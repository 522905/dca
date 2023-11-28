import io
import math
import os
import uuid

import magic
import requests
from PyPDF2 import PdfFileMerger

# THUMBOR_URL = "http://dca.arungas.com:6988/unsafe/fit-in/1520x2688/filters:quality(80)/"
from domestic_app.settings import THUMBOR_WEB_URL
from ujjwala.management.commands.ujjwala_file_worker import tus_client

THUMBOR_URL = "{}/unsafe/fit-in/{}x{}/filters:quality({})/"


def compress_file(file_url, target_size=500):
    response = requests.get("{}".format(file_url))
    print("File To Be Compressed: {} Original Size: {}".format(file_url, len(response.content)))

    original_file_content = response.content
    original_file_size = len(original_file_content) / 1024

    if original_file_size <= 500:
        return False, file_url, original_file_size

    resolution_x = 1520
    resolution_y = 2688
    quality = 80

    while True:
        response = requests.get("{}{}".format(
            THUMBOR_URL.format(THUMBOR_WEB_URL, resolution_x, resolution_y, quality),
            file_url)
        )

        compressed_file_content = response.content
        compressed_file_size = len(compressed_file_content) / 1024

        if response.status_code != 200:
            return False, file_url, '-2'

        if compressed_file_size <= target_size:
            break

        divisor = math.sqrt(int(compressed_file_size/target_size))
        resolution_x, resolution_y = int(resolution_x/divisor), int(resolution_y/divisor)

    doc_file_bytes = io.BytesIO(response.content)
    descriptor = magic.detect_from_content(doc_file_bytes.read(2048))
    file_extension = descriptor.mime_type.split('/')[-1]

    file_path = "/tmp/{}.{}".format(str(uuid.uuid4()), file_extension)
    file = open(file_path, "wb")
    file.write(response.content)
    file_size = str(round(len(response.content) / 1024))
    print("Compressed Size: {}".format(round(len(response.content))))
    file.close()
    try:
        uploader = tus_client.uploader(
            file_path=file_path,
            metadata={
                "filetype": descriptor.mime_type,
                "type": descriptor.mime_type
            })
        uploader.upload()
        os.remove(file_path)
        print("New Url: {}".format(uploader.url))
        del_req = requests.delete(file_url, headers={"Tus-Resumable": "1.0.0"})
        return True, uploader.url, file_size
    except Exception as e:
        print(e)
        return False, '', '-1'
