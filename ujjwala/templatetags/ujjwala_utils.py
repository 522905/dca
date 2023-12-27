from django import template

from ujjwala.ujjwala_functions import is_member_of_disbursement_drive, is_member_of_second_cylinder_delivery, \
	is_member_of_reviewer_group, can_resolve_service_request

register = template.Library()


@register.filter()
def has_disbursement_permission(user):
	return is_member_of_disbursement_drive(user)


@register.filter()
def has_second_delivery_permission(user):
	return is_member_of_second_cylinder_delivery(user)


@register.filter()
def has_review_permission(user):
	return is_member_of_reviewer_group(user)


@register.filter()
def filter_status(queryset, status):
	return queryset.filter(status=status)


@register.filter()
def has_service_request_resolve_permission(user):
	return can_resolve_service_request(user)
