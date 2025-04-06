# kundelik/urls.py
from django.urls import path, include
from . import views
from django.contrib.auth import views as auth_views

urlpatterns = [
    path('', views.home, name='home'),
    path('about/', views.about, name='about_us'),
    path('recommendations/', views.recommendations, name='recommendations'),

    # --- Аутентификация и Регистрация ---
    path('register/', views.register, name='register'),
    path('login/', views.user_login, name='login'),
    path('logout/', views.user_logout, name='logout'),
    path('password_reset/', views.CustomPasswordResetView.as_view(), name='password_reset'),
    path('password_reset/done/', auth_views.PasswordResetDoneView.as_view(template_name='password_reset_done.html'), name='password_reset_done'),
    path('reset/<uidb64>/<token>/', auth_views.PasswordResetConfirmView.as_view(template_name = "password_reset_confirm.html"), name='password_reset_confirm'),
    path('reset/done/', auth_views.PasswordResetCompleteView.as_view(template_name = 'password_reset_complete.html'), name='password_reset_complete'),

    path('profile/', views.profile_page_view, name='profile_page'),

    # --- Раздел Дашборда ---
    path('dashboard/schedule/', views.dashboard_schedule_view, name='dashboard_schedule'),
    # --- НОВОВВЕДЕНИЕ: Раскомментировано для исправления ошибки NoReverseMatch ---
    # --- Убедитесь, что view-функция views.dashboard_grades_view существует в вашем views.py ---
    path('dashboard/grades/', views.dashboard_grades_view, name='dashboard_grades'),
    # path('dashboard/exams/', views.dashboard_exams_view, name='dashboard_exams'), # Оставлено закомментированным, если view нет
    # path('dashboard/contact-teacher/', views.dashboard_contact_teacher_view, name='dashboard_contact_teacher'), # Оставлено закомментированным, если view нет
    # path('dashboard/settings/', views.dashboard_settings_view, name='dashboard_settings'), # Оставлено закомментированным, если view нет
    path('dashboard/profile/', views.dashboard_profile_view, name='dashboard_profile'),

    # --- Прочие URLы вашего приложения ---
    path('schedule/', views.schedule, name='schedule'),
    path('daily_grades/', views.daily_grades, name='daily_grades'),
    path('exam_grades/', views.exam_grades, name='exam_grades'),
    path('daily_grades/<int:class_id>/', views.daily_grades, name='daily_grades_by_class'),
    path('exam_grades/<int:class_id>/', views.exam_grades, name='exam_grades_by_class'),
    path('add_person/', views.add_person, name='add_person'),
    path('add_school/', views.add_school, name='add_school'),
    path('add_class/', views.add_class, name='add_class'),
    path('add_subject/', views.add_subject, name='add_subject'),
    path('add_schedule/', views.add_schedule, name='add_schedule'),
    path('add_daily_grade/', views.add_daily_grade, name='add_daily_grade'),
    path('add_exam_grade/', views.add_exam_grade, name='add_exam_grade'),
    path('journal/', views.journal, name='journal'),
    path('teacher_schedule/', views.teacher_schedule, name='teacher_schedule'),
]