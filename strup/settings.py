# settings.py

import os
from pathlib import Path

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

# ҚОЛДАНУШЫ МОДЕЛІ
AUTH_USER_MODEL = 'kundelik.User'

# ҚҰПИЯ КІЛТ (PRODUCTION ҮШІН ҚОРШАҒАН ОРТА АЙНЫМАЛЫСЫНАН АЛЫҢЫЗ)
SECRET_KEY = 'django-insecure-%@t#eom+=036p0@0=wu)-zlgs%z39_x#m91(j&odr$%mm)nm48'

# DEBUG РЕЖИМІ (PRODUCTION ҮШІН FALSE)
DEBUG = True

ALLOWED_HOSTS = [
    'kundelik.whispr.ru',
    'www.kundelik.whispr.ru',
    '127.0.0.1',
    'localhost',
]

CSRF_TRUSTED_ORIGINS = [
    'https://kundelik.whispr.ru',
    'https://www.kundelik.whispr.ru',
    'http://127.0.0.1:8000', # Әзірлеу үшін HTTP
    'http://localhost:8000', # Әзірлеу үшін HTTP
]

# HTTPS үшін параметрлер (DEBUG=False болғанда ғана іске қосылады)
if not DEBUG:
    CSRF_COOKIE_SECURE = True
    SESSION_COOKIE_SECURE = True
    # ... басқа SECURE_ параметрлері
else:
    CSRF_COOKIE_SECURE = False
    SESSION_COOKIE_SECURE = False

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'kundelik',
    'widget_tweaks',
    'ckeditor',
    'ckeditor_uploader',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'strup.urls'

# ==============================================================================
# ШАБЛОНДАР (TEMPLATES) - ОСЫ БӨЛІК МАҢЫЗДЫ
# ==============================================================================
TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        # Django-ға шаблон файлдарын іздейтін негізгі директориялар:
        'DIRS': [
            BASE_DIR / 'templates', # 1. Жобаның негізгі templates папкасы
        ],
        # Қосымшалардың ішіндегі 'templates' папкаларын да іздеу:
        'APP_DIRS': True,        # 2. Мысалы, kundelik/templates/
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]
# ==============================================================================

WSGI_APPLICATION = 'strup.wsgi.application'

DATABASES = { # Сіздің дерекқор баптауларыңыз
    'default': {
        'ENGINE': 'django.db.backends.mysql',
        'NAME': 'defaultdb',
        'USER': 'avnadmin',
        'PASSWORD': "AVNS_UdWfnHm5Skw9Y_mazPU",
        'HOST': 'whispr-whispr.l.aivencloud.com',
        'PORT': '20839',
        'OPTIONS': {
            'ssl': { 'ca': os.path.join(BASE_DIR, 'ca.pem') },
            'init_command': "SET sql_mode='STRICT_TRANS_TABLES'"
        },
    }
}

AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',},
]

LANGUAGE_CODE = 'kk'
TIME_ZONE = 'Asia/Almaty'
USE_I18N = True
USE_L10N = True
USE_TZ = True

STATIC_URL = '/static/'
STATICFILES_DIRS = [ BASE_DIR / 'static', ]
STATIC_ROOT = BASE_DIR / 'staticfiles_collected' # Production үшін

MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

LOGIN_URL = 'login'
LOGIN_REDIRECT_URL = 'home'
LOGOUT_REDIRECT_URL = 'home'

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

CKEDITOR_UPLOAD_PATH = "uploads/"
CKEDITOR_IMAGE_BACKEND = 'pillow'
CKEDITOR_ALLOW_NONIMAGE_FILES = False
CKEDITOR_CONFIGS = { # Сіздің CKEditor конфигурацияңыз
    'default': {
        'skin': 'moono-lisa',
        'toolbar_YourCustomToolbarConfig': [
            {'name': 'document', 'items': ['Source', '-', 'Templates']},
            {'name': 'clipboard', 'items': ['Cut', 'Copy', 'Paste', 'PasteText', 'PasteFromWord', '-', 'Undo', 'Redo']},
            {'name': 'editing', 'items': ['Find', 'Replace', '-', 'SelectAll']},
            '/',
            {'name': 'basicstyles', 'items': ['Bold', 'Italic', 'Underline', 'Strike', 'Subscript', 'Superscript', '-', 'RemoveFormat']},
            {'name': 'paragraph', 'items': ['NumberedList', 'BulletedList', '-', 'Outdent', 'Indent', '-', 'Blockquote', 'CreateDiv', '-', 'JustifyLeft', 'JustifyCenter', 'JustifyRight', 'JustifyBlock']},
            {'name': 'links', 'items': ['Link', 'Unlink', 'Anchor']},
            {'name': 'insert', 'items': ['Image', 'Table', 'HorizontalRule', 'Smiley', 'SpecialChar']},
            '/',
            {'name': 'styles', 'items': ['Styles', 'Format', 'Font', 'FontSize']},
            {'name': 'colors', 'items': ['TextColor', 'BGColor']},
            {'name': 'tools', 'items': ['Maximize', 'ShowBlocks']}
        ],
        'toolbar': 'YourCustomToolbarConfig',
        'width': '100%',
        'filebrowserUploadUrl': "/ckeditor/upload/",
        'filebrowserBrowseUrl': "/ckeditor/browse/",
        'extraPlugins': ','.join([
            'uploadimage', 'div', 'autolink', 'autoembed', 'embedsemantic',
            'autogrow', 'widget', 'lineutils', 'clipboard', 'dialog',
            'dialogui', 'elementspath'
        ]),
    }
}