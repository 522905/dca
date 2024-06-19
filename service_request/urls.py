# Routers provide an easy way of automatically determining the URL conf.
from django.conf.urls import url
from django.urls import path

from service_request import views

urlpatterns = [
	path('dashboard/', views.DashboardView.as_view(), name="index"),
	path(
		'change-address-list-view/',
		views.ServiceRequestChangeAddressListView.as_view(),
		name="service_request_change_address_list"
	),
	path(
		'change-phone-number-list-view/',
		views.ServiceRequestChangePhoneNumberListView.as_view(),
		name="service_request_change_phone_number_list"
	),
	path(
		'change-others-list-view/',
		views.ServiceRequestOthersListView.as_view(),
		name="service_request_others_list"
	),
	url(
		'^service-request-view/(?P<pk>[^/.]+)/$',
		views.ServiceRequestView.as_view(),
		name="service_request_view"
	),
    path(
        'main-menu-grid-menu-view/',
        views.MainMenuGridMenuView.as_view(),
        name="main_menu_grid_menu_view"
    ),
	path(
        'main-menu-grid-menu-view/',
        views.MainMenuGridMenuView.as_view(),
        name="main_menu_grid_menu_view"
    ),
	path(
        'main-menu-grid-menu-view/',
        views.MainMenuGridMenuView.as_view(),
        name="main_menu_grid_menu_view"
    ),
]
