# kundelik/urls.py
from django.urls import path
from . import views

urlpatterns = [
    path('', views.home, name='home'),
    path('schedule/', views.schedule, name='schedule'),
    path('daily_grades/', views.daily_grades, name='daily_grades'),
    path('exam_grades/', views.exam_grades, name='exam_grades'),
    path('daily_grades/<int:class_id>/', views.daily_grades, name='daily_grades_by_class'), # Изменено
    path('exam_grades/<int:class_id>/', views.exam_grades, name='exam_grades_by_class'), # Изменено
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
    path('class_list/', views.class_list, name='class_list'),# добавлено
]