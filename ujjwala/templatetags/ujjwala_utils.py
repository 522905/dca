from django import template

from ujjwala.ujjwala_functions import is_member_of_disbursement_drive

register = template.Library()


@register.filter()
def has_disbursement_permission(user):
	return is_member_of_disbursement_drive(user)
