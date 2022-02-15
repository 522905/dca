import json

from django.http import HttpResponse
from django.shortcuts import render


def index(request):
    return render(request, 'connection_app/index.html')


def interakt_webhook(request):
    data = json.loads(request.body)
    data.get('type')
    return HttpResponse(status=200)
