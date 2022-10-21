from functools import wraps

from django.contrib.auth import REDIRECT_FIELD_NAME
from django.contrib.auth.decorators import user_passes_test
from django.db import connection
from django.http import HttpResponse, HttpResponseRedirect
from django.shortcuts import redirect
from django.urls import reverse

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
		if pi.type == PreInspectionTypeEnum.MECHANIC and url_type == 'self':
			if request.user.is_authenticated:
				return redirect(
					reverse('ujjwala:pre_inspection_form_view',
					         args=(pi.pk, 'mech')) + '?{}'.format(request.GET.urlencode())
				)
			else:
				return redirect(
					reverse('ujjwala:pre_inspection_view_convert_to',
					        args=(pi.pk, 'self')) + '?{}'.format(request.GET.urlencode())
				)
				# return redirect(
				# 	'ujjwala:pre_inspection_view_convert_to', pk=pi.pk, convert_to='self'
				# )
		elif pi.type == PreInspectionTypeEnum.MECHANIC and url_type == 'mech':
			if request.user.is_authenticated:
				return actual_decorator(function)(request, *args, **kwargs)
			else:
				return redirect(
					reverse('ujjwala:pre_inspection_view_convert_to',
					        args=(pi.pk, 'self')) + '?{}'.format(request.GET.urlencode())
				)
				# return redirect(
				# 	'ujjwala:pre_inspection_view_convert_to', pk=pi.pk, convert_to='self'
				# )
		elif pi.type == PreInspectionTypeEnum.SELF and url_type == 'self':
			if not request.user.is_authenticated:
				return function(request, *args, **kwargs)
			else:
				return redirect(
					reverse('ujjwala:pre_inspection_view_convert_to',
					        args=(pi.pk, 'mech')) + '?{}'.format(request.GET.urlencode())
				)
				# return redirect(
				# 	'ujjwala:pre_inspection_view_convert_to', pk=pi.pk, convert_to='mech'
				# )
		elif pi.type == PreInspectionTypeEnum.SELF and url_type == 'mech':
			if request.user.is_authenticated:
				return redirect(
					reverse('ujjwala:pre_inspection_view_convert_to',
					        args=(pi.pk, 'mech')) + '?{}'.format(request.GET.urlencode())
				)
				# return redirect(
				# 	'ujjwala:pre_inspection_view_convert_to', pk=pi.pk, convert_to='mech'
				# )
			else:
				return redirect(
					reverse('ujjwala:pre_inspection_form_view',
					        args=(pi.pk, 'self')) + '?{}'.format(request.GET.urlencode())
				)
				# return redirect(
				# 	'ujjwala:pre_inspection_form_view', pk=pi.pk, type='self'
				# )
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
