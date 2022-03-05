from django.shortcuts import render

def index(request):
    return render(request, 'connection_app/index.html')

def Status(request):
    return render(request, 'connection_app/status.html')

