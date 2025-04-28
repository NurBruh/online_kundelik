# settings.py

import os
from pathlib import Path

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

# --- ҚОЛДАНУШЫ МОДЕЛІ ---
AUTH_USER_MODEL = 'kundelik.User'

# SECURITY WARNING: keep the secret key used in production secret!
# Жақсырақ, бұл кілтті қоршаған орта айнымалысынан алу керек
SECRET_KEY = os.environ.get('DJANGO_SECRET_KEY', 'django-insecure-%@t#eom+=036p0@0=wu)-zlgs%z39_x#m91(j&odr$%mm)nm48') # Әдепкі мән қалдырылды

# SECURITY WARNING: don't run with debug turned on in production!
# Хостингте DEBUG = False болуы керек. Алайда, қазіргі қатені жөндеу үшін True қалдыруға болады.
# Production-ға шығарғанда False деп өзгертіңіз!
DEBUG = True # Production үшін False деп өзгертіңіз

# --- ★★★ Хостинг үшін МАҢЫЗДЫ өзгерістер ★★★ ---
ALLOWED_HOSTS = [
    'kundelik.whispr.ru',
    'www.kundelik.whispr.ru', # Егер www нұсқасы қолданылса
    '127.0.0.1',
    'localhost',
    # Басқа қажетті хосттарды осында қосыңыз (мысалы, IP адрес)
]

# CSRF үшін сенімді домендер
CSRF_TRUSTED_ORIGINS = [
    'https://kundelik.whispr.ru',
    'https://www.kundelik.whispr.ru', # Егер www нұсқасы қолданылса
]

# HTTPS үшін параметрлер (егер сайт https арқылы жұмыс істесе)
# Production-да бұлардың True болғаны өте маңызды!
CSRF_COOKIE_SECURE = True # Production үшін True
SESSION_COOKIE_SECURE = True # Production үшін True
# SECURE_SSL_REDIRECT = True # Веб-сервер бағыттамаса ғана True
# SECURE_HSTS_SECONDS = 31536000 # Бір жыл (optional)
# SECURE_HSTS_INCLUDE_SUBDOMAINS = True # (optional)
# SECURE_HSTS_PRELOAD = True # (optional)
# --- ★★★ Өзгерістер соңы ★★★ ---


# Application definition

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    # Сіздің қосымшаларыңыз:
    'kundelik',
    # Басқа қосымшалар:
    'widget_tweaks',
    # --- CKEDITOR ҚОСЫМШАЛАРЫ ---
    'ckeditor',             # Негізгі CKEditor қосымшасы
    'ckeditor_uploader',    # Файлдарды (суреттерді) жүктеуге арналған
    # --- ---
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

ROOT_URLCONF = 'strup.urls' # Жобаңыздың негізгі urls.py файлының атын тексеріңіз

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
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

WSGI_APPLICATION = 'strup.wsgi.application' # Жобаңыздың wsgi.py файлының атын тексеріңіз


# Database
# Дерекқор баптауларыңыз дұрыс екеніне көз жеткізіңіз
DATABASES = {
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


# Password validation
AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',},
]


# Internationalization
LANGUAGE_CODE = 'kk' # Немесе 'ru', 'en-us'
TIME_ZONE = 'Asia/Almaty'
USE_I18N = True
USE_TZ = True


# Static files (CSS, JavaScript, Images)
STATIC_URL = '/static/' # Басында және соңында '/' болуы маңызды
STATICFILES_DIRS = [ BASE_DIR / 'static', ]
# Production-да статикалық файлдарды жинау үшін STATIC_ROOT қажет болады
# STATIC_ROOT = BASE_DIR / 'staticfiles_collected'

# --- МЕДИА ФАЙЛДАР ---
MEDIA_URL = '/media/' # Басында және соңында '/' болуы маңызды
MEDIA_ROOT = BASE_DIR / 'media'
# --- ---

# Пайдаланушы кірмегенде қай URL-ға бағытталатыны
LOGIN_URL = 'login'
LOGOUT_REDIRECT_URL = 'home'

# Default primary key field type
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# ============================================
# --- CKEDITOR БАПТАУЛАРЫ ---
# ============================================

# CKEditor арқылы жүктелген файлдар MEDIA_ROOT ішіндегі осы папкаға салынады
CKEDITOR_UPLOAD_PATH = "uploads/"

# Суреттерді өңдеуге арналған бэкендтер (мысалы, thumbnail жасау үшін)
# Pillow орнатылған болуы керек (pip install Pillow)
# CKEDITOR_IMAGE_BACKEND = 'pillow' # Қажет болса қосыңыз

# CKEditor конфигурациялары (қалауыңызша өзгертуге болады)
CKEDITOR_CONFIGS = {
    'default': {
        'skin': 'moono-lisa', # Редактордың сыртқы көрінісі
        # 'skin': 'office2013',
        'toolbar_Basic': [
            ['Source', '-', 'Bold', 'Italic']
        ],
        'toolbar_YourCustomToolbarConfig': [
            {'name': 'document', 'items': ['Source', '-', 'Save', 'NewPage', 'Preview', 'Print', '-', 'Templates']},
            {'name': 'clipboard', 'items': ['Cut', 'Copy', 'Paste', 'PasteText', 'PasteFromWord', '-', 'Undo', 'Redo']},
            {'name': 'editing', 'items': ['Find', 'Replace', '-', 'SelectAll']},
            {'name': 'forms', 'items': ['Form', 'Checkbox', 'Radio', 'TextField', 'Textarea', 'Select', 'Button', 'ImageButton', 'HiddenField']},
            '/', # Жаңа қатар
            {'name': 'basicstyles', 'items': ['Bold', 'Italic', 'Underline', 'Strike', 'Subscript', 'Superscript', '-', 'RemoveFormat']},
            {'name': 'paragraph', 'items': ['NumberedList', 'BulletedList', '-', 'Outdent', 'Indent', '-', 'Blockquote', 'CreateDiv', '-', 'JustifyLeft', 'JustifyCenter', 'JustifyRight', 'JustifyBlock', '-', 'BidiLtr', 'BidiRtl', 'Language']},
            {'name': 'links', 'items': ['Link', 'Unlink', 'Anchor']},
            # Сурет жүктеу батырмасы ('Image' плагині)
            {'name': 'insert', 'items': ['Image', 'Flash', 'Table', 'HorizontalRule', 'Smiley', 'SpecialChar', 'PageBreak', 'Iframe']},
            '/', # Жаңа қатар
            {'name': 'styles', 'items': ['Styles', 'Format', 'Font', 'FontSize']},
            {'name': 'colors', 'items': ['TextColor', 'BGColor']},
            {'name': 'tools', 'items': ['Maximize', 'ShowBlocks']}
            # {'name': 'about', 'items': ['About']}
        ],
        'toolbar': 'YourCustomToolbarConfig',  # Жоғарыда анықталған toolbar-ды қолдану
        # 'toolbar': 'full', # Барлық батырмаларды көрсету
        # 'height': 291,
        # 'width': '100%', # Автоматты ен
        # 'filebrowserWindowWidth': 940,
        # 'filebrowserWindowHeight': 725,
        # Файл жүктеу URL-дарын қосу (ckeditor_uploader арқылы)
         'filebrowserUploadUrl': "/ckeditor/upload/",
         'filebrowserBrowseUrl': "/ckeditor/browse/",
        # Қосымша плагиндер (қажет болса)
        'extraPlugins': ','.join([
            'uploadimage', # Суретті базаға жүктеу үшін
            'div',
            'autolink',
            'autoembed',
            'embedsemantic',
            'autogrow',
            # 'devtools',
            'widget',
            'lineutils',
            'clipboard',
            'dialog',
            'dialogui',
            'elementspath'
        ]),
    }
}

# ============================================