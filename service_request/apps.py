from django.apps import AppConfig
from material.frontend.apps import ModuleMixin


class ServiceRequestAppConfig(ModuleMixin, AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'service_request'
    icon = '<i class="material-icons">flight_takeoff</i>'
