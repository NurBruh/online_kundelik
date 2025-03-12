# kundelik/urls.py
from django.urls import path, include, reverse_lazy
from . import views
from django.contrib.auth import views as auth_views #Импортируем

from .views import about

urlpatterns = [
    path('', views.home, name='home'),
    path('schedule/', views.schedule, name='schedule'),
    path('daily_grades/', views.daily_grades, name='daily_grades'),
    path('exam_grades/', views.exam_grades, name='exam_grades'),
    path('daily_grades/<int:class_id>/', views.daily_grades, name='daily_grades_by_class'),
    path('exam_grades/<int:class_id>/', views.exam_grades, name='exam_grades_by_class'),
    path('add_person/', views.add_person, name='add_person'),
    path('add_school/', views.add_school, name='add_school'),
    path('add_class/', views.add_class, name='add_class'),
    path('add_subject/', views.add_subject, name='add_subject'),
    path('register/', views.register, name='register'),
    path('login/', views.user_login, name='login'),
    path('logout/', views.user_logout, name='logout'),
    path('add_schedule/', views.add_schedule, name='add_schedule'),
    path('add_daily_grade/', views.add_daily_grade, name='add_daily_grade'),
    path('add_exam_grade/', views.add_exam_grade, name='add_exam_grade'),
    path('class_list/', views.class_list, name='class_list'),
    path('journal/', views.journal, name='journal'),
    path('teacher_schedule/', views.teacher_schedule, name='teacher_schedule'),
    path('about us/', views.about, name='about'),

    path('recommendations/', views.recommendations, name='recommendations'),
    path('password_reset/', views.CustomPasswordResetView.as_view(), name='password_reset'), #Для сброса пароля
    path('password_reset/done/', auth_views.PasswordResetDoneView.as_view(template_name='password_reset_done.html'), name='password_reset_done'),#Для сброса пароля
    path('reset/<uidb64>/<token>/', auth_views.PasswordResetConfirmView.as_view(template_name = "password_reset_confirm.html"), name='password_reset_confirm'),#Для сброса пароля
    path('reset/done/', auth_views.PasswordResetCompleteView.as_view(template_name = 'password_reset_complete.html'), name='password_reset_complete'),#Для сброса пароля
]