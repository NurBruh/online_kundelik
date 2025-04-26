# kundelik/urls.py

from django.urls import path
from . import views
from django.contrib.auth import views as auth_views

urlpatterns = [
    # --- Бұрынғы маршруттар ---
    path('', views.home, name='home'),
    path('about/', views.about, name='about_us'),
    path('recommendations/', views.recommendations, name='recommendations'),
    path('register/', views.register, name='register'),
    path('login/', views.user_login, name='login'),
    path('logout/', views.user_logout, name='logout'),
    path('password_reset/', views.CustomPasswordResetView.as_view(), name='password_reset'),
    path('password_reset/done/', auth_views.PasswordResetDoneView.as_view(template_name='password_reset_done.html'), name='password_reset_done'),
    path('reset/<uidb64>/<token>/', auth_views.PasswordResetConfirmView.as_view(template_name="password_reset_confirm.html"), name='password_reset_confirm'),
    path('reset/done/', auth_views.PasswordResetCompleteView.as_view(template_name='password_reset_complete.html'), name='password_reset_complete'),
    path('dashboard/profile/edit/', views.profile_edit, name='profile_edit'),
    path('dashboard/schedule/', views.dashboard_schedule_view, name='dashboard_schedule'),
    path('dashboard/grades/', views.dashboard_grades_view, name='dashboard_grades'),
    path('dashboard/profile/', views.dashboard_profile_view, name='dashboard_profile'),
    path('add_person/', views.add_person, name='add_person'),
    path('add_school/', views.add_school, name='add_school'),
    path('add_class/', views.add_class, name='add_class'),
    path('add_subject/', views.add_subject, name='add_subject'),
    path('add_schedule/', views.add_schedule, name='add_schedule'),
    path('add_daily_grade/', views.add_daily_grade, name='add_daily_grade'),
    path('add_exam_grade/', views.add_exam_grade, name='add_exam_grade'),
    path('profile/', views.profile_page_view, name='profile_page'),
    path('schedule/', views.schedule, name='schedule'),
    path('daily_grades/', views.daily_grades, name='daily_grades'),
    path('exam_grades/', views.exam_grades, name='exam_grades'),
    path('daily_grades/<int:class_id>/', views.daily_grades, name='daily_grades_by_class'),
    path('exam_grades/<int:class_id>/', views.exam_grades, name='exam_grades_by_class'),
    path('journal/', views.journal, name='journal'),
    path('teacher_schedule/', views.teacher_schedule, name='teacher_schedule'),

    # --- ЖАҢА МАРШРУТТАР: БЖБ/ТЖБ (ASSESSMENT) ---
    # Мұғалімге арналған
    path('assessment/create/', views.create_assessment, name='create_assessment'),
    path('assessment/my/', views.list_assessments, name='list_assessments'),
    path('assessment/<int:pk>/edit/', views.edit_assessment, name='edit_assessment'),
    path('assessment/<int:assessment_id>/submissions/', views.view_submissions, name='view_submissions'), # Тапсырулар тізімі
    path('submission/<int:submission_id>/grade/', views.grade_submission, name='grade_submission'), # Бағалау

    # Оқушыға арналған
    path('assessment/assigned/', views.list_assigned_assessments, name='list_assigned_assessments'), # Тағайындалғандар тізімі
    path('assessment/<int:pk>/take/', views.take_assessment, name='take_assessment'), # Тапсырманы өту
    path('submission/<int:pk>/result/', views.view_submission_result, name='view_submission_result'), # Нәтижені көру

]