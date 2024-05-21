from django import template

from domestic_app.settings import THUMBOR_WEB_URL, THUMBOR_LOCAL_URL

register = template.Library()


@register.filter()
def resize(url, fit_in_size):
	"""return f"http://dca.arungas.com:6988/unsafe/fit-in/{fit_in_size}/filters:format(webp)/{url}"""
	if not url:
		return ''
	w, h = fit_in_size.split("x")
	# return f"{THUMBOR_LOCAL_URL}/unsafe/fit-in/{w}x0:{h}x0/filters:format(jpeg)/{url}"
	return f"{THUMBOR_LOCAL_URL}/unsafe/{w}x0:{h}x0/filters:format(jpeg)/{url}"
