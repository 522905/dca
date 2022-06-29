def bridge_context(request):
	bridge_link = request.headers.get('Bridge-Location', '')

	return {
		'bridge_available': True if bridge_link else False,
		'bridge_link': bridge_link
	}
