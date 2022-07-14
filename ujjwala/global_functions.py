from functools import wraps

from django.contrib.auth import REDIRECT_FIELD_NAME
from django.contrib.auth.decorators import user_passes_test
from django.db import connection
from django.http import HttpResponse

from ujjwala.enums import PreInspectionTypeEnum
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
	def wrapper(request, *args, **kwargs):
		url_type = kwargs.get('type')
		pi = PreInspection.objects.get(pk=kwargs.get('pk'))
		if pi.type == PreInspectionTypeEnum.SELF and url_type == 'self' and request.user.is_authenticated == False:
			return function(request, *args, **kwargs)
		elif pi.type == PreInspectionTypeEnum.MECHANIC and url_type == 'mech':
			return actual_decorator(function)(request, *args, **kwargs)
		return HttpResponse("Not Valid For Mechanic Inspection")
	# wrapper.__name__ = function.__name__
	# wrapper.__doc__ = function.__doc__
	return wrapper


def get_sdms_mismatched_records(upto_date):

	with connection.cursor() as cursor:
		query = """select sscr.consumer_id from sdms_sdmscustomerrecord sscr 
		                where sscr.consumer_id not in (
		                select consumer_id from ujjwala_ujjwalav2application uua where consumer_id is not null
		                ) and sscr.kyc_date <='{}';""".format(upto_date)
		cursor.execute(query)
		result = cursor.fetchall()
	return result
