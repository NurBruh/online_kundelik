# kundelik/apps.py

from django.apps import AppConfig

class KundelikConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'kundelik'
    verbose_name = 'Күнделік Басқару' # Қалауыңызша

    def ready(self):
        import kundelik.signals # Сигналдарды импорттау