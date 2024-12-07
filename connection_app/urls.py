# Routers provide an easy way of automatically determining the URL conf.
from django.conf.urls import url
from django.urls import path, include
from django.views.generic import RedirectView
from rest_framework import routers

from .vicidial.views import delivery_boy_signup_view, vicidial_webhook, check_access, AgentActionView, \
    CustomerProfileListView
from connection_app.viewsets import ConnectionApplicationViewSet, ConnectionApplicationAPIViewSet, BookSalesOrderViewSet
from . import views
from .views import UpdateDistributorLoginDetailsFormView, UpdateSDMSUserLoginPasswordFormView

router = routers.DefaultRouter()
router.register(r'connection-application', ConnectionApplicationViewSet)
router.register(r'connection-application-api', ConnectionApplicationAPIViewSet, basename="connection_application_api")
router.register(
    r'connection-application-sales-order', BookSalesOrderViewSet, basename="connection_application_sales_order"
)


urlpatterns = [
    path('', views.DashboardView.as_view(), name='index'),
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
    url(
        '^post-inspection/suraksha-pipe-update/(?P<pk>[^/.]+)/$',
        views.PostInspectionSurakshaPipeUpdateView.as_view(),
        name="post_inspection_suraksha_pipe_update"
    ),
    path(
        'customer-profile-search/',
        views.CustomerProfileSearchView.as_view(),
        name="customer_profile_search"
    ),
    url(
        '^customer-profile/(?P<pk>[^/.]+)/$',
        views.CustomerProfileView.as_view(),
        name="customer_profile"
    ),
    url(
        '^customer-profile-public/(?P<pk>[^/.]+)/$',
        views.CustomerProfilePublicView.as_view(),
        name="customer_profile_public"
    ),
    path(
        'generate-lead-form/',
        views.GenerateLeadFormView.as_view(),
        name="generate_lead_form"
    ),
    # path(
    #     'generate-non-customer-lead-form/',
    #     views.GenerateNonCustomerLeadFormView.as_view(),
    #     name="generate_non_customer_lead_form"
    # ),
    url(
        '^customer-profile/document-upload/(?P<pk>[^/.]+)/$',
        views.CustomerProfileDocumentUploadFormView.as_view(),
        name="customer_profile_document_upload"
    ),
    path(
        'sales-order-list/',
        # views.SalesOrderListView.as_view(),
        views.SalesOrderListView.as_view(),
        name="sales_order_list"
    ),
    path(
        'cancel-sales-order-list/',
        # views.SalesOrderListView.as_view(),
        views.CancelSalesOrderListView.as_view(),
        name="cancel_sales_order_list"
    ),
    path(
        'book-sales-order-list/',
        # views.SalesOrderListView.as_view(),
        views.BookSalesOrderListView.as_view(),
        name="book_sales_order_list"
    ),
    url(
        '^sales-order-view/(?P<pk>[^/.]+)/$',
        views.SalesOrderDetailFormView.as_view(),
        name="sales_order_detail_view"
    ),
    url(
        '^customer-profile-contacts/(?P<pk>[^/.]+)/$',
        views.CustomerProfileContactsView.as_view(),
        name="customer_profile_contacts"
    ),
    url(
        '^customer-profile-settings/(?P<pk>[^/.]+)/$',
        views.CustomerProfileSettingsView.as_view(),
        name="customer_profile_settings"
    ),
    path(
        'sales-order-portability/',
        views.SalesOrderPortabilityFormView.as_view(),
        name="sales_order_portability"
    ),
    path(
        'sales-order-portability-list/',
        views.SalesOrderPortabilityListView.as_view(),
        name="sales_order_portability_list"
    ),
    path(
        'sales-order-grid-menu-view/',
        views.SalesOrderGridMenuView.as_view(),
        name="sales_order_grid_menu_view"
    ),
    path(
        'admin-tools-grid-menu-view/',
        views.AdminToolsGridMenuView.as_view(),
        name="admin_tools_grid_menu_view"
    ),
    path(
      'inspection-grid-menu-view/',
      views.InspectionGridMenuView.as_view(),
      name="inspection_grid_menu_view"
    ),
    path(
      'customer-grid-menu-view/',
      views.CustomerGridMenuView.as_view(),
      name="customer_grid_menu_view"
    ),
    path(
        'sales-grid-menu-view/',
        views.SalesGridMenuView.as_view(),
        name="sales_grid_menu_view"
    ),
    # path(
    #     'sales-order-portability/',
    #     views.SalesOrderPortabilityFormView.as_view(),
    #     name="sales_order_portability"
    # ),
    path(
        'customer-profile-list/',
        CustomerProfileListView.as_view(),
        name="customer_profile_list"
    ),
    path(
        'upload-data/',
        views.UploadDataView.as_view(),
        name="upload_data"
    ),
    path(
        'import-data/',
        views.ImportDataView.as_view(),
        name="import_data"
    ),
    url(
        '^download-imported-file/(?P<pk>[^/.]+)/$',
        views.DownloadImportedFileView.as_view(),
        name="download_imported_file"
    ),
    path(
        'override-sale/',
        views.OverrideSaleView.as_view(),
        name="override_sale"
    ),
    path(
        'override-sale-list/',
        views.OverrideSaleListView.as_view(),
        name="override_sale_list"
    ),
    path(
        'promotional-sale/',
        views.PromotionalSaleView.as_view(),
        name="promotional_sale"
    ),
    path(
        'promotional-sale-list/',
        views.PromotionalSaleListView.as_view(),
        name="promotional_sale_list"
    ),
    path(
        'prize-allocation-list/',
        views.PrizeAllocationListView.as_view(),
        name="prize_allocation_list"
    ),
    path(
        'promotional-sale-allocation-prize/<str:parent>/<str:cylinder_type>/',
        views.PromotionalSalePrizeAllocationView.as_view(),
        name='promotional_sale_allocation_prize'
    ),
    url(
        '^prize-allocation/(?P<pk>[^/.]+)/$',
        views.PrizeAllocationView.as_view(),
        name="prize_allocation"
    ),
    path(
        'get-customer-details',
        views.get_customer_details,
        name='get_customer_details'
    ),
    path(
        'get-customer-details-from-consumer-id',
        views.get_customer_details_from_consumer_id,
        name='get_customer_details_from_consumer_id'
    ),
    url(
        '^service-request/change-address/(?P<pk>[^/.]+)/$',
        views.ChangeAddressView.as_view(),
        name="change_address"
    ),
    path(
        'vault-secret-autocomplete-view/',
        views.VaultSecretAutocompleteView.as_view(),
        name='vault_secret_autocomplete_view',
    ),
    path(
        'update-distributor-login-details/',
        UpdateDistributorLoginDetailsFormView.as_view(),
        name='update_distributor_login_details'
    ),
    path(
        'update-sdms-login-password/',
        UpdateSDMSUserLoginPasswordFormView.as_view(),
        name='update_sdms_login_password'
    ),
    # path('submit-delivery-boy-form/',
    #        views.submit_delivery_boy_form,
    #        name='submit_delivery_boy_form'
    # ),
    path('vicidial_webhook/',
         vicidial_webhook,
         name='vicidial_webhook'
         ),
    path('vicidial-signup/',
         delivery_boy_signup_view,
         name='vicidial-signup'
         ),
    path("check-access/",
         check_access,
         name="check_access"
         ),
    path('agent/action/<str:action>/',
         AgentActionView.as_view(),
         name='agent_action'
         ),
    path('load-data-list/',
         AgentActionView.as_view(),
         name='agent_action'
         ),
] + router.urls
