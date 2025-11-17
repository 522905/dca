"""
Django REST Framework ViewSets for Ujjwala V3 Application

This module provides comprehensive API endpoints for all Ujjwala V3 models.
"""

from django.db import transaction
from django.db.models import Q, Count, Prefetch
from django.utils import timezone
from django_filters import rest_framework as filters
from rest_framework import viewsets, status, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.filters import SearchFilter, OrderingFilter

from .models import (
    UjjwalaV3Application,
    UjjwalaV3Address,
    UjjwalaV3FamilyMember,
    UjjwalaV3Document,
    UjjwalaV3AuditLog
)
from .serializers import (
    UjjwalaV3ApplicationListSerializer,
    UjjwalaV3ApplicationDetailSerializer,
    UjjwalaV3ApplicationCreateUpdateSerializer,
    UjjwalaV3AddressSerializer,
    UjjwalaV3FamilyMemberSerializer,
    UjjwalaV3DocumentSerializer,
    UjjwalaV3AuditLogSerializer,
    ApplicationSubmitSerializer,
    ApplicationApprovalSerializer
)
from .enums import ApplicationStatus, AddressType, RelationToApplicant


class UjjwalaV3ApplicationFilter(filters.FilterSet):
    """Filter for applications."""

    applicant_name = filters.CharFilter(field_name='applicant_full_name', lookup_expr='icontains')
    mobile = filters.CharFilter(field_name='applicant_mobile', lookup_expr='exact')
    aadhaar = filters.CharFilter(field_name='applicant_aadhaar_number', lookup_expr='exact')
    status = filters.MultipleChoiceFilter(choices=ApplicationStatus.choices)
    caste = filters.MultipleChoiceFilter(field_name='caste')
    created_after = filters.DateTimeFilter(field_name='created_at', lookup_expr='gte')
    created_before = filters.DateTimeFilter(field_name='created_at', lookup_expr='lte')
    submitted_after = filters.DateTimeFilter(field_name='submitted_at', lookup_expr='gte')
    submitted_before = filters.DateTimeFilter(field_name='submitted_at', lookup_expr='lte')

    class Meta:
        model = UjjwalaV3Application
        fields = [
            'status', 'caste', 'lpg_connection_type', 'is_migrant',
            'family_doc_issuing_state'
        ]


class UjjwalaV3ApplicationViewSet(viewsets.ModelViewSet):
    """
    ViewSet for Ujjwala V3 Applications.

    Provides CRUD operations and custom actions for application lifecycle management.

    list: Get list of all applications
    retrieve: Get details of a specific application
    create: Create a new application
    update: Update an application
    partial_update: Partially update an application
    destroy: Delete an application (soft delete recommended in production)

    Custom Actions:
    - submit: Submit application for review
    - approve: Approve application
    - reject: Reject application
    - mark_verified: Mark application as verified
    - issue_connection: Issue LPG connection
    - statistics: Get application statistics
    """

    queryset = UjjwalaV3Application.objects.all()
    filterset_class = UjjwalaV3ApplicationFilter
    filter_backends = [filters.DjangoFilterBackend, SearchFilter, OrderingFilter]
    search_fields = ['applicant_full_name', 'applicant_mobile', 'application_number', 'applicant_aadhaar_number']
    ordering_fields = ['created_at', 'updated_at', 'submitted_at', 'applicant_full_name']
    ordering = ['-created_at']

    def get_serializer_class(self):
        """Return appropriate serializer based on action."""
        if self.action == 'list':
            return UjjwalaV3ApplicationListSerializer
        elif self.action in ['create', 'update', 'partial_update']:
            return UjjwalaV3ApplicationCreateUpdateSerializer
        elif self.action == 'submit':
            return ApplicationSubmitSerializer
        elif self.action in ['approve', 'reject']:
            return ApplicationApprovalSerializer
        return UjjwalaV3ApplicationDetailSerializer

    def get_queryset(self):
        """Optimize queryset with prefetch_related."""
        queryset = super().get_queryset()

        if self.action == 'retrieve':
            queryset = queryset.prefetch_related(
                'addresses',
                'family_members',
                'documents',
                'audit_logs'
            ).select_related(
                'submitted_by',
                'verified_by',
                'approved_by'
            )

        return queryset

    def perform_create(self, serializer):
        """Set created_by on creation."""
        serializer.save()
        # Create audit log
        self._create_audit_log(
            application=serializer.instance,
            action='CREATED',
            remarks='Application created'
        )

    def perform_update(self, serializer):
        """Create audit log on update."""
        serializer.save()
        self._create_audit_log(
            application=serializer.instance,
            action='UPDATED',
            remarks='Application updated'
        )

    @action(detail=True, methods=['post'])
    def submit(self, request, pk=None):
        """
        Submit application for review using FSM transition.

        Validates all requirements and moves application from DRAFT to SUBMITTED status.
        Uses FSM transition which performs comprehensive validation.
        """
        application = self.get_object()

        serializer = ApplicationSubmitSerializer(
            data=request.data,
            context={'application': application}
        )
        serializer.is_valid(raise_exception=True)

        try:
            # Use FSM transition (includes all validation)
            application.submit(user=request.user if request.user.is_authenticated else None)
            application.save()

            # Create audit log
            self._create_audit_log(
                application=application,
                action='SUBMITTED',
                remarks=serializer.validated_data.get('remarks', 'Application submitted via FSM transition')
            )
        except ValidationError as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )

        return Response(
            UjjwalaV3ApplicationDetailSerializer(application).data,
            status=status.HTTP_200_OK
        )

    @action(detail=True, methods=['post'])
    def start_verification(self, request, pk=None):
        """
        Start verification process using FSM transition.

        Moves application from SUBMITTED to UNDER_VERIFICATION status.
        """
        application = self.get_object()

        remarks = request.data.get('remarks', '')

        try:
            # Use FSM transition
            application.start_verification(user=request.user if request.user.is_authenticated else None)
            application.save()

            # Create audit log
            self._create_audit_log(
                application=application,
                action='VERIFICATION_STARTED',
                remarks=remarks or 'Verification process started via FSM transition'
            )
        except ValidationError as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )

        return Response(
            UjjwalaV3ApplicationDetailSerializer(application).data,
            status=status.HTTP_200_OK
        )

    @action(detail=True, methods=['post'])
    def approve(self, request, pk=None):
        """
        Approve application using FSM transition.

        Moves application from UNDER_VERIFICATION to APPROVED status.
        Validates that all verifications (Aadhaar, Bank, Address) are completed.
        """
        application = self.get_object()

        serializer = ApplicationApprovalSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        if serializer.validated_data['action'] != 'APPROVE':
            return Response(
                {'error': 'Invalid action. Use reject endpoint for rejection.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            # Use FSM transition (validates all verifications are complete)
            application.approve(user=request.user if request.user.is_authenticated else None)
            application.save()

            # Create audit log
            self._create_audit_log(
                application=application,
                action='APPROVED',
                remarks=serializer.validated_data.get('remarks', 'Application approved via FSM transition')
            )
        except ValidationError as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )

        return Response(
            UjjwalaV3ApplicationDetailSerializer(application).data,
            status=status.HTTP_200_OK
        )

    @action(detail=True, methods=['post'])
    def reject(self, request, pk=None):
        """
        Reject application using FSM transition.

        Moves application to REJECTED status with rejection reason.
        Can be called from SUBMITTED, UNDER_VERIFICATION, or VERIFICATION_FAILED states.
        """
        application = self.get_object()

        serializer = ApplicationApprovalSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        if serializer.validated_data['action'] != 'REJECT':
            return Response(
                {'error': 'Invalid action. Use approve endpoint for approval.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            # Use FSM transition (validates rejection_reason is provided)
            application.reject(
                reason=serializer.validated_data['rejection_reason'],
                user=request.user if request.user.is_authenticated else None
            )
            application.save()

            # Create audit log
            self._create_audit_log(
                application=application,
                action='REJECTED',
                remarks=serializer.validated_data.get('remarks', 'Application rejected via FSM transition')
            )
        except ValidationError as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )

        return Response(
            UjjwalaV3ApplicationDetailSerializer(application).data,
            status=status.HTTP_200_OK
        )

    @action(detail=True, methods=['post'])
    def issue_connection(self, request, pk=None):
        """
        Issue LPG connection using FSM transition.

        Final step - marks connection as issued.
        Only possible from APPROVED status.
        """
        application = self.get_object()

        remarks = request.data.get('remarks', '')

        try:
            # Use FSM transition
            application.issue_connection(user=request.user if request.user.is_authenticated else None)
            application.save()

        # Create audit log
        self._create_audit_log(
            application=application,
            action='CONNECTION_ISSUED',
            remarks=remarks or 'LPG connection issued'
        )

        return Response(
            UjjwalaV3ApplicationDetailSerializer(application).data,
            status=status.HTTP_200_OK
        )

    @action(detail=False, methods=['get'])
    def statistics(self, request):
        """
        Get application statistics.

        Returns counts by status, state, caste, etc.
        """
        stats = {
            'total': UjjwalaV3Application.objects.count(),
            'by_status': dict(
                UjjwalaV3Application.objects.values('status').annotate(count=Count('id')).values_list('status', 'count')
            ),
            'by_caste': dict(
                UjjwalaV3Application.objects.values('caste').annotate(count=Count('id')).values_list('caste', 'count')
            ),
            'by_lpg_type': dict(
                UjjwalaV3Application.objects.values('lpg_connection_type').annotate(count=Count('id')).values_list('lpg_connection_type', 'count')
            ),
            'submitted_today': UjjwalaV3Application.objects.filter(
                submitted_at__date=timezone.now().date()
            ).count(),
            'approved_this_month': UjjwalaV3Application.objects.filter(
                approved_at__month=timezone.now().month,
                approved_at__year=timezone.now().year
            ).count(),
        }

        return Response(stats)

    def _create_audit_log(self, application, action, remarks=''):
        """Helper method to create audit log."""
        UjjwalaV3AuditLog.objects.create(
            application=application,
            action=action,
            actor=self.request.user if self.request.user.is_authenticated else None,
            remarks=remarks,
            ip_address=self._get_client_ip()
        )

    def _get_client_ip(self):
        """Get client IP address."""
        x_forwarded_for = self.request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0]
        else:
            ip = self.request.META.get('REMOTE_ADDR')
        return ip


class UjjwalaV3AddressViewSet(viewsets.ModelViewSet):
    """
    ViewSet for Address management.

    Handles CRUD operations for application addresses.
    """

    queryset = UjjwalaV3Address.objects.all()
    serializer_class = UjjwalaV3AddressSerializer
    filterset_fields = ['application', 'address_type', 'state', 'district', 'pincode']
    search_fields = ['city_town', 'district', 'pincode', 'village_panchayat_area']
    ordering_fields = ['created_at', 'address_type']
    ordering = ['address_type', '-created_at']


class UjjwalaV3FamilyMemberViewSet(viewsets.ModelViewSet):
    """
    ViewSet for Family Member management.

    Handles CRUD operations for application family members.
    """

    queryset = UjjwalaV3FamilyMember.objects.all()
    serializer_class = UjjwalaV3FamilyMemberSerializer
    filterset_fields = ['application', 'relation_to_applicant', 'gender']
    search_fields = ['full_name', 'aadhaar_number']
    ordering_fields = ['created_at', 'dob', 'full_name']
    ordering = ['relation_to_applicant', '-created_at']


class UjjwalaV3DocumentViewSet(viewsets.ModelViewSet):
    """
    ViewSet for Document management.

    Handles file uploads and document management.
    """

    queryset = UjjwalaV3Document.objects.all()
    serializer_class = UjjwalaV3DocumentSerializer
    filterset_fields = ['application', 'family_member', 'address', 'doc_type', 'is_verified']
    search_fields = ['file_name', 'description']
    ordering_fields = ['created_at', 'doc_type', 'is_verified']
    ordering = ['-created_at']

    def perform_create(self, serializer):
        """Set uploaded_by on creation."""
        serializer.save(
            uploaded_by=self.request.user if self.request.user.is_authenticated else None
        )

    @action(detail=True, methods=['post'])
    def verify(self, request, pk=None):
        """
        Verify a document.

        Marks document as verified.
        """
        document = self.get_object()

        if document.is_verified:
            return Response(
                {'error': 'Document is already verified.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        remarks = request.data.get('remarks', '')

        document.is_verified = True
        document.verified_by = request.user if request.user.is_authenticated else None
        document.verified_at = timezone.now()
        document.save()

        # Create audit log for application
        UjjwalaV3AuditLog.objects.create(
            application=document.application,
            action='DOCUMENT_VERIFIED',
            actor=request.user if request.user.is_authenticated else None,
            remarks=f'{document.get_doc_type_display()} verified. {remarks}'
        )

        return Response(
            UjjwalaV3DocumentSerializer(document, context={'request': request}).data,
            status=status.HTTP_200_OK
        )


class UjjwalaV3AuditLogViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet for Audit Logs.

    Read-only access to audit trail.
    """

    queryset = UjjwalaV3AuditLog.objects.all()
    serializer_class = UjjwalaV3AuditLogSerializer
    filterset_fields = ['application', 'action', 'actor']
    search_fields = ['action', 'remarks']
    ordering_fields = ['created_at', 'action']
    ordering = ['-created_at']
