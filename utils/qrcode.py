
import pyqrcode
import fitz


def append_qr_code_to_legal_docs(content, file):
	input_file = file
	qr_code_file = generate_qr_code(content)

	# SV Arun Indane Signature Rectangle Co-ordinates
	image_rectangle = fitz.Rect(150, 535, 225, 585)

	# retrieve the first page of the PDF
	file_handle = fitz.open(input_file)
	first_page = file_handle[0]

	# add the image
	first_page.insertImage(image_rectangle, qr_code_file)
	file_handle.save()


def generate_base64_qr_code(content):
	url = pyqrcode.create(content)
	return url.png_as_base64_str()


def generate_qr_code(content, file_name):
	url = pyqrcode.create(content)

	url.png('{}.png'.format(file_name))
	return url


def append_qr_code(content):
	generate_qr_code(content)


def read_qr_code(doc_url):
	pass


