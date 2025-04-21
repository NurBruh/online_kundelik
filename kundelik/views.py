# kundelik/views.py

from datetime import date, timedelta, datetime
from collections import defaultdict
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth import views as auth_views, login, logout, authenticate
from django.contrib import messages
from django.urls import reverse_lazy, reverse
from django import forms
from django.utils import timezone
from django.db import IntegrityError # <-- Добавили для обработки unique_together
# --- Импорты моделей ---
from .models import (
    User, UserProfile, School, Class, Subject,
    Schedule, DailyGrade, ExamGrade
)
# --- Импорты форм ---
from .forms import (
    UserRegistrationForm, CustomAuthenticationForm, SchoolForm,
    ClassForm, SubjectForm, ScheduleForm, DailyGradeForm, ExamGradeForm, UserEditForm, UserProfileEditForm
)

# ==================================
# ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ
# ==================================
def is_student(user):
    return user.is_authenticated and getattr(user, 'role', None) == 'student'
def is_teacher(user):
    return user.is_authenticated and getattr(user, 'role', None) == 'teacher'
def is_parent(user):
    return user.is_authenticated and getattr(user, 'role', None) == 'parent'
def is_admin_or_director(user):
    return user.is_authenticated and getattr(user, 'role', None) in ['admin', 'director']
def is_school_staff(user):
    return user.is_authenticated and getattr(user, 'role', None) in ['teacher', 'admin', 'director']

def get_current_term():
    today = date.today()
    # TODO: Заменить на более надежную логику определения четверти
    if 9 <= today.month <= 10: return 1
    if 11 <= today.month <= 12: return 2
    if 1 <= today.month <= 3: return 3
    if 4 <= today.month <= 5: return 4
    return None # Лето или каникулы

def redirect_user_based_on_role(request, user):
    role = getattr(user, 'role', None)
    if role in ['student', 'teacher', 'parent', 'admin', 'director']:
        # Всех направляем в расписание по умолчанию
        return redirect('dashboard_schedule')
    elif user.is_staff or user.is_superuser:
         messages.info(request, "Перенаправление в панель администратора сайта.")
         try:
             return redirect(reverse('admin:index'))
         except Exception as e:
             print(f"Не удалось получить URL админки ('admin:index'): {e}")
             messages.warning(request, "Не удалось перейти в панель администратора. Перенаправление в профиль.")
             return redirect('dashboard_profile') # Запасной вариант
    else:
        messages.warning(request, "Сіздің рөліңіз жүйеде анықталмаған. Профиль бетіне бағытталдыңыз.")
        return redirect('dashboard_profile')

def home(request):
    if request.user.is_authenticated:
        return redirect_user_based_on_role(request, request.user)
    return render(request, 'home.html')

def about(request):
    return render(request, 'about_us.html')

def recommendations(request):
    # TODO: Реализовать логику страницы рекомендаций
    messages.info(request, "Бұл бет әзірленуде.")
    return render(request, 'recommendations.html') # Или редирект

# ==================================
# АУТЕНТИФИКАЦИЯ, РЕГИСТРАЦИЯ, ПАРОЛЬ
# ==================================
def register(request):
    if request.user.is_authenticated:
         return redirect_user_based_on_role(request, request.user)

    if request.method == 'POST':
        form = UserRegistrationForm(request.POST)
        if form.is_valid():
            user = form.save() # UserCreationForm сохраняет пользователя
            # Создаем профиль (или получаем, если он вдруг уже есть)
            UserProfile.objects.get_or_create(user=user)
            # Обновляем связь родителя, если она была указана в форме
            parent_of_user = form.cleaned_data.get('parent_of')
            if parent_of_user:
                 user.parent_of = parent_of_user
                 user.save(update_fields=['parent_of'])

            login(request, user)
            messages.success(request, f"Тіркелу сәтті аяқталды! Қош келдіңіз, {user.first_name or user.username}!")
            return redirect_user_based_on_role(request, user)
        else:
            messages.error(request, "Тіркелу кезінде қателер пайда болды. Форманы тексеріңіз.")
    else:
        form = UserRegistrationForm()

    return render(request, 'register.html', {'form': form})

def user_login(request):
    if request.user.is_authenticated:
        return redirect_user_based_on_role(request, request.user)
    if request.method == 'POST':
        form = CustomAuthenticationForm(request, data=request.POST)
        if form.is_valid():
            user = form.get_user()
            login(request, user)
            messages.success(request, f"Қош келдіңіз, {user.first_name or user.username}!")
            return redirect_user_based_on_role(request, user)
        # else: Если форма невалидна, render покажет ошибки
    else:
        form = CustomAuthenticationForm()
    return render(request, 'login.html', {'form': form})

def user_logout(request):
    logout(request)
    messages.info(request, "Сіз жүйеден сәтті шықтыңыз.")
    return redirect('home')

# Используем стандартные view для сброса пароля, но с кастомными шаблонами
class CustomPasswordResetView(auth_views.PasswordResetView):
    template_name = 'password_reset_form.html' # Используйте имя шаблона формы сброса
    email_template_name = 'password_reset_email.html'
    subject_template_name = 'password_reset_subject.txt'
    success_url = reverse_lazy('password_reset_done')

# Определяем URL для стандартных представлений в urls.py, например:
# path('password_reset/done/', auth_views.PasswordResetDoneView.as_view(template_name='password_reset_done.html'), name='password_reset_done'),
# path('reset/<uidb64>/<token>/', auth_views.PasswordResetConfirmView.as_view(template_name="password_reset_confirm.html"), name='password_reset_confirm'),
# path('reset/done/', auth_views.PasswordResetCompleteView.as_view(template_name='password_reset_complete.html'), name='password_reset_complete'),

# ==================================
# ДАШБОРД ПОЛЬЗОВАТЕЛЯ
# ==================================
@login_required
def dashboard_schedule_view(request):
    user = request.user
    schedules_queryset = Schedule.objects.none()
    schedules_by_date = defaultdict(list)
    target_user = user # По умолчанию смотрим свое расписание (для учителя/админа)
    user_role = getattr(user, 'role', None)
    user_school = getattr(user, 'school', None)
    display_mode = user_role # Как интерпретировать расписание
    target_class = None # Класс, чье расписание смотрим (для студента/родителя)

    # --- Получение опорной даты ---
    try:
        current_date_str = request.GET.get('date')
        ref_date = datetime.strptime(current_date_str, '%Y-%m-%d').date() if current_date_str else timezone.localdate()
    except (ValueError, TypeError):
        ref_date = timezone.localdate()

    # --- Вычисление границ недель ---
    weekday = ref_date.weekday()
    start_of_week = ref_date - timedelta(days=weekday)
    end_of_week = start_of_week + timedelta(days=6)
    prev_week_start = start_of_week - timedelta(days=7)
    next_week_start = start_of_week + timedelta(days=7)

    try:
        # --- Определение целевого пользователя/класса ---
        if user_role == 'parent':
            linked_student = getattr(user, 'parent_of', None)
            if linked_student:
                target_user = linked_student # Теперь цель - студент
                display_mode = 'student'
                user_school = getattr(target_user, 'school', user_school)
                try:
                    target_class = target_user.userprofile.grade
                except (UserProfile.DoesNotExist, AttributeError):
                     messages.warning(request, f"Байланысқан оқушы '{target_user.username}' профилі немесе сыныбы табылмады.")
            else:
                messages.warning(request, "Сіздің профиліңізге оқушы тіркелмеген.")
                target_user = None # Нет студента - нет расписания для родителя
        elif user_role == 'student':
            try:
                target_class = user.userprofile.grade
                if not target_class:
                     messages.warning(request, "Сіз сыныпқа тіркелмегенсіз.")
            except (UserProfile.DoesNotExist, AttributeError):
                 messages.warning(request, "Профиль деректері толық емес, сынып анықталмады.")

        # --- Получение данных расписания ---
        if display_mode == 'student':
            if target_class:
                schedules_queryset = Schedule.objects.filter(
                    school_class=target_class, date__range=[start_of_week, end_of_week]
                ).select_related('subject', 'teacher', 'school_class__school')
            # else: Если класса нет, queryset останется пустым
        elif display_mode == 'teacher':
            schedules_queryset = Schedule.objects.filter(
                teacher=target_user, date__range=[start_of_week, end_of_week]
            ).select_related('subject', 'school_class', 'school_class__school')
        elif display_mode in ['admin', 'director']:
             if user_school:
                 # Показываем расписание всей школы админа/директора
                 schedules_queryset = Schedule.objects.filter(
                     school_class__school=user_school, date__range=[start_of_week, end_of_week]
                 ).select_related('subject', 'teacher', 'school_class')
             elif user.is_superuser: # Суперюзер видит всё
                 schedules_queryset = Schedule.objects.filter(
                     date__range=[start_of_week, end_of_week]
                 ).select_related('subject', 'teacher', 'school_class', 'school_class__school')
             else:
                 messages.warning(request, "Мектеп кестесін көру үшін мектепке тіркелуіңіз керек.")
        # Для других ролей schedules_queryset останется пустым

        # --- Сортировка и группировка ---
        if schedules_queryset.exists():
            schedules_queryset = schedules_queryset.order_by('date', 'lesson_number') # Сортировка без времени
            for lesson in schedules_queryset:
                schedules_by_date[lesson.date].append(lesson)

    except Exception as e:
        messages.error(request, f"Кестені жүктеу кезінде күтпеген қате: {e}")
        print(f"Unexpected error in dashboard_schedule_view: {e}")

    context = {
        'schedules_by_date': dict(schedules_by_date),
        'view_date_start': start_of_week,
        'view_date_end': end_of_week,
        'current_view': 'schedule',
        'display_role': display_mode,
        'target_user': target_user if display_mode != 'student' else user, # Для заголовка (студент видит свое имя)
        'viewing_student': target_user if display_mode == 'student' else None, # Явно передаем студента
        'target_class': target_class,
        'prev_week_date_str': prev_week_start.strftime('%Y-%m-%d'),
        'next_week_date_str': next_week_start.strftime('%Y-%m-%d'),
    }
    return render(request, 'dashboard_schedule.html', context)

@login_required
def profile_edit(request):
    user = request.user
    # Используем get_or_create для надежности
    user_profile, created = UserProfile.objects.get_or_create(user=user)

    if request.method == 'POST':
        user_form = UserEditForm(request.POST, instance=user)
        # Передаем instance профиля
        profile_form = UserProfileEditForm(request.POST, request.FILES, instance=user_profile)

        if user_form.is_valid() and profile_form.is_valid():
            user_form.save()
            profile_form.save()
            messages.success(request, 'Профиль сәтті жаңартылды!')
            return redirect('dashboard_profile')
        else:
            messages.error(request, 'Форманы толтыруда қателер пайда болды. Тексеріңіз.')
    else: # GET
        user_form = UserEditForm(instance=user)
        profile_form = UserProfileEditForm(instance=user_profile) # Форма сама отфильтрует классы в __init__

    context = {
        'user_form': user_form,
        'profile_form': profile_form,
        'current_view': 'profile',
        'userprofile': user_profile # Передаем профиль для отображения текущего аватара
    }
    # profile_user не нужен, т.к. user есть по умолчанию, а профиль передается как userprofile
    return render(request, 'profile_edit.html', context)

@login_required
def dashboard_grades_view(request):
    user = request.user
    user_role = getattr(user, 'role', None)
    target_student = None
    student_class = None
    subject_grades_list = []
    student_class_name = "Сынып анықталмаған"
    current_term = get_current_term()

    try:
        # Определяем студента
        if user_role == 'student':
            target_student = user
        elif user_role == 'parent':
            target_student = getattr(user, 'parent_of', None)
            if not target_student:
                messages.warning(request, "Сіздің профиліңізге оқушы тіркелмеген.")
        elif is_teacher(user) or is_admin_or_director(user):
             messages.info(request, "Бағалар журналын көру үшін арнайы бетке өтіңіз.")
        else:
             messages.info(request, "Бағаларды көру рөліңіз үшін қолжетімсіз.")

        # Получаем данные, если студент определен
        if target_student:
            try:
                student_profile = target_student.userprofile
                student_class = student_profile.grade
                if student_class:
                    student_class_name = student_class.name
                else:
                    messages.warning(request, f"Оқушы '{target_student.username}' сыныпқа тіркелмеген.")
            except (UserProfile.DoesNotExist, AttributeError):
                messages.warning(request, f"Оқушы '{target_student.username}' профилі табылмады.")

            if student_class:
                subjects_qs = student_class.subjects.all().order_by('name')
                if not subjects_qs.exists():
                    messages.warning(request, f"{student_class_name} сыныбына пәндер тағайындалмаған.")

                if current_term and subjects_qs.exists():
                    for subject in subjects_qs:
                        daily_grades = DailyGrade.objects.filter(
                            student=target_student, subject=subject, term=current_term
                        ).order_by('date').values('grade', 'date', 'comment')

                        sor_grade_obj = ExamGrade.objects.filter(
                            student=target_student, subject=subject, term=current_term, exam_type='SOR'
                        ).first()
                        soch_grade_obj = ExamGrade.objects.filter(
                            student=target_student, subject=subject, term=current_term, exam_type='SOCH'
                        ).first()

                        term_grade_final = None # TODO: Реализовать расчет итоговой оценки

                        subject_grades_list.append({
                            'subject_name': subject.name,
                            'daily_grades_list': list(daily_grades),
                            'sor_grade': sor_grade_obj.grade if sor_grade_obj else None,
                            'sor_max_grade': sor_grade_obj.max_grade if sor_grade_obj else None,
                            'sor_comment': sor_grade_obj.comment if sor_grade_obj else None,
                            'soch_grade': soch_grade_obj.grade if soch_grade_obj else None,
                            'soch_max_grade': soch_grade_obj.max_grade if soch_grade_obj else None,
                            'soch_comment': soch_grade_obj.comment if soch_grade_obj else None,
                            'term_grade': term_grade_final
                        })
                elif not current_term:
                     messages.warning(request, "Ағымдағы оқу тоқсаны анықталмады.")

    except Exception as e:
        messages.error(request, f"Бағаларды жүктеу кезінде күтпеген қате: {e}")
        print(f"Unexpected error in dashboard_grades_view: {e}")

    context = {
        'student': target_student, # Передаем объект студента
        'student_class_name': student_class_name,
        'current_term': current_term,
        'subject_grades': subject_grades_list,
        'current_view': 'grades',
        'display_role': user_role, # Роль того, кто смотрит страницу
    }
    # Убедитесь, что шаблон daily_grades.html может отобразить эту структуру
    return render(request, 'daily_grades.html', context)

@login_required
def dashboard_profile_view(request):
    user = request.user
    user_profile = None
    try:
        user_profile = user.userprofile
    except (UserProfile.DoesNotExist, AttributeError):
        messages.info(request, "Профиль деректері әлі толық емес немесе қате.")

    context = {
        'profile_user': user, # Пользователь, чей профиль отображается
        'userprofile': user_profile,
        'current_view': 'profile',
    }
    return render(request, 'profile.html', context)

# --- Заглушки/Редиректы (без изменений) ---
@login_required
def dashboard_exams_view(request):
    messages.info(request, "Бұл бөлім ('БЖБ/ТЖБ') әзірленуде.")
    return redirect('dashboard_grades')
@login_required
def dashboard_contact_teacher_view(request):
    messages.info(request, "Бұл бөлім ('Мұғаліммен байланыс') әзірленуде.")
    return redirect('dashboard_schedule')
@login_required
def dashboard_settings_view(request):
    messages.info(request, "Бұл бөлім ('Баптаулар') әзірленуде.")
    return redirect('dashboard_profile')
@login_required
def profile_page_view(request): # Старый URL
    return redirect('dashboard_profile')

# ==================================
# ОПЕРАЦИИ ДОБАВЛЕНИЯ
# ==================================
def admin_director_required(view_func):
    return user_passes_test(is_admin_or_director, login_url='login')(view_func)
def teacher_required(view_func):
    return user_passes_test(is_teacher, login_url='login')(view_func)
def school_staff_required(view_func):
    return user_passes_test(is_school_staff, login_url='login')(view_func)

@login_required
@admin_director_required
def add_person(request):
    if request.method == 'POST':
        form = UserRegistrationForm(request.POST)
        if form.is_valid():
            user = form.save(commit=False)
            if not request.user.is_superuser and hasattr(request.user, 'school'):
                 user.school = request.user.school # Привязываем к школе админа
            user.save() # Сохраняем User
            UserProfile.objects.get_or_create(user=user) # Создаем профиль
            # Обновляем parent_of, если был указан
            parent_of_user = form.cleaned_data.get('parent_of')
            if parent_of_user:
                user.parent_of = parent_of_user
                user.save(update_fields=['parent_of'])
            messages.success(request, f"Пайдаланушы '{user.username}' сәтті қосылды.")
            return redirect('add_person')
        else:
            messages.error(request, "Форма толтыруда қателер бар.")
    else:
        form = UserRegistrationForm()
        if not request.user.is_superuser and hasattr(request.user, 'school') and request.user.school:
             form.fields['school'].initial = request.user.school
             # form.fields['school'].queryset = School.objects.filter(pk=request.user.school.pk)

    context = {'form': form, 'current_view': 'add_person'}
    return render(request, 'add_person.html', context) # Нужен шаблон add_person.html

@login_required
@user_passes_test(lambda u: u.is_superuser, login_url='home')
def add_school(request):
    if request.method == 'POST':
        form = SchoolForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, "Мектеп сәтті қосылды.")
            return redirect('add_school')
    else:
        form = SchoolForm()
    context = {'form': form, 'current_view': 'add_school'}
    return render(request, 'add_school.html', context) # Нужен шаблон add_school.html

@login_required
@admin_director_required
def add_class(request):
    user_school = getattr(request.user, 'school', None)
    if not user_school and not request.user.is_superuser:
        messages.error(request, "Сынып қосу үшін мектепке тіркелуіңіз керек.")
        return redirect('dashboard_profile')

    if request.method == 'POST':
        # Передаем школу в форму для фильтрации M2M
        form = ClassForm(request.POST, school=user_school if not request.user.is_superuser else None)
        # Ограничиваем выбор школы для не-суперюзера
        if not request.user.is_superuser and user_school:
            form.fields['school'].queryset = School.objects.filter(pk=user_school.pk)

        if form.is_valid():
            new_class = form.save(commit=False)
            if not request.user.is_superuser:
                new_class.school = user_school
            if not new_class.school:
                 form.add_error('school', 'Мектеп көрсетілмеген.')
            else:
                 try:
                     new_class.save()
                     form.save_m2m() # Сохраняем предметы (ManyToMany)
                     messages.success(request, f"Сынып '{new_class.name}' сәтті қосылды.")
                     return redirect('add_class')
                 except IntegrityError: # Обработка unique_together для Class
                      form.add_error('name', 'Бұл мектепте мұндай сынып бар.')

    else: # GET
        # Передаем школу в форму для фильтрации M2M при GET запросе
        form = ClassForm(school=user_school if not request.user.is_superuser else None)
        if not request.user.is_superuser and user_school:
            form.fields['school'].queryset = School.objects.filter(pk=user_school.pk)
            form.fields['school'].initial = user_school
            # form.fields['school'].widget = forms.HiddenInput()

    context = {'form': form, 'current_view': 'add_class'}
    return render(request, 'add_class.html', context) # Нужен шаблон add_class.html

@login_required
@admin_director_required
def add_subject(request):
    user_school = getattr(request.user, 'school', None)
    if not user_school and not request.user.is_superuser:
        messages.error(request, "Пән қосу үшін мектепке тіркелуіңіз керек.")
        return redirect('dashboard_profile')

    if request.method == 'POST':
        form = SubjectForm(request.POST)
        if not request.user.is_superuser and user_school:
            form.fields['school'].queryset = School.objects.filter(pk=user_school.pk)

        if form.is_valid():
            subject = form.save(commit=False)
            if not request.user.is_superuser: subject.school = user_school
            if not subject.school: form.add_error('school', 'Мектеп көрсетілмеген.')
            else:
                try:
                    subject.save()
                    messages.success(request, f"Пән '{subject.name}' сәтті қосылды.")
                    return redirect('add_subject')
                except IntegrityError:
                     form.add_error('name', 'Бұл мектепте мұндай пән бар.')
    else:
        form = SubjectForm()
        if not request.user.is_superuser and user_school:
             form.fields['school'].queryset = School.objects.filter(pk=user_school.pk)
             form.fields['school'].initial = user_school
             # form.fields['school'].widget = forms.HiddenInput()

    context = {'form': form, 'current_view': 'add_subject'}
    return render(request, 'add_subject.html', context) # Нужен шаблон add_subject.html

@login_required
@school_staff_required
def add_schedule(request):
    user_school = getattr(request.user, 'school', None)
    if not user_school and not request.user.is_superuser:
        messages.error(request, "Кесте элементін қосу үшін мектепке тіркелуіңіз керек.")
        return redirect('dashboard_profile')

    # Передаем школу и пользователя в форму для фильтрации и установки initial
    school_filter = user_school if not request.user.is_superuser else None

    if request.method == 'POST':
        form = ScheduleForm(request.POST, school=school_filter, user=request.user)
        if form.is_valid():
            schedule_item = form.save(commit=False)
            # Доп. проверки (школа класса, учителя, предмета)
            valid = True
            if school_filter: # Проверяем только если не суперюзер
                 if getattr(schedule_item.school_class, 'school', None) != school_filter:
                     form.add_error('school_class', 'Сынып сіздің мектебіңізден емес.')
                     valid = False
                 if getattr(schedule_item.teacher, 'school', None) != school_filter:
                     form.add_error('teacher', 'Мұғалім сіздің мектебіңізден емес.')
                     valid = False
                 if getattr(schedule_item.subject, 'school', None) != school_filter:
                      form.add_error('subject', 'Пән сіздің мектебіңізден емес.')
                      valid = False

            if valid:
                schedule_item.save()
                messages.success(request, "Кесте элементі сәтті қосылды.")
                return redirect('add_schedule')
    else: # GET
        form = ScheduleForm(school=school_filter, user=request.user)

    context = {'form': form, 'current_view': 'add_schedule'}
    return render(request, 'add_schedule.html', context) # Нужен шаблон add_schedule.html

@login_required
@teacher_required
def add_daily_grade(request):
    user_school = getattr(request.user, 'school', None)
    if not user_school: # Учитель должен быть привязан к школе
        messages.error(request, "Баға қою үшін мектепке тіркелуіңіз керек.")
        return redirect('dashboard_profile')

    # Передаем школу и учителя в форму
    if request.method == 'POST':
        form = DailyGradeForm(request.POST, school=user_school, user=request.user)
        if form.is_valid():
            grade = form.save(commit=False)
            # Учитель уже установлен в __init__ формы
            # Доп. проверки
            valid = True
            if getattr(grade.student, 'school', None) != user_school:
                form.add_error('student', "Оқушы сіздің мектебіңізден емес.")
                valid = False
            if getattr(grade.subject, 'school', None) != user_school:
                form.add_error('subject', "Пән сіздің мектебіңізден емес.")
                valid = False
            # TODO: Проверка, ведет ли учитель этот предмет у этого студента/класса

            if valid:
                try:
                    grade.save()
                    messages.success(request, "Күнделікті баға сәтті қойылды.")
                    # Редирект для добавления следующей оценки (или на другую страницу)
                    return redirect('add_daily_grade')
                except IntegrityError:
                    form.add_error(None, 'Мүмкін, бұл оқушыға осы пәннен осы күні баға қойылған (unique_together).')
    else: # GET
        form = DailyGradeForm(school=user_school, user=request.user)

    context = {'form': form, 'current_view': 'add_daily_grade'}
    return render(request, 'add_daily_grades.html', context) # Нужен шаблон add_daily_grades.html

@login_required
@teacher_required
def add_exam_grade(request):
    user_school = getattr(request.user, 'school', None)
    if not user_school:
        messages.error(request, "Баға қою үшін мектепке тіркелуіңіз керек.")
        return redirect('dashboard_profile')

    # Передаем школу и учителя в форму
    if request.method == 'POST':
        form = ExamGradeForm(request.POST, school=user_school, user=request.user)
        if form.is_valid():
            grade = form.save(commit=False)
            # Учитель уже установлен в __init__
            valid = True
            if getattr(grade.student, 'school', None) != user_school:
                form.add_error('student', "Оқушы сіздің мектебіңізден емес.")
                valid = False
            if getattr(grade.subject, 'school', None) != user_school:
                form.add_error('subject', "Пән сіздің мектебіңізден емес.")
                valid = False
            # TODO: Проверка предмета учителя

            if valid:
                try:
                    grade.save()
                    messages.success(request, f"{grade.get_exam_type_display()} бағасы сәтті қойылды.")
                    return redirect('add_exam_grade')
                except IntegrityError:
                     form.add_error(None, 'Мүмкін, бұл оқушыға осы пәннен осы тоқсанда бұл жұмыс түріне баға қойылған (unique_together).')
    else: # GET
        form = ExamGradeForm(school=user_school, user=request.user)

    context = {'form': form, 'current_view': 'add_exam_grade'}
    return render(request, 'add_exam_grades.html', context) # Нужен шаблон add_exam_grades.html

# ==================================
# УСТАРЕВШИЕ VIEWS (РЕДИРЕКТЫ)
# ==================================
@login_required
def schedule(request):
    messages.info(request, "Кесте енді жеке кабинетте ('Дашборд') қолжетімді.")
    return redirect('dashboard_schedule')

@login_required
def daily_grades(request, class_id=None):
    messages.info(request, "Бағалар енді жеке кабинетте ('Дашборд') қолжетімді.")
    return redirect('dashboard_grades')

@login_required
def exam_grades(request, class_id=None):
    messages.info(request, "БЖБ/ТЖБ бағалары енді жеке кабинетте ('Дашборд') қолжетімді.")
    return redirect('dashboard_grades')

@login_required
def journal(request):
    messages.info(request, "Журнал функциялары енді жеке кабинетте ('Дашборд') қолжетімді.")
    if is_teacher(request.user): return redirect('add_daily_grade')
    elif is_student(request.user) or is_parent(request.user): return redirect('dashboard_grades')
    else: return redirect('dashboard_schedule')

@login_required
def teacher_schedule(request):
    messages.info(request, "Сіздің кестеңіз енді жеке кабинетте ('Дашборд') қолжетімді.")
    return redirect('dashboard_schedule')