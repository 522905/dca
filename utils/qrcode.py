import io

import pyqrcode
import fitz
import re

sv_date = re.compile('(\d{2}-\d{2}-\d{4})')
sv_document_number = re.compile('(7-\d{12})')


def generate_base64_qr_code(content):
	url = pyqrcode.create(content)
	return url.png_as_base64_str()


def generate_qr_code(content, file_name):
	url = pyqrcode.create(content)

	url.png('{}.png'.format(file_name))
	return url


def get_text_block(str_to_find, text_blocks):
	for text_block in text_blocks:
		for text in text_block:
			if str_to_find in str(text):
				return text_block


def get_text_block_exist(str_to_find, pdf_file_bytes):
	file_handle = fitz.open(stream=pdf_file_bytes, filetype="pdf")
	first_page = file_handle[0]

	return get_text_block(str_to_find, first_page.getTextBlocks())


def append_qr_code_to_sv(content, booking_id, pdf_bytes):
	# SV Arun Indane Signature Rectangle Co-ordinates
	# https://www.arungas.com/public/arun_indane_stamp_sign.png

	file_handle = fitz.open(stream=pdf_bytes, filetype="pdf")
	first_page = file_handle[0]

	text_block = get_text_block("PREVIOUS DOCUMENT OF CUSTOMER", first_page.getTextBlocks())

	# Draw Rectangle
	x, y = 62, text_block[1]
	image_rectangle = fitz.Rect(x, y, x + 236, y + 125)
	shape = first_page.newShape()
	shape.drawRect(image_rectangle)
	shape.finish(color=(1, 1, 1), fill=(1, 1, 1))
	shape.commit()

	x = 132
	with io.BytesIO() as file:
		image_rectangle = fitz.Rect(x, y, x + 130, y + 130)
		url = pyqrcode.create(content)
		url.png(file)
		# add the image
		first_page.insertImage(image_rectangle, stream=file)

	x = 60
	y = y + 45

	with io.BytesIO() as file:
		image_rectangle = fitz.Rect(x, y, x + 48, y + 48)
		url = pyqrcode.create(booking_id)
		url.png(file)
		# add the image
		first_page.insertImage(image_rectangle, stream=file)

	text_block = get_text_block("ON BEHALF OF INDIAN OIL CORP. LTD.", first_page.getTextBlocks())
	x, y = 150, text_block[1] - 39
	image_rectangle = fitz.Rect(x, y, x+75, y+50)
	first_page.insertImage(image_rectangle, "utils/arun_indane_stamp_sign.png")

	file_handle.deletePage(1)
	return file_handle.write()


def get_sv_date_and_doc_no(pdf_content):
	result = get_text_block_exist("Date", pdf_content)
	date_match = sv_date.search(result[4])
	doc_no_match = sv_document_number.search(result[4])
	return date_match.groups()[0] if len(date_match.groups()) > 0 else None, doc_no_match.groups()[0] if doc_no_match else None


if __name__ == '__main__':
	pdf_file = open("/tmp/sv_12368.pdf", "rb")
	pdf_file_bytes = io.BytesIO(pdf_file.read())
	bytes_stream = append_qr_code_to_sv("12334,SV", "2-1547851542", pdf_file_bytes)
	with open("/tmp/converted.pdf", "wb") as t:
		t.write(bytes_stream)

	pdf_file.close()