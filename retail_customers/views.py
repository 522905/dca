from django.shortcuts import render


def index(request):
    return render(request, 'retail_customers/index.html')
