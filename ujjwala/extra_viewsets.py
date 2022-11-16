import datetime
import random

import django_rq
import pytz
import requests
from django.http import JsonResponse, HttpResponse
from rest_framework import viewsets
from rest_framework.decorators import action

from ujjwala.models import UjjwalaV2Application
from ujjwala.ujjwala_functions import time_in_range, send_ujjwala_application_whatsapp_link_v2, send_offer_whatsapp_link
from ujjwala.vici_functions import update_lead_in_out1005_campaign, update_lead_in_ujjwala_welcome, \
    update_lead_in_ujjwala_enquiry_list


class UjjwalaApplicationExtraViewSet(viewsets.ViewSet):

    @action(methods=['get'], detail=False, url_path='inbound_call_manage')
    def inbound_call_manage(self, request, *args, **kwargs):
        contact_mobile = request.GET.get('contact_mobile')
        application = UjjwalaV2Application.objects.filter(contact_mobile=contact_mobile).first()

        if application:
            if application.status not in ('APPLICATION_REJECTED', 'OMC_REJECTED'):
                update_lead_in_out1005_campaign(contact_mobile)
        else:
            # scheduler = django_rq.get_scheduler('default')
            inbound_call_user_id = 87
            # start_time = datetime.time(8, 0, 0)
            # end_time = datetime.time(19, 30, 0)

            # current_time = datetime.datetime.now(pytz.timezone('Asia/Kolkata')).time()

            # if time_in_range(
            #         start_time, end_time, current_time
            # ):
            #     date = datetime.date(1, 1, 1)
            #     datetime1 = datetime.datetime.combine(date, end_time)
            #     datetime2 = datetime.datetime.combine(date, current_time)
            #
            #     time_difference = datetime1 - datetime2
            #
            #     time_difference = time_difference + datetime.timedelta(seconds=random.randint(0, 60 * 60))
            #     scheduler.enqueue_in(
            #         time_difference,
            #         send_ujjwala_application_whatsapp_link_v2,
            #         contact_mobile=contact_mobile, user_id=inbound_call_user_id
            #     )
            # else:
            #     send_ujjwala_application_whatsapp_link_v2(contact_mobile, user_id=inbound_call_user_id)
            # To be removed for scheduled message delivery
            send_ujjwala_application_whatsapp_link_v2(contact_mobile, user_id=inbound_call_user_id)
            update_lead_in_ujjwala_welcome(contact_mobile)
            # update_lead_in_ujjwala_enquiry_list(contact_mobile)
            update_lead_in_out1005_campaign(contact_mobile)
        return HttpResponse("ok")

    @action(methods=['get'], detail=False, url_path='offer_call_manage')
    def offer_call_manage(self, request, *args, **kwargs):
        contact_mobile = request.GET.get('contact_mobile')
        update_lead_in_out1005_campaign(contact_mobile)
        send_offer_whatsapp_link(contact_mobile)
        return HttpResponse("ok")
