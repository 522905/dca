"""
Django App Configuration for Ujjwala V3

This module configures the Ujjwala V3 Django application.
"""

from django.apps import AppConfig


class UjjwalaV3Config(AppConfig):
    """
    Django app configuration for Ujjwala V3.

    This app handles PMUY (Pradhan Mantri Ujjwala Yojana) V3 applications
    specifically designed for migrant households.
    """

    default_auto_field = 'django.db.models.BigAutoField'
    name = 'ujjwala_v3'
    verbose_name = 'Ujjwala V3 - PMUY for Migrant Households'

    def ready(self):
        """
        Method called when Django starts.

        Import signal handlers or perform other initialization tasks here.
        """
        # Import signals if you create any
        # import ujjwala_v3.signals
        pass
