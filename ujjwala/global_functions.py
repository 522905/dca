from functools import wraps

from django.contrib.auth import REDIRECT_FIELD_NAME
from django.contrib.auth.decorators import user_passes_test

from ujjwala.models import PreInspection


def login_required_if_mech_inspection(function, redirect_field_name=REDIRECT_FIELD_NAME, login_url=None):
	"""
	Decorator for views that checks that the user is logged in, redirecting
	to the log-in page if necessary.
	"""
	actual_decorator = user_passes_test(
		lambda u: u.is_authenticated,
		login_url=login_url,
		redirect_field_name=redirect_field_name
	)

	@wraps(function)
	def wrapper(*args, **kwargs):
		pi = PreInspection.objects.get(pk=kwargs.get('pk'))
		if pi.type == 'SELF':
			return function(*args, **kwargs)
		return actual_decorator(function)(*args, **kwargs)

	# wrapper.__name__ = function.__name__
	# wrapper.__doc__ = function.__doc__
	return wrapper

