from django import template

from domestic_app.settings import THUMBOR_WEB_URL

register = template.Library()


@register.filter()
def resize(url, fit_in_size):
	"""return f"http://dca.arungas.com:6988/unsafe/fit-in/{fit_in_size}/filters:format(webp)/{url}"""
	if not url:
		return ''
	return f"{THUMBOR_WEB_URL}/unsafe/fit-in/{fit_in_size}/filters:format(jpeg)/{url}"
