# settings.py

import os
from pathlib import Path

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

# --- ҚОЛДАНУШЫ МОДЕЛІ ---
AUTH_USER_MODEL = 'kundelik.User' # Сіздің кастомды User моделіңіз

# Quick-start development settings - unsuitable for production
# See https://docs.djangoproject.com/en/5.1/howto/deployment/checklist/

# SECURITY WARNING: keep the secret key used in production secret!
# Нақты жобада бұл кілтті құпия сақтаңыз (мысалы, environment variables арқылы)
SECRET_KEY = 'django-insecure-%@t#eom+=036p0@0=wu)-zlgs%z39_x#m91(j&odr$%mm)nm48'

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = True # Development режимінде True, Production-да False болуы керек

# ALLOWED_HOSTS = [] # Production режимінде домендеріңізді осында қосыңыз
# Development режимінде бос қалдыруға болады немесе ['127.0.0.1', 'localhost'] қосуға болады
ALLOWED_HOSTS = ['127.0.0.1', 'localhost'] # Мысал

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
    # Басқа қосымшалар (мысалы, формалардың стилі үшін):
    'widget_tweaks',
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

ROOT_URLCONF = 'strup.urls' # Жобаңыздың негізгі urls.py файлы

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        # Шаблондарды жобаның негізгі папкасындағы 'templates' ішінен іздеу
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True, # Қосымшалардың ішіндегі 'templates' папкаларын да іздеу
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request', # Шаблондарда request объектісіне қол жеткізу үшін
                'django.contrib.auth.context_processors.auth', # Шаблондарда user объектісіне қол жеткізу үшін
                'django.contrib.messages.context_processors.messages', # Хабарламаларды көрсету үшін
            ],
        },
    },
]

WSGI_APPLICATION = 'strup.wsgi.application' # Production үшін


# Database
# https://docs.djangoproject.com/en/5.1/ref/settings/#databases

# --- SQLite НҰСҚАСЫ (Егер MySQL орнына қолдансаңыз) ---
# DATABASES = {
#     'default': {
#         'ENGINE': 'django.db.backends.sqlite3',
#         'NAME': BASE_DIR / 'db.sqlite3',
#     }
# }
# --- ---

# --- MySQL НҰСҚАСЫ (Сіз бергендей) ---
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.mysql',
        'NAME': 'defaultdb',
        'USER': 'avnadmin',
        'PASSWORD': "AVNS_UdWfnHm5Skw9Y_mazPU",
        'HOST': 'whispr-whispr.l.aivencloud.com',
        'PORT': '20839',
        'OPTIONS': {
            'ssl': {
                # ca.pem файлының жобаның негізгі директориясында жатқанын тексеріңіз
                'ca': os.path.join(BASE_DIR, 'ca.pem')
            },
            # Бұл кейбір MySQL нұсқалары үшін қажет болуы мүмкін
            'init_command': "SET sql_mode='STRICT_TRANS_TABLES'"
        },
    }
}
# --- ---


# Password validation
# https://docs.djangoproject.com/en/5.1/ref/settings/#auth-password-validators

AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',},
]


# Internationalization
# https://docs.djangoproject.com/en/5.1/topics/i18n/

LANGUAGE_CODE = 'kk' # Немесе 'ru' немесе 'en-us'

TIME_ZONE = 'Asia/Almaty' # Қазақстан уақыты

USE_I18N = True # Халықаралықтандыруды қосу (аудармалар үшін)

USE_TZ = True # Уақыт белдеулерін ескеруді қосу


# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/5.1/howto/static-files/

STATIC_URL = 'static/' # Статикалық файлдарға URL префиксі

# Статикалық файлдарды іздейтін қосымша папкалар
STATICFILES_DIRS = [
    BASE_DIR / 'static', # Жобаның негізгі 'static' папкасы
    # os.path.join(BASE_DIR, 'static'), # Бұл да жұмыс істейді
]

# Production режимінде 'collectstatic' командасы статикалық файлдарды жинайтын жер
# STATIC_ROOT = BASE_DIR / 'staticfiles' # Әдетте development-та қажет емес

# Пайдаланушы кірмегенде қай URL-ға бағытталатынын көрсетеді (@login_required үшін)
LOGIN_URL = 'login' # Сіздің login view-іңіздің аты

# Пайдаланушы сәтті кіргеннен кейін қайда бағытталатынын көрсетеді (егер ?next болмаса)
# LOGIN_REDIRECT_URL = 'dashboard_schedule' # Мұны views.py ішіндегі redirect_user_based_on_role шешеді

# Пайдаланушы шыққаннан кейін қайда бағытталатынын көрсетеді
LOGOUT_REDIRECT_URL = 'home'

# Default primary key field type
# https://docs.djangoproject.com/en/5.1/ref/settings/#default-auto-field

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# --- !!! МЕДИА ФАЙЛДАР ҮШІН МАҢЫЗДЫ БАПТАУЛАР !!! ---
# Пайдаланушы жүктеген файлдарға (мысалы, аватарлар) қол жеткізуге арналған URL
MEDIA_URL = '/media/'

# Пайдаланушы жүктеген файлдар серверде физикалық түрде сақталатын папка
# BASE_DIR / 'media' - жобаның негізгі директориясында 'media' папкасын білдіреді
MEDIA_ROOT = BASE_DIR / 'media'
# --- --- --- --- --- --- --- --- --- --- --- --- --- --- ---