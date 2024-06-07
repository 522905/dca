from django.apps import AppConfig
from material.frontend.apps import ModuleMixin


class ServiceRequestAppConfig(ModuleMixin, AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'service_request'
    verbose_name = 'Service Request'
    icon = '<i class="material-icons">settings_applications</i>'
