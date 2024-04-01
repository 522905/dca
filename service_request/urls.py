# Routers provide an easy way of automatically determining the URL conf.
from django.conf.urls import url
from django.urls import path

from service_request import views

urlpatterns = [
	path('portal/pre-inspection/', views.ServiceRequestListView.as_view(), name="index"),
	url(
		'^service-request-view/(?P<pk>[^/.]+)/$',
		views.ServiceRequestView.as_view(),
		name="service_request_view"
	),
]
