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

def get_current_term(ref_date=None):
    """Определяет учебную четверть по дате."""
    today = ref_date if ref_date else date.today()
    # Примерная логика, НАСТРОЙТЕ под ваш учебный год
    # Сентябрь, Октябрь -> 1 четверть
    if 9 <= today.month <= 10: return 1
    # Ноябрь, Декабрь -> 2 четверть
    elif 11 <= today.month <= 12: return 2
    # Январь, Февраль, Март -> 3 четверть
    elif 1 <= today.month <= 3: return 3
    # Апрель, Май -> 4 четверть
    elif 4 <= today.month <= 5: return 4
    # Июнь, Июль, Август -> Каникулы/Нет четверти
    else: return None

def redirect_user_based_on_role(request, user):
    role = getattr(user, 'role', None)
    if role in ['student', 'teacher', 'parent', 'admin', 'director']:
        return redirect('dashboard_schedule')
    elif user.is_staff or user.is_superuser:
         messages.info(request, "Перенаправление в панель администратора сайта.")
         try:
             return redirect(reverse('admin:index'))
         except Exception as e:
             print(f"Не удалось получить URL админки ('admin:index'): {e}")
             messages.warning(request, "Не удалось перейти в панель администратора. Перенаправление в профиль.")
             return redirect('dashboard_profile')
    else:
        messages.warning(request, "Сіздің рөліңіз жүйеде анықталмаған. Профиль бетіне бағытталдыңыз.")
        return redirect('dashboard_profile')

def home(request):
    if request.user.is_authenticated:
        return redirect_user_based_on_role(request, request.user)
    return render(request, 'home.html')

def about(request):
    # Убедитесь, что шаблон about_us.html существует
    return render(request, 'about_us.html')

def recommendations(request):
    messages.info(request, "Бұл бет әзірленуде.")
    # Убедитесь, что шаблон recommendations.html существует или измените редирект
    return render(request, 'recommendations.html')

# ==================================
# АУТЕНТИФИКАЦИЯ, РЕГИСТРАЦИЯ, ПАРОЛЬ
# ==================================
def register(request):
    if request.user.is_authenticated:
         return redirect_user_based_on_role(request, request.user)

    if request.method == 'POST':
        form = UserRegistrationForm(request.POST)
        if form.is_valid():
            user = form.save()
            UserProfile.objects.get_or_create(user=user)
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
    # Убедитесь, что шаблон register.html существует
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
    else:
        form = CustomAuthenticationForm()
    # Убедитесь, что шаблон login.html существует
    return render(request, 'login.html', {'form': form})

def user_logout(request):
    logout(request)
    messages.info(request, "Сіз жүйеден сәтті шықтыңыз.")
    return redirect('home')

class CustomPasswordResetView(auth_views.PasswordResetView):
    template_name = 'password_reset_form.html' # Используйте имя шаблона формы сброса
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
    target_user = user # По умолчанию смотрим свое расписание (для учителя/админа)
    user_role = getattr(user, 'role', None)
    user_school = getattr(user, 'school', None)
    display_mode = user_role # Как интерпретировать расписание
    target_class = None # Класс, чье расписание смотрим (для студента/родителя)

    try:
        current_date_str = request.GET.get('date')
        ref_date = datetime.strptime(current_date_str, '%Y-%m-%d').date() if current_date_str else timezone.localdate()
    except (ValueError, TypeError):
        ref_date = timezone.localdate()

    weekday = ref_date.weekday()
    start_of_week = ref_date - timedelta(days=weekday)
    end_of_week = start_of_week + timedelta(days=6)
    prev_week_start = start_of_week - timedelta(days=7)
    next_week_start = start_of_week + timedelta(days=7)

    try:
        if user_role == 'parent':
            linked_student = getattr(user, 'parent_of', None)
            if linked_student:
                target_user = linked_student
                display_mode = 'student'
                user_school = getattr(target_user, 'school', user_school)
                try:
                    profile = UserProfile.objects.get(user=linked_student)
                    target_class = profile.school_class # Используем новое имя поля
                except UserProfile.DoesNotExist:
                     messages.warning(request, f"Байланысқан оқушы '{target_user.username}' профилі табылмады.")
                     target_class = None
                except AttributeError:
                     messages.warning(request, f"Байланысқан оқушы '{target_user.username}' профилінде сынып көрсетілмеген.")
                     target_class = None
            else:
                messages.warning(request, "Сіздің профиліңізге оқушы тіркелмеген.")
                target_user = None
        elif user_role == 'student':
            try:
                profile = user.userprofile # Используем related_name
                target_class = profile.school_class # Используем новое имя поля
                if not target_class:
                     messages.warning(request, "Сіз сыныпқа тіркелмегенсіз.")
            except UserProfile.DoesNotExist:
                 messages.warning(request, "Профиль деректері табылмады.")
                 target_class = None
            except AttributeError:
                 messages.warning(request, "Профиль деректері толық емес, сынып анықталмады.")
                 target_class = None


        if display_mode == 'student':
            if target_class:
                schedules_queryset = Schedule.objects.filter(
                    school_class=target_class, date__range=[start_of_week, end_of_week]
                ).select_related('subject', 'teacher', 'school_class__school')
        elif display_mode == 'teacher':
            schedules_queryset = Schedule.objects.filter(
                teacher=target_user, date__range=[start_of_week, end_of_week]
            ).select_related('subject', 'school_class', 'school_class__school', 'teacher__school')
        elif display_mode in ['admin', 'director']:
             if user_school:
                 schedules_queryset = Schedule.objects.filter(
                     school_class__school=user_school, date__range=[start_of_week, end_of_week]
                 ).select_related('subject', 'teacher', 'school_class')
             elif user.is_superuser:
                 schedules_queryset = Schedule.objects.filter(
                     date__range=[start_of_week, end_of_week]
                 ).select_related('subject', 'teacher', 'school_class', 'school_class__school')
             else:
                 messages.warning(request, "Мектеп кестесін көру үшін мектепке тіркелуіңіз керек.")

        if schedules_queryset.exists():
            # --- ИСПРАВЛЕНА СТРОКА: Убрали 'time_start' ---
            schedules_queryset = schedules_queryset.order_by('date', 'lesson_number')
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
        'target_user': target_user if display_mode != 'student' else user,
        'viewing_student': target_user if display_mode == 'student' else None,
        'target_class': target_class,
        'prev_week_date_str': prev_week_start.strftime('%Y-%m-%d'),
        'next_week_date_str': next_week_start.strftime('%Y-%m-%d'),
    }
    # Убедитесь, что шаблон dashboard_schedule.html существует
    return render(request, 'dashboard_schedule.html', context)


@login_required
def profile_edit(request):
    user = request.user
    try:
        user_profile = user.userprofile # Используем related name
    except UserProfile.DoesNotExist:
        user_profile = UserProfile.objects.create(user=user)

    if request.method == 'POST':
        user_form = UserEditForm(request.POST, instance=user)
        # Передаем пользователя в UserProfileEditForm, если форма его использует
        profile_form = UserProfileEditForm(request.POST, request.FILES, instance=user_profile, user=user)

        if user_form.is_valid() and profile_form.is_valid():
            user_form.save()
            profile_form.save()
            messages.success(request, 'Профиль сәтті жаңартылды!')
            return redirect('dashboard_profile')
        else:
            messages.error(request, 'Форманы толтыруда қателер пайда болды. Тексеріңіз.')
    else: # GET
        user_form = UserEditForm(instance=user)
        profile_form = UserProfileEditForm(instance=user_profile, user=user)

    context = {
        'user_form': user_form,
        'profile_form': profile_form,
        'current_view': 'profile_edit',
        'userprofile': user_profile
    }
    # Убедитесь, что шаблон profile_edit.html существует
    return render(request, 'profile_edit.html', context)


# ===== ИЗМЕНЕННАЯ ФУНКЦИЯ =====
@login_required
def dashboard_grades_view(request):
    user = request.user
    user_role = getattr(user, 'role', None)
    target_student = None
    student_class = None
    subject_grades_list = []
    student_class_name = "Сынып анықталмаған"
    available_terms = [1, 2, 3, 4] # Доступные четверти

    # --- Определяем выбранную или текущую четверть ---
    try:
        selected_term_str = request.GET.get('term')
        if selected_term_str:
            selected_term = int(selected_term_str)
            if selected_term not in available_terms:
                 messages.warning(request, f"Көрсетілген '{selected_term_str}' тоқсаны жарамсыз. Ағымдағы тоқсан көрсетілді.")
                 selected_term = get_current_term()
        else:
            selected_term = get_current_term()
    except (ValueError, TypeError):
        messages.warning(request, "Тоқсан параметрі жарамсыз. Ағымдағы тоқсан көрсетілді.")
        selected_term = get_current_term()

    # --- Отладочный вывод ---
    # print(f"--- dashboard_grades_view ---")
    # print(f"User: {user.username}, Role: {user_role}")
    # print(f"Requested/Selected Term: {selected_term}")

    try:
        # Определяем студента
        if user_role == 'student':
            target_student = user
        elif user_role == 'parent':
            target_student = getattr(user, 'parent_of', None)
            if not target_student:
                messages.warning(request, "Сіздің профиліңізге оқушы тіркелмеген.")
        elif is_teacher(user) or is_admin_or_director(user):
             messages.info(request, "Бағалар журналын көру үшін арнайы бетке өтіңіз немесе оқушының профилін таңдаңыз.")
        else:
             messages.info(request, "Бағаларды көру рөліңіз үшін қолжетімсіз.")

        # Получаем данные, если студент определен
        if target_student:
            # print(f"Target Student: {target_student.username} (ID: {target_student.id})")
            try:
                student_profile = target_student.userprofile
                student_class = student_profile.school_class # Используем новое имя поля
                if student_class:
                    student_class_name = student_class.name
                    # print(f"Student Class: {student_class_name} (ID: {student_class.id})")
                else:
                    messages.warning(request, f"Оқушы '{target_student.username}' сыныпқа тіркелмеген.")
            except UserProfile.DoesNotExist:
                messages.warning(request, f"Оқушы '{target_student.username}' профилі табылмады.")
                student_class = None
            except AttributeError:
                 messages.warning(request, f"Оқушы '{target_student.username}' профилінде сынып көрсетілмеген.")
                 student_class = None

            # Продолжаем, только если класс найден
            if student_class:
                subjects_qs = student_class.subjects.all().order_by('name')
                # print(f"Subjects for class {student_class.name}: {[s.name for s in subjects_qs]}")

                if not subjects_qs.exists():
                    messages.warning(request, f"{student_class_name} сыныбына пәндер тағайындалмаған.")

                if selected_term is not None and subjects_qs.exists():
                    # print(f"Filtering grades for Term: {selected_term}")
                    for subject in subjects_qs:
                        # print(f"  Processing Subject: {subject.name} (ID: {subject.id})")

                        daily_grades_qs = DailyGrade.objects.filter(
                            student=target_student, subject=subject, term=selected_term
                        ).order_by('date')
                        # print(f"    Found Daily Grades (QuerySet): {daily_grades_qs.count()}")

                        sor_grade_obj = ExamGrade.objects.filter(
                            student=target_student, subject=subject, term=selected_term, exam_type='SOR'
                        ).first()
                        soch_grade_obj = ExamGrade.objects.filter(
                            student=target_student, subject=subject, term=selected_term, exam_type='SOCH'
                        ).first()
                        # print(f"    Found SOR: {'Yes' if sor_grade_obj else 'No'}")
                        # print(f"    Found SOCH: {'Yes' if soch_grade_obj else 'No'}")

                        term_grade_final = None # TODO: Реализовать расчет итоговой оценки

                        subject_grades_list.append({
                            'subject_name': subject.name,
                            'daily_grades_list': daily_grades_qs,
                            'sor_grade': sor_grade_obj.grade if sor_grade_obj else None,
                            'sor_max_grade': sor_grade_obj.max_grade if sor_grade_obj else None,
                            'sor_comment': sor_grade_obj.comment if sor_grade_obj else None,
                            'soch_grade': soch_grade_obj.grade if soch_grade_obj else None,
                            'soch_max_grade': soch_grade_obj.max_grade if soch_grade_obj else None,
                            'soch_comment': soch_grade_obj.comment if soch_grade_obj else None,
                            'term_grade': term_grade_final
                        })
                elif selected_term is None:
                     messages.warning(request, "Ағымдағы оқу тоқсаны анықталмады (мүмкін, қазір каникул). Бағаларды көру үшін тоқсанды таңдаңыз.")

    except Exception as e:
        messages.error(request, f"Бағаларды жүктеу кезінде күтпеген қате: {e}")
        print(f"Unexpected error in dashboard_grades_view: {e}") # Логируем ошибку

    context = {
        'student': target_student,
        'student_class_name': student_class_name,
        'current_term': selected_term,
        'available_terms': available_terms,
        'subject_grades': subject_grades_list,
        'current_view': 'grades',
        'display_role': user_role,
    }
    # Убедитесь, что шаблон daily_grades.html существует
    return render(request, 'daily_grades.html', context)

@login_required
def dashboard_profile_view(request):
    user = request.user
    user_profile = None
    try:
        user_profile = user.userprofile
    except (UserProfile.DoesNotExist, AttributeError):
         pass

    context = {
        'profile_user': user,
        'userprofile': user_profile,
        'current_view': 'profile',
    }
    # Убедитесь, что шаблон profile.html существует
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
# --- Декораторы без изменений ---
def admin_director_required(view_func):
    decorated_view = user_passes_test(
        lambda u: (getattr(u, 'role', None) in ['admin', 'director']) or u.is_superuser,
        login_url='login'
    )(view_func)
    return decorated_view

def teacher_required(view_func):
    decorated_view = user_passes_test(
        lambda u: getattr(u, 'role', None) == 'teacher',
        login_url='login'
    )(view_func)
    return decorated_view

def school_staff_required(view_func):
    decorated_view = user_passes_test(
        lambda u: (getattr(u, 'role', None) in ['teacher', 'admin', 'director']) or u.is_superuser,
        login_url='login'
    )(view_func)
    return decorated_view

# --- Функции добавления ---

@login_required
@admin_director_required
def add_person(request):
    if request.method == 'POST':
        form = UserRegistrationForm(request.POST, request=request)
        if form.is_valid():
            user = form.save(commit=False)
            if not request.user.is_superuser and hasattr(request.user, 'school') and request.user.school:
                 user.school = request.user.school
            user.save()
            UserProfile.objects.get_or_create(user=user)
            parent_of_user = form.cleaned_data.get('parent_of')
            if parent_of_user:
                try:
                    parent_user = User.objects.get(pk=parent_of_user.pk)
                    user.parent_of = parent_user
                    user.save(update_fields=['parent_of'])
                except User.DoesNotExist:
                    messages.warning(request, f"Көрсетілген ата-ана (ID: {parent_of_user.pk}) табылмады.")

            messages.success(request, f"Пайдаланушы '{user.username}' сәтті қосылды.")
            return redirect('add_person')
        else:
            messages.error(request, "Форма толтыруда қателер бар.")
            # print(form.errors)
    else:
        form = UserRegistrationForm(request=request)

    context = {'form': form, 'current_view': 'add_person'}
    # Убедитесь, что шаблон add_person.html существует
    return render(request, 'add_person.html', context)

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
             messages.error(request, "Форма толтыруда қателер бар.")
             # print(form.errors)
    else:
        form = SchoolForm()
    context = {'form': form, 'current_view': 'add_school'}
    # Убедитесь, что шаблон add_school.html существует
    return render(request, 'add_school.html', context)

@login_required
@admin_director_required
def add_class(request):
    user_school = getattr(request.user, 'school', None)
    if not request.user.is_superuser and not user_school:
        messages.error(request, "Сынып қосу үшін мектепке тіркелуіңіз керек.")
        return redirect('dashboard_profile')

    school_filter = user_school if not request.user.is_superuser else None

    if request.method == 'POST':
        form = ClassForm(request.POST, school=school_filter)
        if 'school' in form.fields and not request.user.is_superuser and user_school:
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
                     form.save_m2m()
                     messages.success(request, f"Сынып '{new_class.name}' ({new_class.school.name}) сәтті қосылды.")
                     return redirect('add_class')
                 except IntegrityError:
                      messages.error(request, 'Бұл мектепте мұндай атаумен сынып бар.')
                      form.add_error('name', 'Бұл мектепте мұндай атаумен сынып бар.')

        else:
            messages.error(request, "Форма толтыруда қателер бар.")
            # print(form.errors)

    else: # GET
        form = ClassForm(school=school_filter)
        if 'school' in form.fields and not request.user.is_superuser and user_school:
            form.fields['school'].queryset = School.objects.filter(pk=user_school.pk)
            form.fields['school'].initial = user_school

    context = {'form': form, 'current_view': 'add_class'}
    # Убедитесь, что шаблон add_class.html существует
    return render(request, 'add_class.html', context)

@login_required
@admin_director_required
def add_subject(request):
    user_school = getattr(request.user, 'school', None)
    if not request.user.is_superuser and not user_school:
        messages.error(request, "Пән қосу үшін мектепке тіркелуіңіз керек.")
        return redirect('dashboard_profile')

    school_filter = user_school if not request.user.is_superuser else None

    if request.method == 'POST':
        form = SubjectForm(request.POST, school=school_filter)
        if 'school' in form.fields and not request.user.is_superuser and user_school:
             form.fields['school'].queryset = School.objects.filter(pk=user_school.pk)

        if form.is_valid():
            subject = form.save(commit=False)
            if not request.user.is_superuser: subject.school = user_school
            if not subject.school: form.add_error('school', 'Мектеп көрсетілмеген.')
            else:
                try:
                    subject.save()
                    messages.success(request, f"Пән '{subject.name}' ({subject.school.name}) сәтті қосылды.")
                    return redirect('add_subject')
                except IntegrityError:
                     messages.error(request, 'Бұл мектепте мұндай атаумен пән бар.')
                     form.add_error('name', 'Бұл мектепте мұндай атаумен пән бар.')
        else:
            messages.error(request, "Форма толтыруда қателер бар.")
            # print(form.errors)
    else: # GET
        form = SubjectForm(school=school_filter)
        if 'school' in form.fields and not request.user.is_superuser and user_school:
             form.fields['school'].queryset = School.objects.filter(pk=user_school.pk)
             form.fields['school'].initial = user_school

    context = {'form': form, 'current_view': 'add_subject'}
    # Убедитесь, что шаблон add_subject.html существует
    return render(request, 'add_subject.html', context)

@login_required
@school_staff_required
def add_schedule(request):
    user_school = getattr(request.user, 'school', None)
    if not request.user.is_superuser and not user_school:
        messages.error(request, "Кесте элементін қосу үшін мектепке тіркелуіңіз керек.")
        return redirect('dashboard_profile')

    school_filter = user_school if not request.user.is_superuser else None

    if request.method == 'POST':
        form = ScheduleForm(request.POST, school=school_filter, user=request.user)
        if form.is_valid():
            schedule_item = form.save(commit=False)

            valid = True
            if school_filter:
                 if hasattr(schedule_item.school_class, 'school') and schedule_item.school_class.school != school_filter:
                     form.add_error('school_class', 'Сынып сіздің мектебіңізден емес.')
                     valid = False
                 if hasattr(schedule_item.teacher, 'school') and schedule_item.teacher.school != school_filter:
                     form.add_error('teacher', 'Мұғалім сіздің мектебіңізден емес.')
                     valid = False
                 if hasattr(schedule_item.subject, 'school') and schedule_item.subject.school != school_filter:
                      form.add_error('subject', 'Пән сіздің мектебіңізден емес.')
                      valid = False

            if valid:
                try:
                    schedule_item.save()
                    messages.success(request, "Кесте элементі сәтті қосылды.")
                    return redirect('add_schedule')
                except IntegrityError:
                    messages.error(request, "Дәл осындай кесте элементі (күн, уақыт, сынып/мұғалім) бұрыннан бар.")
                    form.add_error(None, "Дәл осындай кесте элементі бұрыннан бар.")

            else:
                 messages.error(request, "Форма толтыруда қателер бар (мектеп сәйкессіздігі).")
                 # print(form.errors)

        else:
             messages.error(request, "Форма толтыруда қателер бар.")
             # print(form.errors)

    else: # GET
        form = ScheduleForm(school=school_filter, user=request.user)

    context = {'form': form, 'current_view': 'add_schedule'}
    # Убедитесь, что шаблон add_schedule.html существует
    return render(request, 'add_schedule.html', context)

@login_required
@teacher_required
def add_daily_grade(request):
    user_school = getattr(request.user, 'school', None)
    if not user_school:
        messages.error(request, "Баға қою үшін мектепке тіркелуіңіз керек.")
        return redirect('dashboard_profile')

    initial_data = {}
    if request.method == 'GET':
        subject_id = request.GET.get('subject')
        class_id = request.GET.get('class')
        date_str = request.GET.get('date')
        if subject_id: initial_data['subject'] = subject_id
        if date_str: initial_data['date'] = date_str
        if date_str:
            try:
                grade_date = datetime.strptime(date_str, '%Y-%m-%d').date()
                term_for_date = get_current_term(grade_date)
                if term_for_date:
                    initial_data['term'] = term_for_date
            except ValueError: pass

    if request.method == 'POST':
        form = DailyGradeForm(request.POST, school=user_school, user=request.user)
        if form.is_valid():
            grade = form.save(commit=False)
            grade.teacher = request.user

            # print(f"--- add_daily_grade POST ---")
            # print(f"Saving Daily Grade:")
            # print(f"  Student ID: {grade.student.id if grade.student else 'None'}")
            # print(f"  Subject ID: {grade.subject.id if grade.subject else 'None'}")
            # print(f"  Grade: {grade.grade}")
            # print(f"  Date: {grade.date}")
            # print(f"  TERM to be saved: {grade.term}")

            valid = True
            if not grade.student or getattr(grade.student, 'school', None) != user_school:
                form.add_error('student', "Оқушы сіздің мектебіңізден емес немесе көрсетілмеген.")
                valid = False
            if not grade.subject or getattr(grade.subject, 'school', None) != user_school:
                form.add_error('subject', "Пән сіздің мектебіңізден емес немесе көрсетілмеген.")
                valid = False

            if valid:
                try:
                    grade.save()
                    # print("  Grade saved successfully.")
                    messages.success(request, f"Күнделікті баға ({grade.grade}) оқушы {grade.student.get_full_name()} үшін '{grade.subject.name}' пәнінен {grade.date} күніне қойылды.")
                    return redirect(reverse('add_daily_grade'))
                except IntegrityError:
                    # print("  IntegrityError during save.")
                    messages.error(request, 'Мүмкін, бұл оқушыға осы пәннен осы күні баға қойылған.')
                    form.add_error(None, 'Мүмкін, бұл оқушыға осы пәннен осы күні баға қойылған.')
            else:
                # print("  Validation failed (school mismatch or missing fields).")
                messages.error(request, "Форма толтыруда қателер бар.")

        else:
             # print("  Form is NOT valid.")
             # print(form.errors)
             messages.error(request, "Форма толтыруда қателер бар.")

    else: # GET
        form = DailyGradeForm(initial=initial_data, school=user_school, user=request.user)

    context = {'form': form, 'current_view': 'add_daily_grade'}
    # Убедитесь, что шаблон add_daily_grades.html существует
    return render(request, 'add_daily_grades.html', context)

@login_required
@teacher_required
def add_exam_grade(request):
    user_school = getattr(request.user, 'school', None)
    if not user_school:
        messages.error(request, "Баға қою үшін мектепке тіркелуіңіз керек.")
        return redirect('dashboard_profile')

    initial_data = {}
    if request.method == 'GET':
        subject_id = request.GET.get('subject')
        class_id = request.GET.get('class')
        if subject_id: initial_data['subject'] = subject_id
        current_term_val = get_current_term()
        if current_term_val: initial_data['term'] = current_term_val

    if request.method == 'POST':
        form = ExamGradeForm(request.POST, school=user_school, user=request.user)
        if form.is_valid():
            grade = form.save(commit=False)
            grade.teacher = request.user

            # print(f"--- add_exam_grade POST ---")
            # print(f"Saving Exam Grade:")
            # print(f"  Student ID: {grade.student.id if grade.student else 'None'}")
            # print(f"  Subject ID: {grade.subject.id if grade.subject else 'None'}")
            # print(f"  Exam Type: {grade.exam_type}")
            # print(f"  Grade: {grade.grade}")
            # print(f"  TERM to be saved: {grade.term}")

            valid = True
            if not grade.student or getattr(grade.student, 'school', None) != user_school:
                form.add_error('student', "Оқушы сіздің мектебіңізден емес немесе көрсетілмеген.")
                valid = False
            if not grade.subject or getattr(grade.subject, 'school', None) != user_school:
                form.add_error('subject', "Пән сіздің мектебіңізден емес немесе көрсетілмеген.")
                valid = False

            if valid:
                try:
                    grade.save()
                    # print("  Exam Grade saved successfully.")
                    messages.success(request, f"{grade.get_exam_type_display()} бағасы ({grade.grade}) оқушы {grade.student.get_full_name()} үшін '{grade.subject.name}' пәнінен {grade.term}-тоқсанда қойылды.")
                    return redirect(reverse('add_exam_grade'))
                except IntegrityError:
                    #  print("  IntegrityError during save.")
                     messages.error(request, 'Мүмкін, бұл оқушыға осы пәннен осы тоқсанда бұл жұмыс түріне баға қойылған.')
                     form.add_error(None, 'Мүмкін, бұл оқушыға осы пәннен осы тоқсанда бұл жұмыс түріне баға қойылған.')
            else:
                #  print("  Validation failed (school mismatch or missing fields).")
                 messages.error(request, "Форма толтыруда қателер бар.")

        else:
            # print("  Form is NOT valid.")
            # print(form.errors)
            messages.error(request, "Форма толтыруда қателер бар.")

    else: # GET
        form = ExamGradeForm(initial=initial_data, school=user_school, user=request.user)

    context = {'form': form, 'current_view': 'add_exam_grade'}
    # Убедитесь, что шаблон add_exam_grades.html существует
    return render(request, 'add_exam_grades.html', context)

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
    if is_teacher(request.user): return redirect('add_daily_grade') # Учителя направляем на добавление оценок
    elif is_student(request.user) or is_parent(request.user): return redirect('dashboard_grades') # Учеников/родителей на просмотр
    else: return redirect('dashboard_schedule') # Остальных на расписание

@login_required
def teacher_schedule(request):
    messages.info(request, "Сіздің кестеңіз енді жеке кабинетте ('Дашборд') қолжетімді.")
    return redirect('dashboard_schedule')