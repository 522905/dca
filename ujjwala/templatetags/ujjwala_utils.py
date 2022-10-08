from django import template

from ujjwala.ujjwala_functions import is_member_of_disbursement_drive, is_member_of_second_cylinder_delivery

register = template.Library()


@register.filter()
def has_disbursement_permission(user):
	return is_member_of_disbursement_drive(user)


@register.filter()
def has_second_delivery_permission(user):
	return is_member_of_second_cylinder_delivery(user)
