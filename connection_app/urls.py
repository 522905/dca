# Routers provide an easy way of automatically determining the URL conf.
from django.conf.urls import url
from django.urls import path, include
from rest_framework import routers

from connection_app.viewsets import ConnectionApplicationViewSet, ConnectionApplicationAPIViewSet
from . import views

router = routers.DefaultRouter()
router.register(r'connection-application', ConnectionApplicationViewSet)
router.register(r'connection-application-api', ConnectionApplicationAPIViewSet, basename="connection_application_api")


urlpatterns = [
    path('', views.index),
    path('web-form/', views.web_form_view),
    path('connection-application/start/', views.index),
    url(
        '^connection-application/(?P<pk>[^/.]+)/status/$',
        views.ApplicationStatusView.as_view(),
        name="application_status"
    ),
    url(
        '^connection-application/(?P<pk>[^/.]+)/installation/$',
        views.ApplicationInstallationView.as_view(),
        name="installation_start"
    ),
    url(
        '^connection-application/(?P<pk>[^/.]+)/reupload/$',
        views.ApplicationReuploadView.as_view(),
        name="application_reupload"
    ),
    url(
        '^installation-gleam-start/$',
        views.installation_upload_process_gleam_entry_gate,
        name="application_installation_gleam_start"
    ),
    url(
        '^installation-gleam-complete/$',
        views.installation_upload_process_gleam_entry_gate_completed,
        name="application_installation_gleam_complete"
    ),
    path('post-inspection/', views.PostInspectionListView.as_view(), name="post_inspection_list"),
    path('post-inspection/start/', views.PostInspectionStartFormView.as_view(), name="post_inspection_start"),
    url('^post-inspection/(?P<pk>[^/.]+)/$', views.PostInspectionView.as_view(), name="post_inspection_form_view"),
    url(
        '^post-inspection/address-update/(?P<pk>[^/.]+)/$',
        views.PostInspectionAddressUpdateView.as_view(),
        name="post_inspection_address_update"
    ),
    url(
        '^post-inspection/kitchen-photo-update/(?P<pk>[^/.]+)/$',
        views.PostInspectionKitchenPhotoUpdateView.as_view(),
        name="post_inspection_kitchen_photo_update"
    ),
    url(
        '^post-inspection/main-gate-photo-update/(?P<pk>[^/.]+)/$',
        views.PostInspectionMainGatePhotoUpdateView.as_view(),
        name="post_inspection_main_gate_photo_update"
    ),
    url(
        '^post-inspection/uid-photo-update/(?P<pk>[^/.]+)/$',
        views.PostInspectionUIDPhotoUpdateView.as_view(),
        name="post_inspection_uid_photo_update"
    ),
    url(
        '^post-inspection/profile-photo-update/(?P<pk>[^/.]+)/$',
        views.PostInspectionProfilePhotoUpdateView.as_view(),
        name="post_inspection_profile_photo_update"
    ),
    path('', include(router.urls)),
]
