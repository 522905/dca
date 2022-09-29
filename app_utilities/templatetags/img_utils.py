from django import template

register = template.Library()


@register.filter()
def resize(url, fit_in_size):
	"""return f"http://dca.arungas.com:6988/unsafe/fit-in/{fit_in_size}/filters:format(webp)/{url}"""
	if not url:
		return ''
	return f"http://dca.arungas.com:6988/unsafe/fit-in/{fit_in_size}/{url}"
