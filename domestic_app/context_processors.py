from domestic_app import settings


def bridge_context(request):
	bridge_link = request.headers.get('Bridge-Location', '')

	return {
		'bridge_available': True if bridge_link else False,
		'bridge_link': bridge_link
	}


def thumbor_compression_url(request):
	return {'THUMBOR_COMPRESSION_URL': settings.THUMBOR_URL}
