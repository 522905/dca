import datetime
from collections import defaultdict

import pandas as pd
from django.contrib.auth.models import User
from django.http import JsonResponse
from django.urls import reverse
from django_currentuser.middleware import get_current_user
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from teams.models import SDMSUser
from . import models
from .enums import ConnectionApplicationLeadStatus
from .models import ConnectionApplication
from .serializer import SalesOrderSerializer
from .serializers import ConnectionApplicationSerializer


class ConnectionApplicationViewSet(viewsets.ModelViewSet):
    queryset = models.ConnectionApplication.objects.all()
    serializer_class = ConnectionApplicationSerializer

    @action(methods=['post'], detail=False, url_path='wf')
    def web_form(self, request, *args, **kwargs):
        request.PERFORM_SUBMIT = True
        user: User = get_current_user()
        if user and not user.is_anonymous:
            request.data['filled_by_id'] = user.id
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

    @action(methods=['get'], detail=False, url_path='get_last_date_of_sales_order_invoice')
    def get_last_date_of_sales_order_invoice(self, request, *args, **kwargs):
        from connection_app.models import SalesOrderInvoice

        last_record_date = '10-Mar-2023 12:00:00 AM'
        soi_obj: SalesOrderInvoice = SalesOrderInvoice.objects.all().order_by("-created_date").first()

        if soi_obj:
            last_record_date = soi_obj.invoice_date.strftime("%d-%b-%Y %I:%M:%S %p")

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
                    case_num=payment_profile.get('Case Num'),
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

    @action(methods=['post'], detail=False, url_path='toggle_sales_order_view')
    def toggle_sales_order_view(self, request, *args, **kwargs):
        from connection_app.models import SalesOrder

        sales_order_id = request.data.get('sales_order_id')
        value = request.data.get('value')

        so_obj = SalesOrder.objects.get(pk=sales_order_id)
        so_obj.hide_from_view = value
        so_obj.save()
        return Response(data='OK', status=200)

    @action(methods=['get'], detail=False, url_path='get_sales_order_for_delivery_boy')
    def get_sales_order_for_delivery_id(self, request, *args, **kwargs):
        from connection_app.models import SalesOrder

        delivery_boy_login = request.GET.get('delivery_boy_login')
        from_order_date = datetime.datetime.now() - datetime.timedelta(days=10)
        data = SalesOrderSerializer(
            SalesOrder.objects.exclude(
                order_status__in=['COMPLETED', 'Completed', 'Cancelled']
            ).filter(delivery_boy_login=delivery_boy_login, order_date__gte=from_order_date.date()), many=True).data
        return JsonResponse(data, safe=False)


class BookSalesOrderViewSet(viewsets.ViewSet):
    @action(methods=['get'], detail=False, url_path='get_book_sales_order_delivery_boy_login')
    def get_book_sales_order_delivery_boy_login(self, request, *args, **kwargs):
        from connection_app.models import BookSalesOrder
        import requests

        # Base URL of your Camunda instance
        CAMUNDA_URL = "https://camunda.dca.arungas.com/engine-rest"

        # Define the process definition key to filter on
        PROCESS_DEFINITION_KEY = "Process_book_sales_order"  # Replace with the actual key

        process_instances_url = f"{CAMUNDA_URL}/process-instance"

        response = requests.post(
            process_instances_url,
            json={
                    "variables": [
                        {
                            "name": "sdms_task",
                            "operator": "eq",
                            "value": "cancel_booked_sales_order"
                        },
                    ],
                    "processDefinitionKey": PROCESS_DEFINITION_KEY
                }
            )

        result = []

        if response.status_code == 200:
            pids = [i['id'] for i in response.json()]

            variable_instance_url = f"{CAMUNDA_URL}/variable-instance"
            response = requests.post(variable_instance_url, json={'processInstanceIdIn': pids})
            # Group variables by processInstanceId
            grouped_variables = defaultdict(list)

            for variable in response.json():
                instance_id = variable['processInstanceId']
                grouped_variables[instance_id].append({'name': variable['name'], 'value': variable['value']})

            # Output the grouped variables
            for instance_id, variables in grouped_variables.items():
                row = {'process_instance_id': instance_id}
                for var in variables:
                    row[var['name']] = var['value']
                print(row)
                result.append(row)

        # Convert list of dictionaries to DataFrame
        df = pd.DataFrame(result)

        # Get distinct delivery boy logins
        # unique_delivery_boy_logins = df['delivery_boy_login'].unique().tolist()
        unique_delivery_boy_logins = df['delivery_boy_login'].unique().tolist()

        data = []
        for unique_delivery_boy_login in unique_delivery_boy_logins:
            if unique_delivery_boy_login is None:
                continue

            # Due To Incomplete Data Currently Using Filter To Make Sure Code Should Not Crash
            sdmsuser_obj = SDMSUser.objects.filter(delivery_boy_login=unique_delivery_boy_login).first()

            if not sdmsuser_obj:
                print(f"Delivery Boy Login Not Found: {unique_delivery_boy_login}")
                continue

            data.append({'delivery_boy_login': unique_delivery_boy_login,
                         'delivery_boy_password': sdmsuser_obj.delivery_boy_password})

        return JsonResponse(data, safe=False)
