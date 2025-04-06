# kundelik/views.py

from datetime import date, timedelta
from collections import defaultdict
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib.auth import views as auth_views, login, logout
from django.contrib import messages
from django.urls import reverse_lazy
from django import forms
from django.utils import timezone # Используется в dashboard_schedule_view
from django.http import HttpResponseForbidden, Http404

from .models import (
    User, UserProfile, School, Class, Subject,
    Schedule, DailyGrade, ExamGrade
)
from .forms import (
    UserRegistrationForm, CustomAuthenticationForm, SchoolForm,
    ClassForm, SubjectForm, ScheduleForm, DailyGradeForm, ExamGradeForm
)

# ==================================
# ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ (Пример)
# ==================================

def get_current_term():
    """
    Примерная функция для определения текущей четверти.
    В реальном приложении логика может быть сложнее (из настроек, календаря).
    """
    today = date.today()
    # Очень упрощенный пример:
    if 9 <= today.month <= 10: return 1
    if 11 <= today.month <= 12: return 2
    if 1 <= today.month <= 3: return 3
    if 4 <= today.month <= 5: return 4
    return None # Межсезонье или лето

# ==================================
# ОБЩИЕ СТРАНИЦЫ
# ==================================

def home(request):
    return render(request, 'home.html')

def about(request):
    return render(request, 'about_us.html')

def recommendations(request):
    return render(request, 'recommendations.html')

# ==================================
# АУТЕНТИФИКАЦИЯ, РЕГИСТРАЦИЯ, ПАРОЛЬ
# ==================================

def register(request):
    if request.user.is_authenticated:
        return redirect('home')
    if request.method == 'POST':
        form = UserRegistrationForm(request.POST)
        if form.is_valid():
            user = form.save()
            try:
                # Создаем профиль сразу после создания пользователя
                UserProfile.objects.create(user=user)
            except Exception as e:
                 print(f"Error creating UserProfile for {user.username}: {e}")
                 messages.warning(request, "Тіркелу сәтті, бірақ профильді құруда қате пайда болды. Әкімшілікке хабарласыңыз.")
            messages.success(request, "Тіркелу сәтті аяқталды! Енді жүйеге кіре аласыз.")
            return redirect('login')
        else:
            messages.error(request, "Тіркелу кезінде қателер пайда болды. Форманы тексеріңіз.")
    else:
        form = UserRegistrationForm()
    return render(request, 'register.html', {'form': form})

def user_login(request):
    if request.user.is_authenticated:
         return redirect('dashboard_schedule') # Перенаправляем сразу в дашборд
    if request.method == 'POST':
        # Передаем request в форму для обработки CSRF и других контекстных данных
        form = CustomAuthenticationForm(request, data=request.POST)
        if form.is_valid():
            user = form.get_user()
            login(request, user)
            messages.success(request, f"Қош келдіңіз, {user.first_name or user.username}!")
            # Определяем куда перенаправить в зависимости от роли (опционально)
            # if user.role == 'teacher': return redirect('teacher_dashboard')
            return redirect('dashboard_schedule') # По умолчанию в расписание дашборда
        else:
            messages.error(request, "Қате логин немесе құпия сөз.")
    else:
        form = CustomAuthenticationForm()
    return render(request, 'login.html', {'form': form})

def user_logout(request):
    logout(request)
    messages.info(request, "Сіз жүйеден сәтті шықтыңыз.")
    return redirect('home')

class CustomPasswordResetView(auth_views.PasswordResetView):
    template_name = 'recovery.html'
    email_template_name = 'password_reset_email.html'
    subject_template_name = 'password_reset_subject.txt'
    success_url = reverse_lazy('password_reset_done')

# ==================================
# ДАШБОРД ПОЛЬЗОВАТЕЛЯ
# ==================================

@login_required
def dashboard_schedule_view(request):
    user = request.user
    schedules_queryset = Schedule.objects.none()
    schedules_by_date = defaultdict(list)

    today = timezone.localdate()
    start_of_week = today - timedelta(days=today.weekday())
    end_of_week = start_of_week + timedelta(days=6)

    target_user = user # По умолчанию смотрим расписание залогиненного пользователя
    user_role = getattr(user, 'role', None)
    user_school = getattr(user, 'school', None)

    try:
        if user_role == 'parent':
            # Ищем ученика, связанного с родителем
            try:
                # Предполагается, что у UserProfile есть OneToOne 'parent_of' на User (студента)
                target_user = user.userprofile.parent_of
                if not target_user:
                    messages.warning(request, "Сіздің профиліңізге оқушы тіркелмеген.")
                    target_user = None # Сбрасываем, чтобы не было ошибки дальше
            except UserProfile.DoesNotExist:
                 messages.warning(request, "Сіздің профиліңіз табылмады немесе оқушы тіркелмеген.")
                 target_user = None
            except AttributeError:
                 messages.error(request, "Профиль мен оқушы байланысында қате ('parent_of').")
                 target_user = None

        # Получаем расписание для целевого пользователя (или для школы, если админ/директор)
        if target_user and user_role in ['student', 'parent']: # Студент или родитель (смотрящий за студентом)
             schedules_queryset = Schedule.objects.filter(
                student=target_user, date__range=[start_of_week, end_of_week]
            ).select_related('subject', 'teacher', 'school_class')
        elif user_role == 'teacher':
             schedules_queryset = Schedule.objects.filter(
                teacher=user, date__range=[start_of_week, end_of_week]
            ).select_related('subject', 'student', 'school_class')
        elif user_role in ['admin', 'director']:
            if user_school:
                schedules_queryset = Schedule.objects.filter(
                    school_class__school=user_school, date__range=[start_of_week, end_of_week]
                ).select_related('subject', 'teacher', 'student', 'school_class')
            elif user.is_superuser: # Суперюзер видит всё
                schedules_queryset = Schedule.objects.filter(
                    date__range=[start_of_week, end_of_week]
                ).select_related('subject', 'teacher', 'student', 'school_class')
            else:
                messages.warning(request, "Мектеп кестесін көру үшін мектепке тіркелуіңіз керек.")
        elif target_user: # Если target_user найден (для родителя), но роль не покрыта выше
             messages.warning(request, f"'{user_role}' рөлі үшін кесте көрсетілмейді.")

        # Сортировка и группировка по дате
        schedules_queryset = schedules_queryset.order_by('date', 'time')
        for lesson in schedules_queryset:
            schedules_by_date[lesson.date].append(lesson)

    except Exception as e:
        messages.error(request, f"Кестені жүктеу кезінде күтпеген қате: {e}")
        print(f"Unexpected error in dashboard_schedule_view: {e}")

    context = {
        'schedules_by_date': dict(schedules_by_date),
        'view_date_start': start_of_week,
        'view_date_end': end_of_week,
        'current_view': 'schedule' # Для подсветки активного пункта меню в базовом шаблоне
    }
    # Используем базовый шаблон дашборда, который будет включать нужный контент
    # Вместо dashboard_base.html лучше использовать имя конкретного шаблона расписания,
    # который наследуется от базового. Например, 'dashboard/schedule.html'
    return render(request, 'dashboard_schedule.html', context) # УКАЖИТЕ ПРАВИЛЬНЫЙ ШАБЛОН

@login_required
def dashboard_grades_view(request):
    user = request.user
    user_role = getattr(user, 'role', None)
    target_student = None
    subject_grades_list = []
    student_class_name = None
    current_term = get_current_term() # Получаем текущую четверть

    try:
        if user_role == 'student':
            target_student = user
        elif user_role == 'parent':
            try:
                target_student = user.userprofile.parent_of
                if not target_student:
                    messages.warning(request, "Сіздің профиліңізге оқушы тіркелмеген.")
            except UserProfile.DoesNotExist:
                 messages.warning(request, "Сіздің профиліңіз табылмады немесе оқушы тіркелмеген.")
            except AttributeError:
                 messages.error(request, "Профиль мен оқушы байланысында қате ('parent_of').")
        else:
             # Покажем сообщение, что для этой роли просмотр оценок не реализован (или требует выбора ученика)
             messages.info(request, "Бұл көрініс оқушылар мен ата-аналар үшін арналған.")
             # Можно перенаправить или показать пустую страницу
             # return redirect('dashboard_schedule')

        if target_student:
            student_class = getattr(target_student, 'school_class', None)
            student_class_name = student_class.name if student_class else "Белгісіз"

            if student_class and current_term:
                # Получаем предметы класса (или назначенные студенту, если модель позволяет)
                # subjects = Subject.objects.filter(school=student_class.school) # Пример: все предметы школы
                # Или если предметы привязаны к классу:
                subjects = student_class.subjects.all() if hasattr(student_class, 'subjects') else Subject.objects.filter(school=student_class.school)


                for subject in subjects:
                    # Получаем дневные оценки за четверть
                    daily_grades = DailyGrade.objects.filter(
                        student=target_student,
                        subject=subject,
                        # date__year=date.today().year, # Фильтр по году, если нужно
                        term=current_term
                    ).order_by('date').values_list('grade', flat=True)

                    # Получаем оценки за БЖБ (СОР) и ТЖБ (СОЧ)
                    sor_grade = ExamGrade.objects.filter(
                        student=target_student, subject=subject, term=current_term, exam_type='SOR'
                    ).first() # Берем первую найденную (или None)
                    soch_grade = ExamGrade.objects.filter(
                        student=target_student, subject=subject, term=current_term, exam_type='SOCH'
                    ).first() # Берем первую найденную (или None)

                    # TODO: Получить итоговую оценку за четверть (если она хранится отдельно)
                    term_grade_final = None # Заглушка

                    subject_grades_list.append({
                        'subject_name': subject.name,
                        'daily_grades_list': list(daily_grades),
                        'sor_grade': sor_grade.grade if sor_grade else None,
                        'soch_grade': soch_grade.grade if soch_grade else None,
                        'term_grade': term_grade_final # Используйте реальное значение
                    })
            elif not student_class:
                 messages.warning(request, f"Оқушы '{target_student.username}' сыныпқа тіркелмеген.")
            elif not current_term:
                 messages.warning(request, "Ағымдағы оқу тоқсаны анықталмады.")

    except Exception as e:
        messages.error(request, f"Бағаларды жүктеу кезінде күтпеген қате: {e}")
        print(f"Unexpected error in dashboard_grades_view: {e}")

    context = {
        'student': target_student, # Передаем объект студента (или None)
        'student_class_name': student_class_name,
        'current_term': current_term,
        'subject_grades': subject_grades_list,
        'current_view': 'grades' # Для подсветки меню
    }
    # Используем шаблон, который вы предоставили ранее
    return render(request, 'daily_grades.html', context)

@login_required
def dashboard_profile_view(request):
    user = request.user
    user_profile = None
    try:
        user_profile = user.userprofile
    except UserProfile.DoesNotExist:
        pass # Профиль может быть еще не создан
    except AttributeError:
        messages.error(request, "Профильмен байланыс қатесі ('userprofile').")
        print(f"AttributeError getting userprofile for {user.username}")
    except Exception as e:
        messages.error(request, f"Профильді жүктеу қатесі: {e}")
        print(f"Error loading profile in dashboard: {e}")

    context = {
        'user': user,
        'userprofile': user_profile,
        'current_view': 'profile' # Для подсветки меню
    }
    return render(request, 'profile.html', context)

# --- ЗАГЛУШКИ/РЕДИРЕКТЫ для других страниц дашборда (можно реализовать позже) ---
@login_required
def dashboard_exams_view(request):
    # Эта view может быть похожа на dashboard_grades_view, но фокусироваться на ExamGrade
    messages.info(request, "Бұл бөлім ('БЖБ/ТЖБ') әзірленуде.")
    # context = { 'current_view': 'exams' }
    # return render(request, 'dashboard/exams.html', context)
    return redirect('dashboard_schedule')

@login_required
def dashboard_contact_teacher_view(request):
    messages.info(request, "Бұл бөлім ('Мұғаліммен байланыс') әзірленуде.")
    # context = { 'current_view': 'contact' }
    # return render(request, 'dashboard/contact_teacher.html', context)
    return redirect('dashboard_schedule')

@login_required
def dashboard_settings_view(request):
    messages.info(request, "Бұл бөлім ('Баптаулар') әзірленуде.")
    # context = { 'current_view': 'settings' }
    # return render(request, 'dashboard/settings.html', context)
    return redirect('dashboard_schedule')

@login_required
def profile_page_view(request):
    # Можно просто перенаправить в дашборд-профиль
    return redirect('dashboard_profile')
    # Или оставить старую логику, если шаблон 'profile.html' сильно отличается
    # user = request.user
    # user_profile = None
    # try:
    #     user_profile = user.userprofile
    # except UserProfile.DoesNotExist: pass
    # except AttributeError: messages.error(request, "Профильмен байланыс қатесі ('userprofile').")
    # except Exception as e: messages.error(request, f"Профильді жүктеу кезінде күтпеген қате: {e}")
    # context = { 'user': user, 'userprofile': user_profile }
    # return render(request, 'profile.html', context)

# ==================================
# ОПЕРАЦИИ ДОБАВЛЕНИЯ (АДМИН/ДИРЕКТОР/УЧИТЕЛЬ)
# ==================================
# (Код для add_person, add_school, add_class, add_subject, add_schedule,
# add_daily_grade, add_exam_grade остается в целом как был,
# но с исправленными путями к шаблонам и потенциально улучшенной логикой
# фильтрации форм в GET-запросах)

# --- Пример исправленного add_daily_grade ---
@login_required
def add_daily_grade(request):
    if not hasattr(request.user, 'role') or request.user.role != 'teacher':
         return HttpResponseForbidden("Баға қоюға тек мұғалімнің рұқсаты бар.")

    user_school = getattr(request.user, 'school', None)
    if not user_school:
        messages.error(request, "Баға қою үшін мектепке тіркелуіңіз керек.")
        return redirect('dashboard_profile') # Направляем в профиль, чтобы увидел проблему

    if request.method == 'POST':
        form = DailyGradeForm(request.POST)
        # Устанавливаем учителя принудительно перед валидацией
        form.instance.teacher = request.user
        # Фильтруем queryset'ы перед валидацией
        form.fields['student'].queryset = User.objects.filter(role='student', school=user_school)
        form.fields['subject'].queryset = Subject.objects.filter(school=user_school) # Или только предметы учителя?

        if form.is_valid():
            grade = form.save(commit=False)
            # Дополнительные проверки (хотя queryset частично это делает)
            if getattr(grade.student, 'school', None) != user_school:
                form.add_error('student', "Оқушы сіздің мектебіңізден емес.")
            elif getattr(grade.subject, 'school', None) != user_school:
                form.add_error('subject', "Пән сіздің мектебіңізден емес.")
            else:
                grade.save()
                messages.success(request, "Күнделікті баға сәтті қойылды.")
                # Перенаправляем на страницу оценок (или другую relevant страницу)
                return redirect('dashboard_grades')
    else: # GET request
        form = DailyGradeForm(initial={'teacher': request.user})
        form.fields['student'].queryset = User.objects.filter(role='student', school=user_school)
        form.fields['subject'].queryset = Subject.objects.filter(school=user_school)
        form.fields['teacher'].widget = forms.HiddenInput()

    context = {
        'form': form,
        'current_view': 'add_daily_grade'
    }
    return render(request, 'add_daily_grades.html', context)

# --- Остальные add_* views нужно аналогично проверить/исправить ---
# Убедитесь, что они рендерят шаблоны из папки 'dashboard/' и
# что фильтрация полей формы (особенно в GET) корректна для роли пользователя.

@login_required
def add_person(request, form=None):
    # ... (логика как была, но рендер 'dashboard/add_person.html') ...
     if not hasattr(request.user, 'role') or request.user.role not in ['admin', 'director']:
         return HttpResponseForbidden("Рұқсат жоқ.")
     # ... (остальная логика) ...
     return render(request, 'add_person.html', {'form': form, 'current_view': 'add_person'})


@login_required
def add_school(request, form=None):
    # ... (логика как была, но рендер 'dashboard/add_school.html') ...
    if not request.user.is_superuser and getattr(request.user, 'role', None) != 'admin':
        return HttpResponseForbidden("Рұқсат жоқ.")
    # ... (остальная логика) ...
    return render(request, 'add_school.html', {'form': form, 'current_view': 'add_school'})

@login_required
def add_class(request, form=None):
    # ... (логика как была, но рендер 'dashboard/add_class.html') ...
    if not hasattr(request.user, 'role') or request.user.role not in ['admin', 'director']:
         return HttpResponseForbidden("Рұқсат жоқ.")
    # ... (остальная логика) ...
    return render(request, 'add_class.html', {'form': form, 'current_view': 'add_class'})

@login_required
def add_subject(request, form=None):
    # ... (логика как была, но рендер 'dashboard/add_subject.html') ...
    if not hasattr(request.user, 'role') or request.user.role not in ['admin', 'director']:
        return HttpResponseForbidden("Рұқсат жоқ.")
    # ... (остальная логика) ...
    return render(request, 'add_subject.html', {'form':form, 'current_view': 'add_subject'})

@login_required
def add_schedule(request, form=None):
    # ... (логика как была, но рендер 'dashboard/add_schedule.html') ...
    if not hasattr(request.user, 'role') or request.user.role not in ['teacher', 'admin', 'director']:
        return HttpResponseForbidden("Рұқсат жоқ.")
    # ... (остальная логика) ...
    return render(request, 'add_schedule.html', {'form': form, 'current_view': 'add_schedule'})


@login_required
def add_exam_grade(request):
    # ... (логика как была, но рендер 'dashboard/add_exam_grade.html') ...
     if not hasattr(request.user, 'role') or request.user.role != 'teacher':
        return HttpResponseForbidden("Баға қоюға тек мұғалімнің рұқсаты бар.")
     # ... (остальная логика) ...
     # Проверяем фильтрацию формы для GET
     form = ExamGradeForm(initial={'teacher': request.user})
     user_school = getattr(request.user, 'school', None)
     if user_school:
         form.fields['student'].queryset = User.objects.filter(role='student', school=user_school)
         form.fields['subject'].queryset = Subject.objects.filter(school=user_school)
     form.fields['teacher'].widget = forms.HiddenInput()

     return render(request, 'add_exam_grades.html', {'form': form, 'current_view': 'add_exam_grade'})


# ==================================
# УСТАРЕВШИЕ VIEWS (Редиректы)
# ==================================
# Оставляем редиректы для обратной совместимости

@login_required
def schedule(request):
    messages.info(request, "Күнделік енді жеке кабинетте ('Дашборд') қолжетімді.")
    return redirect('dashboard_schedule')

@login_required
def daily_grades(request, class_id=None): # Объединяем обе версии
    messages.info(request, "Бағалар енді жеке кабинетте ('Дашборд') қолжетімді.")
    # Если раньше был class_id, сейчас он не используется в dashboard_grades_view
    # для студента/родителя. Админу/учителю может понадобиться выбор класса.
    return redirect('dashboard_grades')

@login_required
def exam_grades(request, class_id=None): # Объединяем обе версии
    messages.info(request, "БЖБ/ТЖБ бағалары енді жеке кабинетте ('Дашборд') қолжетімді.")
    return redirect('dashboard_exams')

@login_required
def journal(request):
    messages.info(request, "Журнал енді жеке кабинетте ('Дашборд') қолжетімді.")
    # Журнал обычно это смесь расписания и оценок, направим на оценки
    return redirect('dashboard_grades')

@login_required
def teacher_schedule(request):
    messages.info(request, "Сіздің кестеңіз енді жеке кабинетте ('Дашборд') қолжетімді.")
    return redirect('dashboard_schedule')