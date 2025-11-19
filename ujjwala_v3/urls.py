"""
URL Configuration for Ujjwala V3 API

This module defines the URL routing for the Ujjwala V3 REST API.
"""

from django.urls import path, include
from rest_framework.routers import DefaultRouter

from .viewsets import (
    UjjwalaV3ApplicationViewSet,
    UjjwalaV3AddressViewSet,
    UjjwalaV3FamilyMemberViewSet,
    UjjwalaV3DocumentViewSet,
    UjjwalaV2ToV3MigrationViewSet
)
from .views import public_application_form, application_success

# Create a router and register our viewsets
router = DefaultRouter()

router.register(
    r'applications',
    UjjwalaV3ApplicationViewSet,
    basename='ujjwala-v3-application'
)

router.register(
    r'addresses',
    UjjwalaV3AddressViewSet,
    basename='ujjwala-v3-address'
)

router.register(
    r'family-members',
    UjjwalaV3FamilyMemberViewSet,
    basename='ujjwala-v3-family-member'
)

router.register(
    r'documents',
    UjjwalaV3DocumentViewSet,
    basename='ujjwala-v3-document'
)

router.register(
    r'migration',
    UjjwalaV2ToV3MigrationViewSet,
    basename='ujjwala-v2-to-v3-migration'
)

# The API URLs are now determined automatically by the router
urlpatterns = [
    # Public application form URLs
    path('apply/', public_application_form, name='ujjwala_v3_public_form'),
    path('application-success/<str:application_number>/', application_success, name='ujjwala_v3_application_success'),

    # REST API URLs
    path('', include(router.urls)),
]

"""
API Endpoints:

Applications:
    GET    /api/ujjwala-v3/applications/                    - List all applications
    POST   /api/ujjwala-v3/applications/                    - Create new application
    GET    /api/ujjwala-v3/applications/{id}/               - Get application details
    PUT    /api/ujjwala-v3/applications/{id}/               - Update application
    PATCH  /api/ujjwala-v3/applications/{id}/               - Partial update
    DELETE /api/ujjwala-v3/applications/{id}/               - Delete application

    # Custom actions
    POST   /api/ujjwala-v3/applications/{id}/submit/        - Submit application
    POST   /api/ujjwala-v3/applications/{id}/mark_verified/ - Mark as verified
    POST   /api/ujjwala-v3/applications/{id}/approve/       - Approve application
    POST   /api/ujjwala-v3/applications/{id}/reject/        - Reject application
    POST   /api/ujjwala-v3/applications/{id}/issue_connection/ - Issue connection
    GET    /api/ujjwala-v3/applications/statistics/         - Get statistics

Addresses:
    GET    /api/ujjwala-v3/addresses/                       - List all addresses
    POST   /api/ujjwala-v3/addresses/                       - Create new address
    GET    /api/ujjwala-v3/addresses/{id}/                  - Get address details
    PUT    /api/ujjwala-v3/addresses/{id}/                  - Update address
    PATCH  /api/ujjwala-v3/addresses/{id}/                  - Partial update
    DELETE /api/ujjwala-v3/addresses/{id}/                  - Delete address

Family Members:
    GET    /api/ujjwala-v3/family-members/                  - List all family members
    POST   /api/ujjwala-v3/family-members/                  - Create new family member
    GET    /api/ujjwala-v3/family-members/{id}/             - Get family member details
    PUT    /api/ujjwala-v3/family-members/{id}/             - Update family member
    PATCH  /api/ujjwala-v3/family-members/{id}/             - Partial update
    DELETE /api/ujjwala-v3/family-members/{id}/             - Delete family member

Documents:
    GET    /api/ujjwala-v3/documents/                       - List all documents
    POST   /api/ujjwala-v3/documents/                       - Upload new document
    GET    /api/ujjwala-v3/documents/{id}/                  - Get document details
    PUT    /api/ujjwala-v3/documents/{id}/                  - Update document
    PATCH  /api/ujjwala-v3/documents/{id}/                  - Partial update
    DELETE /api/ujjwala-v3/documents/{id}/                  - Delete document

    # Custom actions
    POST   /api/ujjwala-v3/documents/{id}/verify/           - Verify document

Migration (V2 to V3):
    POST   /api/ujjwala-v3/migration/migrate-single/        - Migrate single V2 application
           Body: {"v2_app_id": 123, "skip_if_exists": true}

    POST   /api/ujjwala-v3/migration/migrate-batch/         - Batch migrate V2 applications
           Body: {"v2_app_ids": [123, 456], "limit": 100, "skip_if_exists": true}

    GET    /api/ujjwala-v3/migration/migration-stats/       - Get migration statistics
"""
