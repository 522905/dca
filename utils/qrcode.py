import io

import pyqrcode
import fitz


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


def append_qr_code_to_sv(content, pdf_bytes):
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

	text_block = get_text_block("ON BEHALF OF INDIAN OIL CORP. LTD.", first_page.getTextBlocks())
	x, y = 150, text_block[1] - 39
	image_rectangle = fitz.Rect(x, y, x+75, y+50)
	first_page.insertImage(image_rectangle, "utils/arun_indane_stamp_sign.png")

	return file_handle.write()
