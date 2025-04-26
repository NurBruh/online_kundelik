# kundelik/views.py

from datetime import date, timedelta, datetime
from collections import defaultdict

from django.core.exceptions import ValidationError, PermissionDenied # PermissionDenied қосылды
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth import views as auth_views, login, logout, authenticate
from django.contrib import messages
from django.urls import reverse_lazy, reverse
from django import forms
from django.forms import inlineformset_factory # Формсеттер үшін
from django.utils import timezone
from django.db import IntegrityError, transaction # Транзакциялар үшін
from django.db.models import Avg, Sum, Prefetch
from django.http import Http404, HttpResponseForbidden # Қателер және рұқсаттар үшін
import math

# --- Импорты моделей ---
from .models import (
    User, UserProfile, School, Class, Subject,
    Schedule, DailyGrade, ExamGrade,
    Assessment, Question, Choice, Submission, Answer # Жаңа модельдер
)
# --- Импорты форм ---
from .forms import (
    UserRegistrationForm, CustomAuthenticationForm, SchoolForm,
    ClassForm, SubjectForm, ScheduleForm, DailyGradeForm, ExamGradeForm,
    UserEditForm, UserProfileEditForm,
    AssessmentForm, QuestionForm, BaseQuestionFormSet,
    ChoiceForm, # <--- ChoiceForm импортталған
    SubmissionForm, GradeSubmissionForm
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
    today = ref_date if ref_date else date.today()
    year = today.year
    school_year_start_year = year if today.month >= 9 else year - 1
    # Оқу жылының басталу және аяқталу күндерін нақтылау қажет болуы мүмкін
    term1_start = date(school_year_start_year, 9, 1); term1_end = date(school_year_start_year, 10, 31) # Шамамен
    term2_start = date(school_year_start_year, 11, 8); term2_end = date(school_year_start_year, 12, 31) # Шамамен
    term3_start = date(school_year_start_year + 1, 1, 11); term3_end = date(school_year_start_year + 1, 3, 20) # Шамамен
    term4_start = date(school_year_start_year + 1, 4, 1); term4_end = date(school_year_start_year + 1, 5, 25) # Шамамен
    if term1_start <= today <= term1_end: return 1
    if term2_start <= today <= term2_end: return 2
    if term3_start <= today <= term3_end: return 3
    if term4_start <= today <= term4_end: return 4
    return None # Каникул немесе белгісіз уақыт

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
                        # Тоқсандық бағаны есептеу логикасын күрделендіру керек болуы мүмкін
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

# --- Заглушки/Редиректы ---
@login_required
def dashboard_exams_view(request):
    if is_student(request.user): return redirect('list_assigned_assessments')
    if is_teacher(request.user): return redirect('list_assessments') # Мұғалімді Assessment тізіміне жіберу
    messages.info(request, "Бағалау (БЖБ/ТЖБ) беті.")
    return redirect('dashboard_schedule') # Немесе басқа әдепкі бет

@login_required
def dashboard_contact_teacher_view(request): messages.info(request, "Бұл бөлім ('Мұғаліммен байланыс') әзірленуде."); return redirect('dashboard_schedule')
@login_required
def dashboard_settings_view(request): messages.info(request, "Бұл бөлім ('Баптаулар') әзірленуде."); return redirect('dashboard_profile')
@login_required
def profile_page_view(request): return redirect('dashboard_profile')

# ==================================
# ҚОСУ ОПЕРАЦИЯЛАРЫ
# ==================================
# --- Декораторлар ---
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
            user = form.save(); UserProfile.objects.get_or_create(user=user)
            parent_of_user = form.cleaned_data.get('parent_of')
            if parent_of_user: user.parent_of = parent_of_user; user.save(update_fields=['parent_of'])
            messages.success(request, f"Пайдаланушы '{user.username}' сәтті қосылды."); return redirect('add_person')
        else: messages.error(request, "Форма толтыруда қателер бар.")
    else: form = UserRegistrationForm(user=request.user)
    context = {'form': form, 'current_view': 'add_person'}; return render(request, 'add_person.html', context)

@login_required
@user_passes_test(lambda u: u.is_superuser, login_url='home')
def add_school(request):
    if request.method == 'POST':
        form = SchoolForm(request.POST)
        if form.is_valid(): form.save(); messages.success(request, "Мектеп сәтті қосылды."); return redirect('add_school')
        else: messages.error(request, "Форма толтыруда қателер бар.")
    else: form = SchoolForm()
    context = {'form': form, 'current_view': 'add_school'}; return render(request, 'add_school.html', context)

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
    else: form = ClassForm(school=school_filter)
    context = {'form': form, 'current_view': 'add_class'}; return render(request, 'add_class.html', context)

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
    else: form = SubjectForm(school=school_filter)
    context = {'form': form, 'current_view': 'add_subject'}; return render(request, 'add_subject.html', context)

# --- add_schedule (Өзгеріссіз) ---
@login_required
@school_staff_required
def add_schedule(request):
    user = request.user
    user_school = getattr(user, 'school', None)
    if not user.is_superuser and not user_school: messages.error(request, "Кесте элементін қосу үшін мектепке тіркелуіңіз керек."); return redirect('dashboard_profile')
    school_filter = user_school if not user.is_superuser else None
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
                schedule_item.full_clean(); schedule_item.save()
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
    else: form = ScheduleForm(initial=initial_data, school=school_filter, user=user)
    context = {'form': form, 'current_view': 'add_schedule'}; return render(request, 'add_schedule.html', context)

# --- add_daily_grade, add_exam_grade (Өзгеріссіз) ---
@login_required
@teacher_required
def add_daily_grade(request):
    user = request.user
    user_school = getattr(user, 'school', None)
    if not user_school: messages.error(request, "Баға қою үшін мектепке тіркелуіңіз керек."); return redirect('dashboard_profile')
    teacher_classes = Class.objects.filter(school=user_school).order_by('name')
    selected_class_id_str = request.GET.get('class_id') or request.POST.get('selected_class_id')
    selected_class_id = None; selected_class = None
    students_queryset = User.objects.none(); show_form = False
    if selected_class_id_str and selected_class_id_str.isdigit():
        try:
            selected_class_id = int(selected_class_id_str)
            selected_class = Class.objects.get(pk=selected_class_id)
            if not request.user.is_superuser and selected_class.school != user_school: messages.error(request, "Бұл сынып сіздің мектебіңізге жатпайды."); selected_class = None; selected_class_id = None
            else:
                 students_queryset = User.objects.filter(role='student',school=selected_class.school,userprofile__school_class=selected_class).select_related('userprofile').order_by('last_name', 'first_name')
                 if students_queryset.exists(): show_form = True
                 else: messages.warning(request, f"Таңдалған сыныпта ('{selected_class.name}') тіркелген оқушылар табылмады.")
        except Class.DoesNotExist: messages.error(request, f"Сынып табылмады (ID: {selected_class_id_str})."); selected_class_id = None; selected_class = None
    elif selected_class_id_str is not None and selected_class_id_str != "": messages.error(request, f"Жарамсыз сынып идентификаторы: '{selected_class_id_str}'."); selected_class_id = None; selected_class = None
    initial_data = {'teacher': user}
    subject_id_get = request.GET.get('subject'); date_str_get = request.GET.get('date')
    if subject_id_get: initial_data['subject'] = subject_id_get
    if date_str_get:
        initial_data['date'] = date_str_get
        try:
            grade_date = datetime.strptime(date_str_get, '%Y-%m-%d').date(); term_for_date = get_current_term(grade_date)
            if term_for_date: initial_data['term'] = term_for_date
        except ValueError: pass
    if request.method == 'POST':
        if not show_form:
             messages.error(request, "Баға қою үшін жарамды сынып таңдалып, онда оқушылар болуы керек.")
             redirect_url = reverse('add_daily_grade');
             if selected_class_id: redirect_url += f'?class_id={selected_class_id}'
             return redirect(redirect_url)
        form = DailyGradeForm(request.POST, school=user_school, user=user); form.fields['student'].queryset = students_queryset
        if form.is_valid():
            grade = form.save(commit=False); grade.teacher = user
            try:
                grade.full_clean(); grade.save()
                messages.success(request, f"Баға ({grade.grade}) оқушы {grade.student.get_full_name()} үшін '{grade.subject.name}' пәнінен ({grade.date}) сәтті қойылды.")
                redirect_url = reverse('add_daily_grade');
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
        else: form.fields['student'].queryset = students_queryset; messages.error(request, "Форма толтыруда қателер бар. Өрістерді тексеріңіз.")
    else: form = DailyGradeForm(initial=initial_data, school=user_school, user=user); form.fields['student'].queryset = students_queryset
    context = {'form': form, 'teacher_classes': teacher_classes, 'selected_class': selected_class, 'students_count': students_queryset.count(), 'show_form': show_form, 'current_view': 'add_daily_grade'}
    return render(request, 'add_daily_grades.html', context)

@login_required
@teacher_required
def add_exam_grade(request):
    user = request.user
    user_school = getattr(user, 'school', None)
    if not user_school: messages.error(request, "Баға қою үшін мектепке тіркелуіңіз керек."); return redirect('dashboard_profile')
    teacher_classes = Class.objects.filter(school=user_school).order_by('name')
    selected_class_id_str = request.GET.get('class_id') or request.POST.get('selected_class_id')
    selected_class_id = None; selected_class = None
    students_queryset = User.objects.none(); show_form = False
    if selected_class_id_str and selected_class_id_str.isdigit():
        try:
            selected_class_id = int(selected_class_id_str)
            selected_class = Class.objects.get(pk=selected_class_id)
            if not request.user.is_superuser and selected_class.school != user_school: messages.error(request, "Бұл сынып сіздің мектебіңізге жатпайды."); selected_class = None; selected_class_id = None
            else:
                 students_queryset = User.objects.filter(role='student',school=selected_class.school,userprofile__school_class=selected_class).select_related('userprofile').order_by('last_name', 'first_name')
                 if students_queryset.exists(): show_form = True
                 else: messages.warning(request, f"Таңдалған сыныпта ('{selected_class.name}') тіркелген оқушылар табылмады.")
        except Class.DoesNotExist: messages.error(request, f"Сынып табылмады (ID: {selected_class_id_str})."); selected_class_id = None; selected_class = None
    elif selected_class_id_str is not None and selected_class_id_str != "": messages.error(request, f"Жарамсыз сынып идентификаторы: '{selected_class_id_str}'."); selected_class_id = None; selected_class = None
    initial_data = {'teacher': user}
    current_term_val = get_current_term()
    if current_term_val: initial_data['term'] = current_term_val
    subject_id_get = request.GET.get('subject')
    if subject_id_get: initial_data['subject'] = subject_id_get
    if request.method == 'POST':
        if not show_form:
             messages.error(request, "Баға қою үшін жарамды сынып таңдалып, онда оқушылар болуы керек.")
             redirect_url = reverse('add_exam_grade');
             if selected_class_id: redirect_url += f'?class_id={selected_class_id}'
             return redirect(redirect_url)
        form = ExamGradeForm(request.POST, school=user_school, user=user); form.fields['student'].queryset = students_queryset
        if form.is_valid():
            grade = form.save(commit=False); grade.teacher = user
            try:
                grade.full_clean(); grade.save()
                messages.success(request, f"{grade.get_exam_type_display()} бағасы ({grade.grade}/{grade.max_grade}) оқушы {grade.student.get_full_name()} үшін '{grade.subject.name}' пәнінен ({grade.term}-тоқсан) сәтті қойылды.")
                redirect_url = reverse('add_exam_grade');
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
        else: form.fields['student'].queryset = students_queryset; messages.error(request, "Форма толтыруда қателер бар. Өрістерді тексеріңіз.")
    else: form = ExamGradeForm(initial=initial_data, school=user_school, user=user); form.fields['student'].queryset = students_queryset
    context = {'form': form, 'teacher_classes': teacher_classes, 'selected_class': selected_class, 'students_count': students_queryset.count(), 'show_form': show_form, 'current_view': 'add_exam_grade'}
    return render(request, 'add_exam_grades.html', context)

# ==================================
# ЖАҢА VIEWS: БЖБ/ТЖБ (ASSESSMENT)
# ==================================

# --- ★★★ create_assessment (Нұсқалар формсетімен жаңартылған) ★★★ ---
@login_required
@teacher_required
@transaction.atomic # Транзакцияны осы жерге қоюға болады
def create_assessment(request):
    user = request.user
    user_school = getattr(user, 'school', None)
    if not user_school and not user.is_superuser:
        messages.error(request, "БЖБ/ТЖБ құру үшін мектепке тіркелуіңіз керек.")
        return redirect('dashboard_schedule')

    # Сұрақтар формсетін анықтау
    QuestionFormSet = inlineformset_factory(
        Assessment, Question, form=QuestionForm, formset=BaseQuestionFormSet,
        fields=('text', 'question_type', 'points', 'order'), extra=1, can_delete=True
    )
    # Нұсқалар формсетін анықтау (ChoiceForm бұрын импортталған болуы керек)
    ChoiceFormSetInline = inlineformset_factory(
        Question, Choice, form=ChoiceForm,
        fields=('text', 'is_correct'), extra=1, can_delete=True
    )

    if request.method == 'POST':
        assessment_form = AssessmentForm(request.POST, school=user_school, user=user)
        # Сұрақтар формсетін POST деректерімен құру
        question_formset = QuestionFormSet(request.POST, prefix='questions')

        # Нұсқалар формсеттерін сақтауға арналған сөздік
        choice_formsets_dict = {}
        is_valid_overall = assessment_form.is_valid() and question_formset.is_valid()

        if is_valid_overall:
            # Сұрақтар формсетіндегі әр форма үшін нұсқалар формсетін тексеру
            for q_form in question_formset:
                # Тек жарамды және жойылмайтын сұрақтарды тексереміз
                if q_form.is_valid() and not q_form.cleaned_data.get('DELETE'):
                    # Егер сұрақ типі нұсқаларды қажет етсе
                    if q_form.cleaned_data.get('question_type') in ['MCQ', 'MAQ', 'TF']:
                        prefix = f'choices-questions-{q_form.prefix}'
                        # Нұсқалар формсетін POST деректерімен құру
                        choice_formset = ChoiceFormSetInline(request.POST, prefix=prefix) # instance әлі жоқ
                        choice_formsets_dict[q_form.prefix] = choice_formset
                        # Нұсқалар формсетінің жарамдылығын тексеру
                        if not choice_formset.is_valid():
                            is_valid_overall = False
                            print(f"Нұсқа формсетіндегі қателер (prefix {q_form.prefix}): {choice_formset.errors}")
                            print(f"Нұсқа формсетінің формадан тыс қателері: {choice_formset.non_form_errors()}")

        if is_valid_overall:
            try:
                # with transaction.atomic(): # Декоратор бар
                # 1. Негізгі бағалауды сақтау (әлі DB-ға жазбай)
                assessment = assessment_form.save(commit=False)
                assessment.teacher = user # Авторды белгілеу
                # Мектепті тексеру (edit_assessment-тегідей)
                if not user_school and user.is_superuser:
                    selected_class = assessment_form.cleaned_data.get('school_class')
                    if not (selected_class and selected_class.school): assessment_form.add_error('school_class', "Мектепті анықтау үшін сыныпты таңдау қажет."); raise ValidationError("Сынып таңдалмаған.")
                elif user_school:
                     selected_class = assessment_form.cleaned_data.get('school_class')
                     if selected_class and selected_class.school != user_school: assessment_form.add_error('school_class', "Бұл сынып сіздің мектебіңізге жатпайды."); raise ValidationError("Сынып сәйкес емес.")
                else: raise ValidationError("Мектеп анықталмаған.")

                assessment.save() # Негізгі бағалауды сақтау (PK алу үшін)

                # 2. Сұрақтарды сақтау
                questions_to_save = question_formset.save(commit=False)
                saved_questions_map = {}
                for q_form in question_formset:
                    if not q_form.cleaned_data.get('DELETE'):
                        q_instance = q_form.save(commit=False)
                        q_instance.assessment = assessment # Сұрақты бағалауға байлау
                        q_instance.save() # Сұрақты сақтау
                        saved_questions_map[q_form.prefix] = q_instance # Кейін нұсқаларды байлау үшін сақтау

                # 3. Нұсқаларды сақтау
                for q_prefix, cfset in choice_formsets_dict.items():
                    target_question = saved_questions_map.get(q_prefix)
                    if target_question:
                        choices = cfset.save(commit=False)
                        for choice in choices:
                            choice.question = target_question # Нұсқаны сұраққа байлау
                            choice.save() # Нұсқаны сақтау
                        # cfset.save_m2m() # Егер Choice моделінде M2M болса
                    else:
                        # Егер сұрақ өшірілмесе, бірақ табылмаса, бұл қате болуы мүмкін
                        original_q_form = next((form for form in question_formset if form.prefix == q_prefix), None)
                        if not (original_q_form and original_q_form.cleaned_data.get('DELETE')):
                             print(f"ҚАТЕ (жасау): Нұсқалар ({q_prefix}) үшін сәйкес сұрақ табылмады!")

                # 4. Жоюға белгіленген сұрақтарды өшіру (қажет емес, өйткені олар сақталмады)

                # 5. Максималды баллды есептеу
                assessment.recalculate_max_score()

                messages.success(request, f"Бағалау '{assessment.title}' сәтті құрылды.")
                # Жасалғаннан кейін өңдеу бетіне өту
                return redirect('edit_assessment', pk=assessment.pk)
            except ValidationError as e: messages.error(request, f"Форма толтыруда қателер бар: {e}")
            except Exception as e: messages.error(request, f"Бағалауды сақтау кезінде күтпеген қате: {e}"); print(f"Error creating assessment: {e}")
        else:
            # Егер формалар жарамсыз болса, қателермен бірге қайта көрсету
             if not messages.get_messages(request): # Қайталанатын хабарламаларды болдырмау
                  messages.error(request, "Форма толтыруда қателер бар. Тексеріңіз.")
    else: # GET request
        assessment_form = AssessmentForm(school=user_school, user=user)
        question_formset = QuestionFormSet(prefix='questions')
        choice_formsets_dict = {} # GET кезінде бос

    # --- ★★★ Контекстті дайындау (GET немесе POST қатесі үшін) ★★★ ---
    questions_with_forms = []
    for q_form in question_formset:
        # Әр сұрақ үшін сәйкес нұсқалар формсетін дайындау
        prefix = f'choices-questions-{q_form.prefix}'
        choice_formset_instance = None

        # Егер POST болса және осы сұрақ үшін нұсқа деректері болса
        if request.method == 'POST' and q_form.prefix in choice_formsets_dict:
            choice_formset_instance = choice_formsets_dict[q_form.prefix]
        # Егер POST болса, бірақ негізгі форма қате болса да, нұсқа формсетін құру
        elif request.method == 'POST':
            # Бұл жағдайда instance жоқ, өйткені жаңадан жасалуда
             choice_formset_instance = ChoiceFormSetInline(request.POST, prefix=prefix)
             choice_formset_instance.is_valid() # Қателерді жүктеу үшін
        # GET сұранысы кезінде бос нұсқа формсетін құру
        else:
            choice_formset_instance = ChoiceFormSetInline(prefix=prefix)

        questions_with_forms.append({
            'question_form': q_form,
            'choice_formset': choice_formset_instance,
            'instance': q_form.instance # Жаңа сұрақ үшін бұл None болады
        })

    # Шаблонда жаңа нұсқа қосуға арналған бос форма үлгісі
    empty_choice_form_for_template = ChoiceFormSetInline.empty_form

    context = {
        'assessment_form': assessment_form,
        'question_formset': question_formset, # Management form үшін қажет
        'questions_with_forms': questions_with_forms, # Итерация үшін жаңартылған контекст
        'empty_choice_form_for_template': empty_choice_form_for_template, # JS үшін бос нұсқа үлгісі
        'current_view': 'create_assessment',
        'page_title': "Жаңа БЖБ/ТЖБ құру"
    }
    # Шаблон атауын тексеріңіз (assessment_form.html дұрыс)
    return render(request, 'assessment/assessment_form.html', context)
# --- ★★★ create_assessment соңы ★★★ ---

@login_required
@teacher_required
def edit_assessment(request, pk):
    assessment = get_object_or_404(Assessment, pk=pk)
    # Тек автор немесе суперадмин өңдей алады
    if assessment.teacher != request.user and not request.user.is_superuser:
        messages.error(request, "Бұл бағалауды өңдеуге рұқсатыңыз жоқ.")
        return redirect('list_assessments') # Немесе басқа бетке жіберу

    user_school = getattr(request.user, 'school', None)

    QuestionFormSet = inlineformset_factory(
        Assessment, Question, form=QuestionForm, formset=BaseQuestionFormSet,
        fields=('text', 'question_type', 'points', 'order'), extra=0, can_delete=True # extra=0 өңдеуде
    )
    # Нұсқалар үшін формсет фабрикасын алдын ала анықтау
    ChoiceFormSetInline = inlineformset_factory(
        Question, Choice, form=ChoiceForm,
        fields=('text', 'is_correct'), extra=1, can_delete=True
    )

    if request.method == 'POST':
        assessment_form = AssessmentForm(request.POST, instance=assessment, school=user_school, user=request.user)
        question_formset = QuestionFormSet(request.POST, instance=assessment, prefix='questions')

        choice_formsets_dict = {} # Нұсқа формсеттерін сақтау үшін
        is_valid_overall = assessment_form.is_valid() and question_formset.is_valid()

        if is_valid_overall:
             # Алдымен негізгі формалар жарамды болса, нұсқа формсеттерін тексереміз
             for q_form in question_formset:
                 # Тек жарамды, жойылмаған және нұсқалары бар сұрақтарды тексереміз
                 if q_form.is_valid() and not q_form.cleaned_data.get('DELETE'):
                     if q_form.cleaned_data.get('question_type') in ['MCQ', 'MAQ', 'TF']:
                         # Әр сұрақ нұсқасының формсеті үшін бірегей префикс
                         prefix = f'choices-questions-{q_form.prefix}'
                         # POST деректерімен нұсқа формсетін құру
                         choice_formset = ChoiceFormSetInline(request.POST, instance=q_form.instance, prefix=prefix)
                         choice_formsets_dict[q_form.prefix] = choice_formset # Кейін сақтау үшін сақтаймыз
                         # Егер бір нұсқа формсеті жарамсыз болса, жалпы жарамдылықты false етеміз
                         if not choice_formset.is_valid():
                             is_valid_overall = False
                             print(f"Нұсқа формсетіндегі қателер (prefix {q_form.prefix}): {choice_formset.errors}")
                             print(f"Нұсқа формсетінің формадан тыс қателері: {choice_formset.non_form_errors()}")

        if is_valid_overall:
            try:
                with transaction.atomic():
                    # 1. Бағалауды сақтау
                    saved_assessment = assessment_form.save()

                    # 2. Сұрақтарды сақтау
                    questions_to_save = question_formset.save(commit=False) # DB-ға жазбай, объектілерді алу
                    saved_questions_map = {} # Сақталған сұрақтарды prefix арқылы сақтау
                    for q_form in question_formset:
                        # Жойылмаған сұрақтарды сақтаймыз
                        if q_form.has_changed() and not q_form.cleaned_data.get('DELETE'):
                             q_instance = q_form.save(commit=False)
                             q_instance.assessment = saved_assessment # Байланысты орнату
                             q_instance.save() # Сұрақты DB-ға сақтау
                             saved_questions_map[q_form.prefix] = q_instance # Картаға қосу
                        elif q_form.instance.pk and not q_form.cleaned_data.get('DELETE'):
                             # Егер форма өзгермесе, бірақ жойылмаса, бұрынғы instance-ты қолданамыз
                             saved_questions_map[q_form.prefix] = q_form.instance

                    # 3. Нұсқа формсеттерін сақтау
                    for q_prefix, cfset in choice_formsets_dict.items():
                         target_question = saved_questions_map.get(q_prefix)
                         # Егер сәйкес сақталған сұрақ болса ғана нұсқаларды сақтаймыз
                         if target_question:
                             cfset.instance = target_question # Нұсқаларды сұраққа байлау
                             cfset.save() # Нұсқаларды сақтау
                         else:
                            # Егер сәйкес сұрақ табылмаса (өшірілген болуы мүмкін), ештеңе істемейміз
                            original_q_form = next((form for form in question_formset if form.prefix == q_prefix), None)
                            if not (original_q_form and original_q_form.cleaned_data.get('DELETE')):
                                 print(f"Назар аударыңыз (сақтау): Нұсқалар ({q_prefix}) үшін сәйкес сұрақ сақталмаған болуы мүмкін.")

                    # 4. Жоюға белгіленген сұрақтарды өшіру (формсеттің save методын шақыру арқылы)
                    question_formset.save()

                    # 5. Максималды баллды қайта есептеу
                    saved_assessment.recalculate_max_score()

                messages.success(request, f"Бағалау '{saved_assessment.title}' сәтті жаңартылды.")
                return redirect('edit_assessment', pk=saved_assessment.pk) # Сол бетте қалу

            except Exception as e:
                messages.error(request, f"Бағалауды сақтау кезінде күтпеген қате: {e}")
                print(f"Error saving assessment and related forms: {e}")
                # Қате болған жағдайда, формалар сол күйінде көрсетіледі
        else:
             # Егер қателер болса және хабарлама жоқ болса, жалпы қате хабарламасын қосу
             if not messages.get_messages(request):
                  messages.error(request, "Форма толтыруда қателер бар. Тексеріңіз.")

    # GET сұранысы немесе POST қатесі кезінде
    else:
        assessment_form = AssessmentForm(instance=assessment, school=user_school, user=request.user)
        question_formset = QuestionFormSet(instance=assessment, prefix='questions')
        choice_formsets_dict = {} # GET кезінде бос

    # Контекстті дайындау (GET немесе POST қатесі үшін)
    questions_with_forms = []
    for q_form in question_formset:
        choice_formset_instance = None
        # Нұсқа формсеті үшін бірегей префикс
        prefix_for_choices = f'choices-questions-{q_form.prefix}'

        # POST кезінде қате болса, қолданушы енгізген деректермен формсетті көрсету
        if request.method == 'POST' and q_form.prefix in choice_formsets_dict:
            choice_formset_instance = choice_formsets_dict[q_form.prefix]
        elif request.method == 'POST' and q_form.is_valid() and not q_form.cleaned_data.get('DELETE') and q_form.cleaned_data.get('question_type') in ['MCQ', 'MAQ', 'TF']:
            # Егер POST болса, бірақ алдыңғы if орындалмаса (мысалы, негізгі форма қате)
             choice_formset_instance = ChoiceFormSetInline(request.POST, instance=q_form.instance, prefix=prefix_for_choices)
             choice_formset_instance.is_valid() # Қателерді жүктеу үшін
        # GET кезінде немесе жаңа сұрақ үшін (instance.pk жоқ)
        elif q_form.instance and q_form.instance.pk and q_form.instance.question_type in ['MCQ', 'MAQ', 'TF']:
             choice_formset_instance = ChoiceFormSetInline(instance=q_form.instance, prefix=prefix_for_choices)
        # Жаңа сұрақ үшін де формсет құруға болады (бірақ instance болмайды)
        elif not q_form.instance.pk and request.method != 'POST' and q_form.initial.get('question_type') in ['MCQ','MAQ','TF']:
             choice_formset_instance = ChoiceFormSetInline(prefix=prefix_for_choices)


        questions_with_forms.append({
            'question_form': q_form,
            'choice_formset': choice_formset_instance,
            'instance': q_form.instance # Шаблонда қолдану үшін
        })

    # Шаблонда жаңа нұсқа қосуға арналған бос форма
    empty_choice_form_for_template = ChoiceFormSetInline.empty_form

    context = {
        'assessment': assessment,
        'assessment_form': assessment_form,
        'question_formset': question_formset, # Негізгі сұрақтар формсеті
        'questions_with_forms': questions_with_forms, # Сұрақ формасы + нұсқа формсеті
        'empty_choice_form_for_template': empty_choice_form_for_template, # JS үшін бос нұсқа формасы
        'current_view': 'edit_assessment',
        'page_title': f"Бағалауды өңдеу: {assessment.title}" # Бет тақырыбы
    }
    # Бұл жерде edit формасын көрсету керек
    return render(request, 'assessment/assessment_edit_form.html', context)


# --- list_assessments (Мұғалім үшін) ---
@login_required
@teacher_required # Тек мұғалімдерге
def list_assessments(request):
    user = request.user
    # Мұғалім құрған бағалауларды тізімдеу
    assessments = Assessment.objects.filter(teacher=user).select_related(
        'subject', 'school_class', 'subject__school'
    ).order_by('-created_at')
    context = {
        'assessments': assessments,
        'current_view': 'list_assessments', # Менюді белсенді ету үшін
        'page_title': "Менің бағалауларым (БЖБ/ТЖБ)"
    }
    return render(request, 'assessment/assessment_list.html', context)

# ==================================
# ОҚУШЫ ҮШІН БЖБ/ТЖБ VIEWS
# ==================================
@login_required
@user_passes_test(is_student)
def list_assigned_assessments(request):
    student = request.user; student_class = None
    try: student_class = student.userprofile.grade
    except (UserProfile.DoesNotExist, AttributeError): messages.warning(request, "Профиліңізде сынып көрсетілмеген."); return redirect('dashboard_profile')
    if not student_class: messages.warning(request, "Сіз ешқандай сыныпқа тіркелмегенсіз."); return redirect('dashboard_profile')
    now = timezone.now()
    # Оқушының сыныбына тағайындалған, белсенді бағалауларды алу
    assessments = Assessment.objects.filter(
        school_class=student_class,
        is_active=True,
    ).select_related('subject', 'teacher').order_by('-created_at', 'subject') # Жаңаларын бірінші көрсету

    # Оқушының тапсырмаларын алу (оптимизация)
    submissions = Submission.objects.filter(
        student=student,
        assessment__in=assessments # Тек көрсетілетін бағалаулар бойынша
    ).values('assessment_id', 'pk', 'is_graded', 'score') # Қажетті өрістерді ғана алу

    # Тапсырылған және бағаланған картасын жасау
    submitted_map = {}
    for s in submissions:
        submitted_map[s['assessment_id']] = {'submission_pk': s['pk'], 'is_graded': s['is_graded'], 'score': s['score']}

    context = {
        'assessments': assessments,
        'submitted_map': submitted_map,
        'now': now, # Мерзімді тексеру үшін
        'current_view': 'list_assigned_assessments',
        'page_title': "Маған тағайындалған БЖБ/ТЖБ"
    }
    return render(request, 'assessment/assessment_assigned_list.html', context)

@login_required
@user_passes_test(is_student)
@transaction.atomic # Форма сақталғанда бірнеше DB операциясы болуы мүмкін
def take_assessment(request, pk):
    student = request.user
    # Белсенді және select_related арқылы байланысты модельдерді жүктеу
    assessment = get_object_or_404(
        Assessment.objects.select_related('school_class', 'subject'),
        pk=pk,
        is_active=True
    )

    # Оқушының дұрыс сыныпта екенін тексеру
    try:
        profile = student.userprofile
        if not profile or profile.grade != assessment.school_class:
             messages.error(request, "Сіз бұл тапсырманы орындай алмайсыз (басқа сынып немесе профиль қатесі).")
             return redirect('list_assigned_assessments')
    except UserProfile.DoesNotExist:
        messages.error(request, "Профиліңіз табылмады. Администраторға хабарласыңыз.")
        return redirect('list_assigned_assessments')
    except AttributeError:
         messages.error(request, "Профиліңізде сынып көрсетілмеген.")
         return redirect('dashboard_profile')

    # Тапсырма бұрын тапсырылған ба?
    existing_submission = Submission.objects.filter(assessment=assessment, student=student).first()
    if existing_submission:
        messages.info(request, f"Сіз бұл тапсырманы ('{assessment.title}') бұрын тапсырғансыз.")
        return redirect('view_submission_result', pk=existing_submission.pk)

    # Мерзімі өтіп кеткен бе?
    if assessment.due_date and timezone.now() > assessment.due_date:
        messages.error(request, f"Тапсырманы ('{assessment.title}') орындау мерзімі өтіп кетті.")
        return redirect('list_assigned_assessments')

    # Сұрақтарды алу
    questions = assessment.questions.order_by('order')

    if request.method == 'POST':
        form = SubmissionForm(request.POST, request.FILES, assessment=assessment, student=student)
        if form.is_valid():
            try:
                # Форманың save әдісі Submission объектісін қайтарады
                submission = form.save(commit=True) # commit=True маңызды
                messages.success(request, f"Тапсырма ('{assessment.title}') сәтті тапсырылды!")
                # Нәтиже бетіне жіберу
                return redirect('view_submission_result', pk=submission.pk)
            except Exception as e:
                messages.error(request, f"Тапсырманы сақтау кезінде қате: {e}")
                print(f"Error saving submission: {e}")
                # Қате болса, форма қайта көрсетіледі
        else:
            messages.error(request, "Форма толтыруда қателер бар. Жауаптарыңызды тексеріңіз.")
            # Қате болса, форма қайта көрсетіледі (төмендегі кодпен)
    else: # GET request
        form = SubmissionForm(assessment=assessment, student=student)

    # Шаблонға жіберу үшін сұрақтарды форма өрістерімен біріктіру
    questions_with_fields = []
    for question in questions:
        q_fields = {}
        field_key_base = f'question_{question.pk}'
        try:
            # Сұрақ түріне байланысты формадағы өрісті алу
            if question.question_type in ['MCQ', 'TF']:
                q_fields['choice'] = form[f'{field_key_base}_choice']
            elif question.question_type == 'MAQ':
                q_fields['choices'] = form[f'{field_key_base}_choices']
            elif question.question_type == 'OPEN':
                q_fields['text'] = form[f'{field_key_base}_text']
                q_fields['file'] = form[f'{field_key_base}_file']
        except KeyError:
            # Егер формада өріс табылмаса (күтпеген жағдай)
            print(f"Назар аударыңыз: Сұрақ {question.pk} (тип: {question.question_type}) үшін SubmissionForm-да өріс табылмады.")
        questions_with_fields.append({'question': question, 'fields': q_fields})

    context = {
        'assessment': assessment,
        'form': form, # POST кезінде қателермен немесе GET кезінде бос форма
        'questions_with_fields': questions_with_fields,
        'current_view': 'take_assessment',
        'page_title': f"БЖБ/ТЖБ өту: {assessment.title}"
    }
    return render(request, 'assessment/assessment_take.html', context)


# --- ★★★ view_submission_result (Шекті мәндермен) ★★★ ---
@login_required
# @user_passes_test(is_student) # Мұғалім де көре алатындай етіп, тексеруді ішке көшірдік
def view_submission_result(request, pk):
    submission = get_object_or_404(
        Submission.objects.select_related(
            'assessment', 'assessment__subject', 'student',
            'student__userprofile', 'student__userprofile__school_class'
        ),
        pk=pk
    )
    assessment = submission.assessment

    # Қауіпсіздік: Тек тапсырған оқушы немесе бағалау авторы (мұғалім) көре алады
    if request.user != submission.student and request.user != assessment.teacher and not request.user.is_superuser:
        raise PermissionDenied("Бұл тапсырма нәтижесін көруге рұқсатыңыз жоқ.")

    answers = Answer.objects.filter(submission=submission).select_related(
        'question', 'selected_choice'
    ).prefetch_related(
        'selected_choices', 'question__choices'
    ).order_by('question__order')

    correct_choices_ids = set(
        Choice.objects.filter(question__assessment=assessment, is_correct=True)
                      .values_list('id', flat=True)
    )
    selected_choices_map = defaultdict(set)
    for ans in answers:
        if ans.question.question_type == 'MAQ':
            selected_choices_map[ans.question.pk] = set(choice.pk for choice in ans.selected_choices.all())

    # Шекті мәндерді есептеу (шаблондағы көбейтуді болдырмау үшін)
    threshold_80 = None
    threshold_50 = None
    if assessment.max_score is not None and assessment.max_score > 0:
        try:
            threshold_80 = float(assessment.max_score) * 0.8
            threshold_50 = float(assessment.max_score) * 0.5
        except (TypeError, ValueError):
            print(f"Назар аударыңыз: Бағалау {assessment.pk} үшін шекті мәндерді есептеу мүмкін болмады.")

    context = {
        'submission': submission,
        'assessment': assessment,
        'answers': answers,
        'correct_choices_ids': correct_choices_ids,
        'selected_choices_map': selected_choices_map,
        'threshold_80': threshold_80, # ★★★ Контекстке қосылды ★★★
        'threshold_50': threshold_50, # ★★★ Контекстке қосылды ★★★
        'current_view': 'view_submission_result',
        'page_title': f"Нәтиже: {assessment.title} ({submission.student.get_full_name()})"
    }
    # Шаблон атауы дұрыс екенін тексеріңіз
    return render(request, 'assessment/submission_result.html', context)


# ==================================
# МҰҒАЛІМ ҮШІН БЖБ/ТЖБ БАҒАЛАУ VIEWS
# ==================================
@login_required
@teacher_required
def view_submissions(request, assessment_id):
    assessment = get_object_or_404(
        Assessment.objects.select_related('school_class', 'subject', 'teacher'),
        pk=assessment_id
    )
    if assessment.teacher != request.user and not request.user.is_superuser:
        raise PermissionDenied("Бұл бағалаудың тапсырмаларын көруге рұқсатыңыз жоқ.")

    submissions = Submission.objects.filter(assessment=assessment).select_related(
        'student', 'student__userprofile'
    ).order_by('student__last_name', 'student__first_name')

    context = {
        'assessment': assessment,
        'submissions': submissions,
        'current_view': 'view_submissions',
        'page_title': f"Тапсырмалар: {assessment.title}"
    }
    return render(request, 'assessment/submission_list.html', context)

# --- ★★★ grade_submission (Шекті мәндерді есептеу қажет емес) ★★★ ---
@login_required
@teacher_required
@transaction.atomic # Бірнеше модельді жаңарту мүмкін
def grade_submission(request, submission_id):
    submission = get_object_or_404(
        Submission.objects.select_related(
            'assessment', 'assessment__subject', 'student', 'student__userprofile'
        ),
        pk=submission_id
    )
    assessment = submission.assessment; student = submission.student

    if assessment.teacher != request.user and not request.user.is_superuser:
        raise PermissionDenied("Бұл тапсырманы бағалауға рұқсатыңыз жоқ.")

    answers = Answer.objects.filter(submission=submission).select_related(
        'question', 'selected_choice'
    ).prefetch_related(
        'selected_choices', 'question__choices'
    ).order_by('question__order')

    correct_choices_ids = set(
        Choice.objects.filter(question__assessment=assessment, is_correct=True)
                      .values_list('id', flat=True)
    )
    selected_choices_map = defaultdict(set)
    for ans in answers:
        if ans.question.question_type == 'MAQ':
            selected_choices_map[ans.question.pk] = set(choice.pk for choice in ans.selected_choices.all())

    if request.method == 'POST':
        form = GradeSubmissionForm(request.POST, instance=submission)
        if form.is_valid():
            submission = form.save(commit=False)
            submission.is_graded = True
            submission.graded_at = timezone.now()
            submission.save(update_fields=['score', 'is_graded', 'graded_at'])

            exam_grade, created = ExamGrade.objects.update_or_create(
                student=student, subject=assessment.subject, term=assessment.term, exam_type=assessment.exam_type,
                defaults={
                    'teacher': request.user, 'grade': submission.score,
                    'max_grade': assessment.max_score, 'date': submission.graded_at.date(),
                }
            )
            messages.success(request, f"{student.get_full_name()} оқушысының жұмысы бағаланды ({submission.score}/{assessment.max_score}).")
            return redirect('view_submissions', assessment_id=assessment.id)
        else:
            messages.error(request, "Форма толтыруда қателер бар. Баллды тексеріңіз.")
    else:
        form = GradeSubmissionForm(instance=submission)

    context = {
        'submission': submission, 'assessment': assessment, 'student': student,
        'answers': answers, 'correct_choices_ids': correct_choices_ids,
        'selected_choices_map': selected_choices_map, 'form': form,
        'current_view': 'grade_submission',
        'page_title': f"Бағалау: {assessment.title} ({student.get_full_name()})"
    }
    return render(request, 'assessment/grade_submission.html', context)


# ==================================
# ЕСКІРГЕН VIEWS (РЕДИРЕКТТЕР)
# ==================================
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
    elif is_student(request.user) or is_parent(request.user): return redirect('dashboard_grades') # Оқушы/ата-ананы бағалар бетіне жіберу
    else: return redirect('dashboard_schedule')
@login_required
def teacher_schedule(request): messages.info(request, "Сіздің кестеңіз енді жеке кабинетте ('Дашборд') қолжетімді."); return redirect('dashboard_schedule')