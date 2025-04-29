# kundelik/signals.py

from django.contrib.auth.signals import user_logged_in
from django.dispatch import receiver
from .models import ActivityLog, User # User моделін импорттау қажет болуы мүмкін

@receiver(user_logged_in)
def log_user_login(sender, request, user, **kwargs):
    """Пайдаланушы жүйеге кіргенде ActivityLog жазбасын жасайды."""
    # Тек оқушылардың кіруін тіркеу (қажет болса)
    if getattr(user, 'role', None) == 'student':
        try:
            ActivityLog.objects.create(user=user, activity_type='LOGIN')
            print(f"Login activity logged for student: {user.username}") # Отладка үшін
        except Exception as e:
            # Қате болған жағдайда журналға жазу (міндетті емес)
            print(f"Error logging user login for {user.username}: {e}")