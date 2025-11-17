# Integration Guide for Ujjwala V3

This document provides step-by-step instructions to integrate the Ujjwala V3 app into your Django project.

## Step 1: Add to INSTALLED_APPS

In `domestic_app/settings.py`:

```python
INSTALLED_APPS = [
    # ... existing apps
    'rest_framework',
    'django_filters',

    # Add ujjwala_v3
    'ujjwala_v3.apps.UjjwalaV3Config',
]
```

## Step 2: Configure REST Framework

Add/update REST Framework settings in `domestic_app/settings.py`:

```python
REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'rest_framework.authentication.SessionAuthentication',
        'rest_framework.authentication.TokenAuthentication',
    ],
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.IsAuthenticated',
    ],
    'DEFAULT_FILTER_BACKENDS': [
        'django_filters.rest_framework.DjangoFilterBackend',
        'rest_framework.filters.SearchFilter',
        'rest_framework.filters.OrderingFilter',
    ],
    'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.PageNumberPagination',
    'PAGE_SIZE': 50,
}
```

## Step 3: Add URLs

In `domestic_app/urls.py`:

```python
from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path('admin/', admin.site.urls),

    # ... existing URL patterns

    # Add Ujjwala V3 API
    path('api/ujjwala-v3/', include('ujjwala_v3.urls')),

    # Optional: Add DRF browsable API authentication
    path('api-auth/', include('rest_framework.urls')),
]
```

## Step 4: Configure Media Files (for document uploads)

In `domestic_app/settings.py`:

```python
import os

# Media files (for file uploads)
MEDIA_URL = '/media/'
MEDIA_ROOT = os.path.join(BASE_DIR, 'media')
```

In `domestic_app/urls.py` (for development):

```python
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    # ... your URL patterns
]

# Serve media files in development
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
```

## Step 5: Run Migrations

```bash
# Create migrations
python manage.py makemigrations ujjwala_v3

# Apply migrations
python manage.py migrate ujjwala_v3
```

## Step 6: Create Superuser (if needed)

```bash
python manage.py createsuperuser
```

## Step 7: Test the Installation

### Test Django Admin

1. Start the development server:
   ```bash
   python manage.py runserver
   ```

2. Navigate to: `http://localhost:8000/admin/`

3. Login with your superuser credentials

4. You should see "Ujjwala V3 - PMUY for Migrant Households" section with:
   - Ujjwala V3 Applications
   - Ujjwala V3 Addresses
   - Ujjwala V3 Audit Logs
   - Ujjwala V3 Documents
   - Ujjwala V3 Family Members

### Test REST API

1. Navigate to: `http://localhost:8000/api/ujjwala-v3/`

2. You should see the DRF browsable API root with links to:
   - applications
   - addresses
   - family-members
   - documents
   - audit-logs

3. Test creating an application via API or admin

## Optional: Production Settings

### Use PostgreSQL (recommended)

```python
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': 'ujjwala_v3_db',
        'USER': 'your_db_user',
        'PASSWORD': 'your_db_password',
        'HOST': 'localhost',
        'PORT': '5432',
    }
}
```

### Use S3/MinIO for File Storage

Install:
```bash
pip install django-storages boto3
```

Configure in settings:
```python
# For AWS S3
DEFAULT_FILE_STORAGE = 'storages.backends.s3boto3.S3Boto3Storage'
AWS_ACCESS_KEY_ID = 'your-access-key'
AWS_SECRET_ACCESS_KEY = 'your-secret-key'
AWS_STORAGE_BUCKET_NAME = 'ujjwala-v3-documents'
AWS_S3_REGION_NAME = 'ap-south-1'

# For MinIO
DEFAULT_FILE_STORAGE = 'storages.backends.s3boto3.S3Boto3Storage'
AWS_ACCESS_KEY_ID = 'minio-access-key'
AWS_SECRET_ACCESS_KEY = 'minio-secret-key'
AWS_STORAGE_BUCKET_NAME = 'ujjwala-v3'
AWS_S3_ENDPOINT_URL = 'http://minio-server:9000'
```

### Configure Logging

```python
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'handlers': {
        'file': {
            'level': 'INFO',
            'class': 'logging.FileHandler',
            'filename': 'ujjwala_v3.log',
        },
    },
    'loggers': {
        'ujjwala_v3': {
            'handlers': ['file'],
            'level': 'INFO',
            'propagate': True,
        },
    },
}
```

## Troubleshooting

### Issue: Migrations not detected

**Solution:**
```bash
python manage.py makemigrations ujjwala_v3 --empty
# Then manually write migration or let Django auto-generate
```

### Issue: File uploads not working

**Solution:**
- Ensure MEDIA_ROOT and MEDIA_URL are configured
- Check file permissions on MEDIA_ROOT directory
- For production, use S3/MinIO/CDN

### Issue: API returns 403 Forbidden

**Solution:**
- Check DRF authentication settings
- Ensure user is logged in
- Disable authentication for testing:
  ```python
  REST_FRAMEWORK = {
      'DEFAULT_PERMISSION_CLASSES': [
          'rest_framework.permissions.AllowAny',  # WARNING: Only for testing!
      ],
  }
  ```

### Issue: Database constraint errors

**Solution:**
- Ensure all hard requirements are met:
  - applicant_gender = 'F'
  - is_migrant = True
  - applicant age >= 18

## Next Steps

1. **Customize Permissions**: Add custom permission classes for different user roles
2. **Add Celery Tasks**: For async processing (e.g., document verification, notifications)
3. **Add Signals**: For post-save operations (e.g., send WhatsApp messages)
4. **Add Tests**: Write comprehensive tests for models, serializers, viewsets
5. **Add Documentation**: Use drf-yasg or drf-spectacular for OpenAPI docs

## Support

For issues or questions, refer to:
- README.md in the ujjwala_v3 directory
- Django documentation: https://docs.djangoproject.com/
- DRF documentation: https://www.django-rest-framework.org/
