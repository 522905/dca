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
    UjjwalaV3AuditLogViewSet
)

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
    r'audit-logs',
    UjjwalaV3AuditLogViewSet,
    basename='ujjwala-v3-audit-log'
)

# The API URLs are now determined automatically by the router
urlpatterns = [
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

Audit Logs:
    GET    /api/ujjwala-v3/audit-logs/                      - List all audit logs
    GET    /api/ujjwala-v3/audit-logs/{id}/                 - Get audit log details
"""
