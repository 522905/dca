INSTALLED_APPS = [
    'daphne',
    'channels',
]


os.environ["DJANGO_ALLOW_ASYNC_UNSAFE"] = "true"

MIDDLEWARE = [
     'django.middleware.security.SecurityMiddleware',
     'django.contrib.sessions.middleware.SessionMiddleware',
     'corsheaders.middleware.CorsMiddleware',
     'django.middleware.common.CommonMiddleware',
     'django.middleware.csrf.CsrfViewMiddleware',
     'django.contrib.auth.middleware.AuthenticationMiddleware',
     'django.contrib.messages.middleware.MessageMiddleware',
     'django.middleware.clickjacking.XFrameOptionsMiddleware',
     'corsheaders.middleware.CorsMiddleware',
     'django.middleware.common.CommonMiddleware',
     'django_currentuser.middleware.ThreadLocalUserMiddleware',
     'django.contrib.sites.middleware.CurrentSiteMiddleware'
     'django.contrib.sites.middleware.CurrentSiteMiddleware',
]

ASGI_APPLICATION = "domestic_app.asgi.application"


CHANNEL_LAYERS = {
    'default': {
        'BACKEND': 'channels_redis.core.RedisChannelLayer',
        'CONFIG': {
            "hosts": [('192.168.171.65', 56379)],  # Ensure Redis server is running at this address
        },
},
}


