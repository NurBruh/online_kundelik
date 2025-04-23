# kundelik/views.py

from datetime import date, timedelta, datetime
from collections import defaultdict

from django.core.exceptions import ValidationError
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth import views as auth_views, login, logout, authenticate
from django.contrib import messages
from django.urls import reverse_lazy, reverse
from django import forms
from django.utils import timezone
from django.db import IntegrityError
from django.db.models import Avg, Sum
from django.http import Http404
import math

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
    return user.is_authenticated and (getattr(user, 'role', None) in ['admin', 'director'] or user.is_superuser)
def is_school_staff(user):
    return user.is_authenticated and (getattr(user, 'role', None) in ['teacher', 'admin', 'director'] or user.is_superuser)

def get_current_term(ref_date=None):
    """Определяет учебную четверть по дате."""
    today = ref_date if ref_date else date.today()
    year = today.year
    school_year_start_year = year if today.month >= 9 else year - 1
    term1_start = date(school_year_start_year, 9, 1); term1_end = date(school_year_start_year, 10, 31)
    term2_start = date(school_year_start_year, 11, 8); term2_end = date(school_year_start_year, 12, 31)
    term3_start = date(school_year_start_year + 1, 1, 11); term3_end = date(school_year_start_year + 1, 3, 20)
    term4_start = date(school_year_start_year + 1, 4, 1); term4_end = date(school_year_start_year + 1, 5, 25)
    if term1_start <= today <= term1_end: return 1
    if term2_start <= today <= term2_end: return 2
    if term3_start <= today <= term3_end: return 3
    if term4_start <= today <= term4_end: return 4
    return None

def redirect_user_based_on_role(request, user):
    role = getattr(user, 'role', None)
    if role in ['student', 'teacher', 'parent', 'admin', 'director']: return redirect('dashboard_schedule')
    elif user.is_staff or user.is_superuser:
         messages.info(request, "Перенаправление в панель администратора сайта.")
         try: return redirect(reverse('admin:index'))
         except Exception as e:
             print(f"Не удалось получить URL админки ('admin:index'): {e}")
             messages.warning(request, "Не удалось перейти в панель администратора. Перенаправление в профиль.")
             return redirect('dashboard_profile')
    else: messages.warning(request, "Сіздің рөліңіз жүйеде анықталмаған. Профиль бетіне бағытталдыңыз."); return redirect('dashboard_profile')

# --- Негізгі беттер ---
def home(request):
    if request.user.is_authenticated: return redirect_user_based_on_role(request, request.user)
    return render(request, 'home.html')
def about(request): return render(request, 'about_us.html')
def recommendations(request): messages.info(request, "Бұл бет әзірленуде."); return render(request, 'recommendations.html')

# --- Аутентификация, Регистрация, Құпия сөз ---
def register(request):
    if request.user.is_authenticated: return redirect_user_based_on_role(request, request.user)
    if request.method == 'POST':
        form = UserRegistrationForm(request.POST, user=request.user)
        if form.is_valid():
            user = form.save()
            UserProfile.objects.get_or_create(user=user)
            parent_of_user = form.cleaned_data.get('parent_of')
            if parent_of_user: user.parent_of = parent_of_user; user.save(update_fields=['parent_of'])
            login(request, user)
            messages.success(request, f"Тіркелу сәтті аяқталды! Қош келдіңіз, {user.first_name or user.username}!")
            return redirect_user_based_on_role(request, user)
        else: messages.error(request, "Тіркелу кезінде қателер пайда болды. Форманы тексеріңіз.")
    else: form = UserRegistrationForm(user=request.user)
    return render(request, 'register.html', {'form': form})

def user_login(request):
    if request.user.is_authenticated: return redirect_user_based_on_role(request, request.user)
    if request.method == 'POST':
        form = CustomAuthenticationForm(request, data=request.POST)
        if form.is_valid():
            user = form.get_user(); login(request, user)
            messages.success(request, f"Қош келдіңіз, {user.first_name or user.username}!")
            return redirect_user_based_on_role(request, user)
    else: form = CustomAuthenticationForm()
    return render(request, 'login.html', {'form': form})

def user_logout(request): logout(request); messages.info(request, "Сіз жүйеден сәтті шықтыңыз."); return redirect('home')
class CustomPasswordResetView(auth_views.PasswordResetView):
    template_name = 'password_reset_form.html'; email_template_name = 'password_reset_email.html'
    subject_template_name = 'password_reset_subject.txt'; success_url = reverse_lazy('password_reset_done')

# ==================================
# ПАЙДАЛАНУШЫ ПАНЕЛІ (ДАШБОРД)
# ==================================
@login_required
def dashboard_schedule_view(request):
    user = request.user; schedules_by_date = defaultdict(list); target_user = user
    user_role = getattr(user, 'role', None); user_school = getattr(user, 'school', None)
    display_mode = user_role; target_class = None; viewing_student = None
    try:
        current_date_str = request.GET.get('date')
        ref_date = datetime.strptime(current_date_str, '%Y-%m-%d').date() if current_date_str else timezone.localdate()
    except (ValueError, TypeError): ref_date = timezone.localdate()
    weekday = ref_date.weekday(); start_of_week = ref_date - timedelta(days=weekday)
    end_of_week = start_of_week + timedelta(days=6); prev_week_start = start_of_week - timedelta(days=7)
    next_week_start = start_of_week + timedelta(days=7); schedule_filters = {'date__range': [start_of_week, end_of_week]}
    schedules_queryset = Schedule.objects.none()
    try:
        if user_role == 'parent':
            linked_student = getattr(user, 'parent_of', None)
            if linked_student:
                target_user = linked_student; viewing_student = linked_student; display_mode = 'student'
                user_school = getattr(target_user, 'school', user_school)
                try: target_class = target_user.userprofile.grade
                except (UserProfile.DoesNotExist, AttributeError): target_class = None
                if not target_class: messages.warning(request, f"Оқушы '{target_user.username}' үшін сынып көрсетілмеген.")
            else: messages.warning(request, "Сіздің профиліңізге оқушы тіркелмеген."); schedule_filters = None
        elif user_role == 'student':
            viewing_student = user
            try: target_class = user.userprofile.grade
            except (UserProfile.DoesNotExist, AttributeError): target_class = None
            if not target_class: messages.warning(request, "Профиліңізде сынып көрсетілмеген, кесте көрсетілмейді.")
        if schedule_filters is not None:
            if display_mode == 'student' and target_class: schedule_filters['school_class'] = target_class
            elif display_mode == 'teacher': schedule_filters['teacher'] = target_user
            elif display_mode in ['admin', 'director']:
                 if user_school: schedule_filters['school_class__school'] = user_school
                 elif not user.is_superuser: messages.warning(request, "Мектеп кестесін көру үшін мектепке тіркелуіңіз керек."); schedule_filters = None
            elif display_mode == 'parent' and not viewing_student: schedule_filters = None
            elif display_mode == 'student' and not target_class: schedule_filters = None
            if schedule_filters is not None:
                schedules_queryset = Schedule.objects.filter(**schedule_filters).select_related(
                    'subject', 'teacher', 'school_class', 'school_class__school'
                ).order_by('date', 'lesson_number', 'time_start')
                for lesson in schedules_queryset: schedules_by_date[lesson.date].append(lesson)
    except Exception as e: messages.error(request, f"Кестені жүктеу кезінде күтпеген қате: {e}"); print(f"Unexpected error in dashboard_schedule_view: {e}")
    context = {
        'schedules_by_date': dict(schedules_by_date), 'view_date_start': start_of_week, 'view_date_end': end_of_week,
        'current_view': 'schedule', 'display_role': display_mode, 'target_user': target_user, 'viewing_student': viewing_student,
        'target_class': target_class, 'prev_week_date_str': prev_week_start.strftime('%Y-%m-%d'), 'next_week_date_str': next_week_start.strftime('%Y-%m-%d'),
    }
    return render(request, 'dashboard_schedule.html', context)

@login_required
def profile_edit(request):
    user = request.user
    try: user_profile = user.userprofile
    except UserProfile.DoesNotExist: user_profile = UserProfile.objects.create(user=user)
    if request.method == 'POST':
        user_form = UserEditForm(request.POST, instance=user)
        profile_form = UserProfileEditForm(request.POST, request.FILES, instance=user_profile, user=user)
        if user_form.is_valid() and profile_form.is_valid():
            user_form.save(); profile_form.save()
            messages.success(request, 'Профиль сәтті жаңартылды!')
            return redirect('dashboard_profile')
        else: messages.error(request, 'Профильді жаңарту кезінде қателер пайда болды. Форманы тексеріңіз.')
    else: # GET
        user_form = UserEditForm(instance=user); profile_form = UserProfileEditForm(instance=user_profile, user=user)
    context = { 'user_form': user_form, 'profile_form': profile_form, 'current_view': 'profile_edit', 'userprofile': user_profile }
    return render(request, 'profile_edit.html', context)

@login_required
def dashboard_grades_view(request):
    user = request.user; user_role = getattr(user, 'role', None); target_student = None; student_class = None
    subject_grades_list = []; student_class_name = "Сынып анықталмаған"; available_terms = [1, 2, 3, 4]
    try:
        selected_term_str = request.GET.get('term')
        selected_term = int(selected_term_str) if selected_term_str and selected_term_str.isdigit() and int(selected_term_str) in available_terms else get_current_term()
    except (ValueError, TypeError): selected_term = get_current_term()
    try:
        if user_role == 'student': target_student = user
        elif user_role == 'parent':
            target_student = getattr(user, 'parent_of', None)
            if not target_student: messages.warning(request, "Сіздің профиліңізге оқушы тіркелмеген.")
        elif is_teacher(user) or is_admin_or_director(user): messages.info(request, "Бағалар журналын көру үшін 'Баға қою' немесе арнайы есеп беру беттеріне өтіңіз.")
        else: messages.info(request, "Бағаларды көру рөліңіз үшін қолжетімсіз.")
        if target_student:
            try:
                student_profile = target_student.userprofile; student_class = student_profile.grade
                if student_class: student_class_name = f"{student_class.name} ({student_class.school.name})"
                else: messages.warning(request, f"Оқушы '{target_student.username}' сыныпқа тіркелмеген.")
            except (UserProfile.DoesNotExist, AttributeError): student_class = None; messages.warning(request, f"Оқушы '{target_student.username}' профилі немесе сыныбы табылмады.")
            if student_class and selected_term is not None:
                subjects_qs = student_class.subjects.all().order_by('name')
                if not subjects_qs.exists(): messages.warning(request, f"{student_class_name} сыныбына пәндер тағайындалмаған.")
                for subject in subjects_qs:
                    daily_grades_qs = DailyGrade.objects.filter(student=target_student, subject=subject, term=selected_term).order_by('date')
                    daily_grades_data = list(daily_grades_qs.values('grade', 'date', 'comment'))
                    sor_grade_obj = ExamGrade.objects.filter(student=target_student, subject=subject, term=selected_term, exam_type='SOR').first()
                    soch_grade_obj = ExamGrade.objects.filter(student=target_student, subject=subject, term=selected_term, exam_type='SOCH').first()
                    term_grade_final = None
                    daily_grades_values = [g['grade'] for g in daily_grades_data if g.get('grade') is not None]
                    if daily_grades_values:
                        avg_daily = sum(daily_grades_values) / len(daily_grades_values); rounded_grade = math.floor(avg_daily + 0.5)
                        term_grade_final = max(2, min(5, rounded_grade))
                    subject_grades_list.append({
                        'subject_name': subject.name, 'daily_grades_list': daily_grades_data,
                        'sor_grade': sor_grade_obj.grade if sor_grade_obj else None, 'sor_max_grade': sor_grade_obj.max_grade if sor_grade_obj else None, 'sor_comment': sor_grade_obj.comment if sor_grade_obj else None,
                        'soch_grade': soch_grade_obj.grade if soch_grade_obj else None, 'soch_max_grade': soch_grade_obj.max_grade if soch_grade_obj else None, 'soch_comment': soch_grade_obj.comment if soch_grade_obj else None,
                        'term_grade': term_grade_final
                    })
            elif selected_term is None: messages.warning(request, "Ағымдағы оқу тоқсаны анықталмады немесе каникул уақыты. Бағаларды көру үшін тоқсанды таңдаңыз.")
    except Exception as e: messages.error(request, f"Бағаларды жүктеу кезінде күтпеген қате: {e}"); print(f"Unexpected error in dashboard_grades_view: {e}")
    context = {
        'student': target_student, 'student_class_name': student_class_name, 'current_term': selected_term,
        'available_terms': available_terms, 'subject_grades': subject_grades_list, 'current_view': 'grades',
        'display_role': user_role, 'target_user': target_student,
    }
    return render(request, 'daily_grades.html', context)

@login_required
def dashboard_profile_view(request):
    user = request.user; user_profile = None
    try: user_profile = user.userprofile
    except (UserProfile.DoesNotExist, AttributeError): pass
    context = {'profile_user': user, 'userprofile': user_profile, 'current_view': 'profile'}
    return render(request, 'profile.html', context)

# --- Заглушки/Редиректы (Өзгеріссіз) ---
@login_required
def dashboard_exams_view(request): messages.info(request, "Бұл бөлім ('БЖБ/ТЖБ') әзірленуде."); return redirect('dashboard_grades')
@login_required
def dashboard_contact_teacher_view(request): messages.info(request, "Бұл бөлім ('Мұғаліммен байланыс') әзірленуде."); return redirect('dashboard_schedule')
@login_required
def dashboard_settings_view(request): messages.info(request, "Бұл бөлім ('Баптаулар') әзірленуде."); return redirect('dashboard_profile')
@login_required
def profile_page_view(request): return redirect('dashboard_profile')

# ==================================
# ҚОСУ ОПЕРАЦИЯЛАРЫ
# ==================================
# --- Декораторлар (Өзгеріссіз) ---
def admin_director_required(view_func): return user_passes_test(lambda u: (getattr(u, 'role', None) in ['admin', 'director']) or u.is_superuser, login_url='login')(view_func)
def teacher_required(view_func): return user_passes_test(lambda u: getattr(u, 'role', None) == 'teacher', login_url='login')(view_func)
def school_staff_required(view_func): return user_passes_test(lambda u: (getattr(u, 'role', None) in ['teacher', 'admin', 'director']) or u.is_superuser, login_url='login')(view_func)

# --- add_person, add_school, add_class, add_subject (Өзгеріссіз) ---
@login_required
@admin_director_required
def add_person(request):
    if request.method == 'POST':
        form = UserRegistrationForm(request.POST, user=request.user)
        if form.is_valid():
            user = form.save()
            UserProfile.objects.get_or_create(user=user)
            parent_of_user = form.cleaned_data.get('parent_of')
            if parent_of_user: user.parent_of = parent_of_user; user.save(update_fields=['parent_of'])
            messages.success(request, f"Пайдаланушы '{user.username}' сәтті қосылды.")
            return redirect('add_person')
        else: messages.error(request, "Форма толтыруда қателер бар.")
    else: # GET
        form = UserRegistrationForm(user=request.user)
    context = {'form': form, 'current_view': 'add_person'}
    return render(request, 'add_person.html', context)

@login_required
@user_passes_test(lambda u: u.is_superuser, login_url='home')
def add_school(request):
    if request.method == 'POST':
        form = SchoolForm(request.POST)
        if form.is_valid(): form.save(); messages.success(request, "Мектеп сәтті қосылды."); return redirect('add_school')
        else: messages.error(request, "Форма толтыруда қателер бар.")
    else: form = SchoolForm()
    context = {'form': form, 'current_view': 'add_school'}
    return render(request, 'add_school.html', context)

@login_required
@admin_director_required
def add_class(request):
    user_school = getattr(request.user, 'school', None)
    if not request.user.is_superuser and not user_school: messages.error(request, "Сынып қосу үшін мектепке тіркелуіңіз керек."); return redirect('dashboard_profile')
    school_filter = user_school if not request.user.is_superuser else None
    if request.method == 'POST':
        form = ClassForm(request.POST, school=school_filter)
        if form.is_valid():
            new_class = form.save(commit=False)
            if not request.user.is_superuser and school_filter: new_class.school = school_filter
            elif not new_class.school: form.add_error('school', 'Мектеп көрсетілмеген.');
            if not form.errors:
                 try: new_class.save(); form.save_m2m(); messages.success(request, f"Сынып '{new_class.name}' ({new_class.school.name}) сәтті қосылды."); return redirect('add_class')
                 except IntegrityError: form.add_error('name', 'Бұл мектепте мұндай атаумен сынып бұрыннан бар.')
                 except Exception as e: messages.error(request, f"Сыныпты сақтау кезінде қате: {e}")
            else: messages.error(request, "Форма толтыруда қателер бар.")
        else: messages.error(request, "Форма толтыруда қателер бар.")
    else: # GET
        form = ClassForm(school=school_filter)
    context = {'form': form, 'current_view': 'add_class'}
    return render(request, 'add_class.html', context)

@login_required
@admin_director_required
def add_subject(request):
    user_school = getattr(request.user, 'school', None)
    if not request.user.is_superuser and not user_school: messages.error(request, "Пән қосу үшін мектепке тіркелуіңіз керек."); return redirect('dashboard_profile')
    school_filter = user_school if not request.user.is_superuser else None
    if request.method == 'POST':
        form = SubjectForm(request.POST, school=school_filter)
        if form.is_valid():
            subject = form.save(commit=False)
            if not request.user.is_superuser and school_filter: subject.school = school_filter
            elif not subject.school: form.add_error('school', 'Мектеп көрсетілмеген.');
            if not form.errors:
                try: subject.save(); messages.success(request, f"Пән '{subject.name}' ({subject.school.name}) сәтті қосылды."); return redirect('add_subject')
                except IntegrityError: form.add_error('name', 'Бұл мектепте мұндай атаумен пән бар.')
                except Exception as e: messages.error(request, f"Пәнді сақтау кезінде қате: {e}")
            else: messages.error(request, "Форма толтыруда қателер бар.")
        else: messages.error(request, "Форма толтыруда қателер бар.")
    else: # GET
        form = SubjectForm(school=school_filter)
    context = {'form': form, 'current_view': 'add_subject'}
    return render(request, 'add_subject.html', context)

# --- add_schedule (Өзгеріссіз) ---
@login_required
@school_staff_required
def add_schedule(request):
    user = request.user
    user_school = getattr(user, 'school', None)
    if not user.is_superuser and not user_school: messages.error(request, "Кесте элементін қосу үшін мектепке тіркелуіңіз керек."); return redirect('dashboard_profile')
    school_filter = user_school if not request.user.is_superuser else None
    initial_data = {}
    date_from_get = request.GET.get('date')
    if date_from_get:
        try: valid_date = datetime.strptime(date_from_get, '%Y-%m-%d').date(); initial_data['date'] = valid_date
        except ValueError: messages.warning(request, "Кестеге қосу үшін жарамсыз күн форматы (`YYYY-MM-DD` болуы керек).")

    if request.method == 'POST':
        form = ScheduleForm(request.POST, school=school_filter, user=user)
        if form.is_valid():
            schedule_item = form.save(commit=False)
            is_teacher_adding = is_teacher(user); teacher_field_disabled = False
            if 'teacher' in form.fields: teacher_field_disabled = form.fields['teacher'].disabled
            if is_teacher_adding and teacher_field_disabled: schedule_item.teacher = user
            try:
                schedule_item.full_clean()
                schedule_item.save()
                messages.success(request, f"Кесте элементі ({schedule_item.date}, {schedule_item.lesson_number}-сабақ, {schedule_item.school_class.name}, {schedule_item.subject.name}) сәтті қосылды.")
                return redirect('add_schedule')
            except (IntegrityError, ValidationError) as e:
                if isinstance(e, IntegrityError): form.add_error(None, "Дәл осындай кесте элементі (күні, сыныбы, сабақ нөмірі немесе күні, мұғалім, сабақ нөмірі) бұрыннан бар.")
                elif isinstance(e, ValidationError):
                     if hasattr(e, 'error_dict'):
                         for field, errors in e.message_dict.items(): form.add_error(field if field != '__all__' else None, errors)
                     else: form.add_error(None, e.messages)
                messages.error(request, "Кесте элементін сақтау мүмкін болмады. Мәліметтерді тексеріңіз.")
            except Exception as e: messages.error(request, f"Кестені сақтау кезінде күтпеген қате: {e}")
        else: messages.error(request, "Форма толтыруда қателер бар. Өрістерді тексеріңіз.")
    else: # GET
        form = ScheduleForm(initial=initial_data, school=school_filter, user=user)
    context = {'form': form, 'current_view': 'add_schedule'}
    return render(request, 'add_schedule.html', context)


# --- add_daily_grade (ДЕБАГГИНГ ҚОСЫЛҒАН) ---
@login_required
@teacher_required
def add_daily_grade(request):
    user = request.user
    user_school = getattr(user, 'school', None)
    if not user_school:
        messages.error(request, "Баға қою үшін мектепке тіркелуіңіз керек.")
        return redirect('dashboard_profile')

    teacher_classes = Class.objects.filter(school=user_school).order_by('name')
    selected_class_id_str = request.GET.get('class_id') or request.POST.get('selected_class_id')
    selected_class_id = None
    selected_class = None
    students_queryset = User.objects.none() # Изначально пустой queryset
    show_form = False

    # --- ДЕБАГГИНГ БАСЫ ---
    print(f"\n--- add_daily_grade: Request User: {user} (ID: {user.id}), School: {user_school}")
    print(f"--- add_daily_grade: Received class_id_str: '{selected_class_id_str}'")
    # --- ДЕБАГГИНГ СОҢЫ ---

    if selected_class_id_str and selected_class_id_str.isdigit():
        try:
            selected_class_id = int(selected_class_id_str)
            # --- ДЕБАГГИНГ БАСЫ ---
            print(f"--- add_daily_grade: Parsed class_id: {selected_class_id}")
            # --- ДЕБАГГИНГ СОҢЫ ---
            selected_class = Class.objects.get(pk=selected_class_id)
            # --- ДЕБАГГИНГ БАСЫ ---
            print(f"--- add_daily_grade: Found Class: {selected_class} (School: {selected_class.school})")
            # --- ДЕБАГГИНГ СОҢЫ ---

            if not request.user.is_superuser and selected_class.school != user_school:
                messages.error(request, "Бұл сынып сіздің мектебіңізге жатпайды.")
                # --- ДЕБАГГИНГ БАСЫ ---
                print(f"--- add_daily_grade: ERROR - Class school mismatch (Class: {selected_class.school}, User: {user_school})")
                # --- ДЕБАГГИНГ СОҢЫ ---
                selected_class = None; selected_class_id = None
            else:
                 # --- ДЕБАГГИНГ БАСЫ ---
                 print(f"--- add_daily_grade: Filtering students: role='student', school={selected_class.school}, userprofile__school_class={selected_class}")
                 # --- ДЕБАГГИНГ СОҢЫ ---
                 students_queryset = User.objects.filter(
                     role='student',
                     school=selected_class.school,
                     userprofile__school_class=selected_class # Нақты өріспен сүзу
                 ).select_related('userprofile').order_by('last_name', 'first_name')
                 # --- ДЕБАГГИНГ БАСЫ ---
                 print(f"--- add_daily_grade: Found students count: {students_queryset.count()}")
                 # Көп оқушы болса, терминалды толтырмас үшін алғашқы 5-еуін шығарайық
                 if students_queryset.exists():
                      print(f"--- add_daily_grade: Found students (first 5): {list(students_queryset[:5].values_list('id', 'username'))}") # ID мен username шығару
                 # --- ДЕБАГГИНГ СОҢЫ ---

                 if students_queryset.exists():
                      show_form = True
                      # --- ДЕБАГГИНГ БАСЫ ---
                      print(f"--- add_daily_grade: Setting show_form = True")
                      # --- ДЕБАГГИНГ СОҢЫ ---
                 else:
                      messages.warning(request, f"Таңдалған сыныпта ('{selected_class.name}') тіркелген оқушылар табылмады.")
                      # --- ДЕБАГГИНГ БАСЫ ---
                      print(f"--- add_daily_grade: No students found, show_form = False")
                      # --- ДЕБАГГИНГ СОҢЫ ---

        except Class.DoesNotExist:
            messages.error(request, f"Сынып табылмады (ID: {selected_class_id_str}).")
            # --- ДЕБАГГИНГ БАСЫ ---
            print(f"--- add_daily_grade: ERROR - Class.DoesNotExist for ID: {selected_class_id_str}")
            # --- ДЕБАГГИНГ СОҢЫ ---
            selected_class_id = None; selected_class = None

    elif selected_class_id_str is not None and selected_class_id_str != "":
        messages.error(request, f"Жарамсыз сынып идентификаторы: '{selected_class_id_str}'.")
        # --- ДЕБАГГИНГ БАСЫ ---
        print(f"--- add_daily_grade: ERROR - Invalid class ID format: '{selected_class_id_str}'")
        # --- ДЕБАГГИНГ СОҢЫ ---
        selected_class_id = None; selected_class = None
    # else: # ID бос немесе жоқ болса, дебаггинг қосуға болады
    #    print(f"--- add_daily_grade: No class ID provided.")

    initial_data = {'teacher': user}
    subject_id_get = request.GET.get('subject'); date_str_get = request.GET.get('date')
    if subject_id_get: initial_data['subject'] = subject_id_get
    if date_str_get:
        initial_data['date'] = date_str_get
        try:
            grade_date = datetime.strptime(date_str_get, '%Y-%m-%d').date()
            term_for_date = get_current_term(grade_date)
            if term_for_date: initial_data['term'] = term_for_date
        except ValueError: pass

    if request.method == 'POST':
        # --- ДЕБАГГИНГ БАСЫ ---
        print(f"--- add_daily_grade (POST): show_form = {show_form}")
        # --- ДЕБАГГИНГ СОҢЫ ---
        if not show_form:
             messages.error(request, "Баға қою үшін жарамды сынып таңдалып, онда оқушылар болуы керек.")
             redirect_url = reverse('add_daily_grade')
             if selected_class_id: redirect_url += f'?class_id={selected_class_id}'
             return redirect(redirect_url)

        form = DailyGradeForm(request.POST, school=user_school, user=user)
        form.fields['student'].queryset = students_queryset

        if form.is_valid():
            grade = form.save(commit=False); grade.teacher = user
            try:
                grade.full_clean(); grade.save()
                messages.success(request, f"Баға ({grade.grade}) оқушы {grade.student.get_full_name()} үшін '{grade.subject.name}' пәнінен ({grade.date}) сәтті қойылды.")
                redirect_url = reverse('add_daily_grade')
                if selected_class_id: redirect_url += f'?class_id={selected_class_id}'
                return redirect(redirect_url)
            except (IntegrityError, ValidationError) as e:
                if isinstance(e, IntegrityError): form.add_error(None, 'Бұл оқушыға осы пәннен осы күні баға бұрын қойылған болуы мүмкін.')
                elif isinstance(e, ValidationError):
                     if hasattr(e, 'error_dict'):
                         for field, errors in e.message_dict.items(): form.add_error(field if field != '__all__' else None, errors)
                     else: form.add_error(None, e.messages)
                messages.error(request, "Бағаны сақтау мүмкін болмады.")
            except Exception as e: messages.error(request, f"Бағаны сақтау кезінде күтпеген қате: {e}")
        else:
            # POST кезінде форма жарамсыз болса, студенттер тізімін қайта орнату маңызды
            form.fields['student'].queryset = students_queryset
            messages.error(request, "Форма толтыруда қателер бар. Өрістерді тексеріңіз.")
    else: # GET
        form = DailyGradeForm(initial=initial_data, school=user_school, user=user)
        form.fields['student'].queryset = students_queryset

    context = {
        'form': form, 'teacher_classes': teacher_classes, 'selected_class': selected_class,
        'students_count': students_queryset.count(), 'show_form': show_form,
        'current_view': 'add_daily_grade'
    }
    # --- ДЕБАГГИНГ БАСЫ ---
    print(f"--- add_daily_grade: Rendering context: show_form={show_form}, students_count={students_queryset.count()}")
    # --- ДЕБАГГИНГ СОҢЫ ---
    return render(request, 'add_daily_grades.html', context)


# --- add_exam_grade (ДЕБАГГИНГ ҚОСЫЛҒАН) ---
@login_required
@teacher_required
def add_exam_grade(request):
    user = request.user
    user_school = getattr(user, 'school', None)
    if not user_school:
        messages.error(request, "Баға қою үшін мектепке тіркелуіңіз керек.")
        return redirect('dashboard_profile')

    teacher_classes = Class.objects.filter(school=user_school).order_by('name')
    selected_class_id_str = request.GET.get('class_id') or request.POST.get('selected_class_id')
    selected_class_id = None
    selected_class = None
    students_queryset = User.objects.none()
    show_form = False

    # --- ДЕБАГГИНГ БАСЫ ---
    print(f"\n--- add_exam_grade: Request User: {user} (ID: {user.id}), School: {user_school}")
    print(f"--- add_exam_grade: Received class_id_str: '{selected_class_id_str}'")
    # --- ДЕБАГГИНГ СОҢЫ ---

    if selected_class_id_str and selected_class_id_str.isdigit():
        try:
            selected_class_id = int(selected_class_id_str)
            # --- ДЕБАГГИНГ БАСЫ ---
            print(f"--- add_exam_grade: Parsed class_id: {selected_class_id}")
            # --- ДЕБАГГИНГ СОҢЫ ---
            selected_class = Class.objects.get(pk=selected_class_id)
            # --- ДЕБАГГИНГ БАСЫ ---
            print(f"--- add_exam_grade: Found Class: {selected_class} (School: {selected_class.school})")
            # --- ДЕБАГГИНГ СОҢЫ ---

            if not request.user.is_superuser and selected_class.school != user_school:
                messages.error(request, "Бұл сынып сіздің мектебіңізге жатпайды.")
                # --- ДЕБАГГИНГ БАСЫ ---
                print(f"--- add_exam_grade: ERROR - Class school mismatch (Class: {selected_class.school}, User: {user_school})")
                # --- ДЕБАГГИНГ СОҢЫ ---
                selected_class = None; selected_class_id = None
            else:
                 # --- ДЕБАГГИНГ БАСЫ ---
                 print(f"--- add_exam_grade: Filtering students: role='student', school={selected_class.school}, userprofile__school_class={selected_class}")
                 # --- ДЕБАГГИНГ СОҢЫ ---
                 students_queryset = User.objects.filter(
                     role='student',
                     school=selected_class.school,
                     userprofile__school_class=selected_class
                 ).select_related('userprofile').order_by('last_name', 'first_name')
                 # --- ДЕБАГГИНГ БАСЫ ---
                 print(f"--- add_exam_grade: Found students count: {students_queryset.count()}")
                 if students_queryset.exists():
                      print(f"--- add_exam_grade: Found students (first 5): {list(students_queryset[:5].values_list('id', 'username'))}") # ID мен username шығару
                 # --- ДЕБАГГИНГ СОҢЫ ---

                 if students_queryset.exists():
                     show_form = True
                     # --- ДЕБАГГИНГ БАСЫ ---
                     print(f"--- add_exam_grade: Setting show_form = True")
                     # --- ДЕБАГГИНГ СОҢЫ ---
                 else:
                     messages.warning(request, f"Таңдалған сыныпта ('{selected_class.name}') тіркелген оқушылар табылмады.")
                     # --- ДЕБАГГИНГ БАСЫ ---
                     print(f"--- add_exam_grade: No students found, show_form = False")
                     # --- ДЕБАГГИНГ СОҢЫ ---

        except Class.DoesNotExist:
            messages.error(request, f"Сынып табылмады (ID: {selected_class_id_str}).")
            # --- ДЕБАГГИНГ БАСЫ ---
            print(f"--- add_exam_grade: ERROR - Class.DoesNotExist for ID: {selected_class_id_str}")
            # --- ДЕБАГГИНГ СОҢЫ ---
            selected_class_id = None; selected_class = None

    elif selected_class_id_str is not None and selected_class_id_str != "":
        messages.error(request, f"Жарамсыз сынып идентификаторы: '{selected_class_id_str}'.")
        # --- ДЕБАГГИНГ БАСЫ ---
        print(f"--- add_exam_grade: ERROR - Invalid class ID format: '{selected_class_id_str}'")
        # --- ДЕБАГГИНГ СОҢЫ ---
        selected_class_id = None; selected_class = None
    # else:
    #    print(f"--- add_exam_grade: No class ID provided.")

    initial_data = {'teacher': user}
    current_term_val = get_current_term()
    if current_term_val: initial_data['term'] = current_term_val
    subject_id_get = request.GET.get('subject')
    if subject_id_get: initial_data['subject'] = subject_id_get

    if request.method == 'POST':
        # --- ДЕБАГГИНГ БАСЫ ---
        print(f"--- add_exam_grade (POST): show_form = {show_form}")
        # --- ДЕБАГГИНГ СОҢЫ ---
        if not show_form:
             messages.error(request, "Баға қою үшін жарамды сынып таңдалып, онда оқушылар болуы керек.")
             redirect_url = reverse('add_exam_grade')
             if selected_class_id: redirect_url += f'?class_id={selected_class_id}'
             return redirect(redirect_url)

        form = ExamGradeForm(request.POST, school=user_school, user=user)
        form.fields['student'].queryset = students_queryset

        if form.is_valid():
            grade = form.save(commit=False); grade.teacher = user
            try:
                grade.full_clean(); grade.save()
                messages.success(request, f"{grade.get_exam_type_display()} бағасы ({grade.grade}/{grade.max_grade}) оқушы {grade.student.get_full_name()} үшін '{grade.subject.name}' пәнінен ({grade.term}-тоқсан) сәтті қойылды.")
                redirect_url = reverse('add_exam_grade')
                if selected_class_id: redirect_url += f'?class_id={selected_class_id}'
                return redirect(redirect_url)
            except (IntegrityError, ValidationError) as e:
                if isinstance(e, IntegrityError): form.add_error(None, 'Бұл оқушыға осы пәннен осы тоқсанда бұл БЖБ/ТЖБ түріне баға бұрын қойылған болуы мүмкін.')
                elif isinstance(e, ValidationError):
                     if hasattr(e, 'error_dict'):
                         for field, errors in e.message_dict.items(): form.add_error(field if field != '__all__' else None, errors)
                     else: form.add_error(None, e.messages)
                messages.error(request, "Бағаны сақтау мүмкін болмады.")
            except Exception as e: messages.error(request, f"Бағаны сақтау кезінде күтпеген қате: {e}")
        else:
            # POST кезінде форма жарамсыз болса, студенттер тізімін қайта орнату
            form.fields['student'].queryset = students_queryset
            messages.error(request, "Форма толтыруда қателер бар. Өрістерді тексеріңіз.")
    else: # GET
        form = ExamGradeForm(initial=initial_data, school=user_school, user=user)
        form.fields['student'].queryset = students_queryset

    context = {
        'form': form, 'teacher_classes': teacher_classes, 'selected_class': selected_class,
        'students_count': students_queryset.count(), 'show_form': show_form,
        'current_view': 'add_exam_grade'
    }
    # --- ДЕБАГГИНГ БАСЫ ---
    print(f"--- add_exam_grade: Rendering context: show_form={show_form}, students_count={students_queryset.count()}")
    # --- ДЕБАГГИНГ СОҢЫ ---
    return render(request, 'add_exam_grades.html', context)


# ==================================
# ЕСКІРГЕН VIEWS (РЕДИРЕКТТЕР)
# ==================================
# (Өзгеріссіз)
@login_required
def schedule(request): messages.info(request, "Кесте енді жеке кабинетте ('Дашборд') қолжетімді."); return redirect('dashboard_schedule')
@login_required
def daily_grades(request, class_id=None): messages.info(request, "Бағалар енді жеке кабинетте ('Дашборд') қолжетімді."); return redirect('dashboard_grades')
@login_required
def exam_grades(request, class_id=None): messages.info(request, "БЖБ/ТЖБ бағалары енді жеке кабинетте ('Дашборд') қолжетімді."); return redirect('dashboard_grades')
@login_required
def journal(request):
    messages.info(request, "Журнал функциялары енді жеке кабинетте ('Дашборд') және 'Баға қою' беттерінде қолжетімді.")
    if is_teacher(request.user): return redirect('add_daily_grade')
    elif is_student(request.user) or is_parent(request.user): return redirect('dashboard_grades')
    else: return redirect('dashboard_schedule')
@login_required
def teacher_schedule(request): messages.info(request, "Сіздің кестеңіз енді жеке кабинетте ('Дашборд') қолжетімді."); return redirect('dashboard_schedule')