# kundelik/urls.py (Этот файл НЕ нужно изменять для исправления reverse('admin:index'))

from django.urls import path
from . import views
from django.contrib.auth import views as auth_views

urlpatterns = [
    # --- Общедоступные страницы ---
    path('', views.home, name='home'), # Главная страница (с редиректом для залогиненных)
    path('about/', views.about, name='about_us'),
    path('recommendations/', views.recommendations, name='recommendations'),

    # --- Аутентификация, Регистрация, Сброс пароля ---
    path('register/', views.register, name='register'), # Регистрация (с авто-логином и редиректом по роли)
    path('login/', views.user_login, name='login'),     # Вход (с редиректом по роли)
    path('logout/', views.user_logout, name='logout'),
    path('password_reset/', views.CustomPasswordResetView.as_view(), name='password_reset'),
    path('password_reset/done/', auth_views.PasswordResetDoneView.as_view(template_name='password_reset_done.html'), name='password_reset_done'),
    path('reset/<uidb64>/<token>/', auth_views.PasswordResetConfirmView.as_view(template_name="password_reset_confirm.html"), name='password_reset_confirm'),
    path('reset/done/', auth_views.PasswordResetCompleteView.as_view(template_name='password_reset_complete.html'), name='password_reset_complete'),

    # --- Основной раздел "Дашборд" (Личный кабинет) ---
    # Эти view теперь обрабатывают разные роли внутри себя
    path('dashboard/profile/edit/', views.profile_edit, name='profile_edit'), # <-- Вот эта строка исправляет ошибку
    path('dashboard/schedule/', views.dashboard_schedule_view, name='dashboard_schedule'), # Основная страница расписания для всех ролей
    path('dashboard/grades/', views.dashboard_grades_view, name='dashboard_grades'),       # Основная страница оценок (студент/родитель)
    path('dashboard/profile/', views.dashboard_profile_view, name='dashboard_profile'),     # Профиль пользователя в дашборде

    # --- Закомментированные URL дашборда (функционал пока не реализован или является редиректом) ---
    # path('dashboard/exams/', views.dashboard_exams_view, name='dashboard_exams'),
    # path('dashboard/contact-teacher/', views.dashboard_contact_teacher_view, name='dashboard_contact_teacher'),
    # path('dashboard/settings/', views.dashboard_settings_view, name='dashboard_settings'),

    # --- URL для добавления данных (доступ ограничен ролями через декораторы в views.py) ---
    path('add_person/', views.add_person, name='add_person'),
    path('add_school/', views.add_school, name='add_school'),
    path('add_class/', views.add_class, name='add_class'),
    path('add_subject/', views.add_subject, name='add_subject'),
    path('add_schedule/', views.add_schedule, name='add_schedule'),
    path('add_daily_grade/', views.add_daily_grade, name='add_daily_grade'),
    path('add_exam_grade/', views.add_exam_grade, name='add_exam_grade'),

    # --- Устаревшие/Перенаправляемые URL (оставлены для совместимости) ---
    path('profile/', views.profile_page_view, name='profile_page'), # Редирект на 'dashboard_profile'
    path('schedule/', views.schedule, name='schedule'), # Редирект на 'dashboard_schedule'
    path('daily_grades/', views.daily_grades, name='daily_grades'), # Редирект на 'dashboard_grades'
    path('exam_grades/', views.exam_grades, name='exam_grades'), # Редирект на 'dashboard_grades'
    path('daily_grades/<int:class_id>/', views.daily_grades, name='daily_grades_by_class'), # Редирект на 'dashboard_grades'
    path('exam_grades/<int:class_id>/', views.exam_grades, name='exam_grades_by_class'),   # Редирект на 'dashboard_grades'
    path('journal/', views.journal, name='journal'), # Редирект в зависимости от роли
    path('teacher_schedule/', views.teacher_schedule, name='teacher_schedule'), # Редирект на 'dashboard_schedule'
]