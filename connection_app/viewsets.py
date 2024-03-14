import datetime
import json

from django.http import JsonResponse
from django.urls import reverse
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from . import models
from .enums import ConnectionApplicationLeadStatus
from .models import ConnectionApplication, ConnectionApplicationDocuments
from .serializers import ConnectionApplicationSerializer


class ConnectionApplicationViewSet(viewsets.ModelViewSet):
    queryset = models.ConnectionApplication.objects.all()
    serializer_class = ConnectionApplicationSerializer

    @action(methods=['post'], detail=False, url_path='wf')
    def web_form(self, request, *args, **kwargs):
        request.PERFORM_SUBMIT = True
        return super().create(request, *args, **kwargs)

    @action(methods=['post'], detail=True, url_path='reupload_application')
    def reupload_application(self, request, *args, **kwargs):
        instance: ConnectionApplication = self.get_object()

        serializer = self.get_serializer(instance, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)

        for document in request.data.get('documents'):
            instance.documents.filter(type=document['type']).delete()
            instance.documents.create(**document)

        instance.reuploaded_by_customer()
        instance.save()

        return Response({'id': instance.id})

    @action(methods=['get'], detail=False, url_path='check_phone')
    def check_phone(self, request, *args, **kwargs):
        mobile = request.GET.get('mobile')

        application = ConnectionApplication.objects.exclude(
            status=ConnectionApplicationLeadStatus.NOT_INTERESTED
        ).filter(mobile=mobile)

        if application.exists():
            status_url = reverse('application_status', kwargs={'pk': application.first().pk})
            return JsonResponse({
                "status": False,
                "application_url": request.build_absolute_uri(status_url)
            })

        return JsonResponse({
            "status": True
        })

    def perform_create(self, serializer):
        application = serializer.save()
        if getattr(self.request, "PERFORM_SUBMIT", False):
            application.save()
            application.submit()
            application.save()
        return application

    @action(methods=['post'], detail=True, url_path='upload_installation')
    def upload_installation(self, request, *args, **kwargs):
        instance: ConnectionApplication = self.get_object()

        serializer = self.get_serializer(instance, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)

        for document in request.data.get('documents'):
            instance.documents.filter(type=document['type']).delete()
            instance.documents.create(**document)

        instance.upload_installation()
        instance.save()

        return Response({'id': instance.id})


class ConnectionApplicationAPIViewSet(viewsets.ViewSet):

    @action(methods=['get'], detail=False, url_path='get_last_date_of_record')
    def get_last_date_of_record(self, request, *args, **kwargs):
        from connection_app.models import PaymentProfile

        last_record_date = '14-Nov-2023 12:00:00 AM'
        pp_obj: PaymentProfile = PaymentProfile.objects.all().order_by("-created_date").first()

        if pp_obj:
            last_record_date = pp_obj.created_date.strftime("%d-%b-%Y %I:%M:%S %p")

        return JsonResponse(data={"last_record_date": last_record_date})

    @action(methods=['post'], detail=False, url_path='update_payment_profile_list')
    def update_payment_profile_list(self, request, *args, **kwargs):
        from connection_app.models import PaymentProfile

        data = request.data

        skipped_rows = []
        for payment_profile in data['data']:
            if PaymentProfile.objects.filter(case_num=payment_profile.get('case_num')).exists():
                skipped_rows.append(payment_profile)
            else:
                PaymentProfile.objects.create(
                    case_num=payment_profile.get('case_num'),
                    closed_data=datetime.datetime.strptime(payment_profile.get("Closed Date"),
                                                           "%d-%b-%Y %I:%M:%S %p") if payment_profile.get(
                        "Closed Date") else None,
                    created_date=datetime.datetime.strptime(payment_profile.get("Created Date"),
                                                            "%d-%b-%Y %I:%M:%S %p"),
                    name_as_per_bank=payment_profile.get("Name As Per Bank"),
                    name_as_on_relationship=payment_profile.get("Name As On Relationship"),
                    name_as_per_bank_response=payment_profile.get("Name As Per Bank Response"),
                    name_match=True if payment_profile.get("Name Match") == 'Y' else False,
                    distributor_code=payment_profile.get("Distributor Code"),
                    distributor_name=payment_profile.get("Distributor Name"),
                    comments=payment_profile.get("Comments"),
                    relationship_id=payment_profile.get("Relationship Id"),
                    payment_profile_id=payment_profile.get("Payment Profile Id"),
                    account_id=payment_profile.get("Account Id"),
                    status=payment_profile.get("Status"),
                    contact_id=payment_profile.get("Contact Id"),
                    profile_type=payment_profile.get("Type"),
                    pfms_payment_method=payment_profile.get("PFMS Payment Method"))

        return JsonResponse(data={"status": "Processed", "skipped_rows": skipped_rows})
