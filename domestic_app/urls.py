"""domestic_app URL Configuration

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/3.1/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.template.defaulttags import url
from django.urls import path, include
from django.contrib.staticfiles.urls import staticfiles_urlpatterns
from django.views.generic import RedirectView
from material.frontend import urls as frontend_urls

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api-auth/', include('rest_framework.urls')),
    path(r'connection-app/', include('connection_app.urls')),
    path(r'commlog/', include('communication_log.urls')),
    path(r'advanced_filters/', include('advanced_filters.urls')),
    path(r'app_utilities/', include('app_utilities.urls')),
    path(r'retail-customers/', include('retail_customers.urls')),
    path(r'sdms/', include('sdms.urls')),
    # path(r'', RedirectView.as_view(url='https://www.arungas.com/info', permanent=False)),
    # path(r'ujjwala/', include('ujjwala.urls')),
    # path(r'', RedirectView.as_view(url='/ujjwala/portal/application-status-search/', permanent=False)),
    path(r'', RedirectView.as_view(url='/ujjwala/portal/user_dashboard/', permanent=False)),
    path(r'', include(frontend_urls)),
]


urlpatterns += [
    path('django-rq/', include('django_rq.urls'))
]
