import json
import logging

import django_rq
from django.http import HttpResponse
from django.views.decorators.csrf import csrf_exempt

from communication_log.jobs import interakt_webhook_job_processing, infobip_webhook_job_processing


@csrf_exempt
def interakt_webhook(request, is_async=True):
    logging.info(request.body)
    data = json.loads(request.body)
    django_rq.enqueue(interakt_webhook_job_processing, args=(data,), is_async=is_async)
    return HttpResponse(status=200)


@csrf_exempt
def infobip_webhook(request, is_async=True):
    data = json.loads(request.body)
    django_rq.enqueue(infobip_webhook_job_processing, args=(data,), is_async=is_async)
    return HttpResponse(status=200)
