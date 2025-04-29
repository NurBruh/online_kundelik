# kundelik/views.py

from datetime import date, timedelta, datetime
from collections import defaultdict

from django.core.exceptions import ValidationError, PermissionDenied
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth import views as auth_views, login, logout, authenticate
from django.contrib import messages
from django.urls import reverse_lazy, reverse
from django import forms
from django.forms import inlineformset_factory
from django.utils import timezone
from django.db import IntegrityError, transaction
from django.db.models import Avg, Sum, Prefetch, Count
from django.db.models.functions import TruncDate
from django.http import Http404, HttpResponseForbidden
from django.utils.translation import gettext_lazy as _ # <--- ОСЫ ИМПОРТТЫ ОСЫ ЖЕРГЕ ҚОЙЫҢЫЗ

import math # Бұл импортты да басқа стандартты кітапханалармен бірге орналастырған жөн
import json
import logging # Бұл да

logger = logging.getLogger(__name__)

# --- Импорты моделей ---
from .models import (
    User, UserProfile, School, Class, Subject,
    Schedule, DailyGrade, ExamGrade,
    Assessment, Question, Choice, Submission, Answer,
    ActivityLog
)
# --- Импорты форм ---
from .forms import (
    UserRegistrationForm, CustomAuthenticationForm, SchoolForm,
    ClassForm, SubjectForm, ScheduleForm, DailyGradeForm, ExamGradeForm,
    UserEditForm, UserProfileEditForm,
    AssessmentForm, QuestionForm, BaseQuestionFormSet,
    ChoiceForm,
    SubmissionForm, GradeSubmissionForm
)
# ==================================
# КӨМЕКШІ ФУНКЦИЯЛАР ЖӘНЕ ДЕКОРАТОРЛАР
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

def admin_director_required(view_func):
    return user_passes_test(lambda u: is_admin_or_director(u), login_url='login')(view_func)

def teacher_required(view_func):
    return user_passes_test(lambda u: is_teacher(u), login_url='login')(view_func)

def school_staff_required(view_func):
     return user_passes_test(lambda u: is_school_staff(u), login_url='login')(view_func)

def get_current_term(ref_date=None):
    today = ref_date if ref_date else timezone.localdate()
    year = today.year
    school_year_start_year = year if today.month >= 9 else year - 1
    # --- НАСТРОЙТЕ ЭТИ ДАТЫ СОГЛАСНО ВАШЕМУ УЧЕБНОМУ КАЛЕНДАРЮ ---
    term1_start = date(school_year_start_year, 9, 1); term1_end = date(school_year_start_year, 10, 27)
    term2_start = date(school_year_start_year, 11, 7); term2_end = date(school_year_start_year, 12, 29)
    term3_start = date(school_year_start_year + 1, 1, 10); term3_end = date(school_year_start_year + 1, 3, 21)
    term4_start = date(school_year_start_year + 1, 4, 1); term4_end = date(school_year_start_year + 1, 5, 31)
    # --- ---
    if term1_start <= today <= term1_end: return 1
    if term2_start <= today <= term2_end: return 2
    if term3_start <= today <= term3_end: return 3
    if term4_start <= today <= term4_end: return 4
    logger.warning(f"Дата {today} не попадает ни в один из определенных токсанов.")
    return None

def redirect_user_based_on_role(request, user):
    role = getattr(user, 'role', None)
    if role in ['student', 'teacher', 'parent', 'admin', 'director']:
        return redirect('dashboard_schedule')
    elif user.is_staff or user.is_superuser:
         messages.info(request, "Перенаправление в панель администратора сайта.")
         try: admin_url = reverse('admin:index'); return redirect(admin_url)
         except Exception as e:
             logger.error(f"Не удалось получить URL админки ('admin:index'): {e}")
             messages.warning(request, "Не удалось перейти в панель администратора. Перенаправление в профиль.")
             return redirect('dashboard_profile')
    else:
        messages.warning(request, "Сіздің рөліңіз жүйеде анықталмаған. Профиль бетіне бағытталдыңыз.")
        return redirect('dashboard_profile')

def calculate_term_grade(daily_grades_values, sor_grades_list, soch_grade_obj):
    WEIGHT_FB = 0.25; WEIGHT_SOR = 0.25; WEIGHT_SOCH = 0.50
    MIN_DAILY_COUNT = 1; MIN_SOR_COUNT = 1; MIN_SOCH_COUNT = 1
    fb_percentage = None
    if daily_grades_values and len(daily_grades_values) >= MIN_DAILY_COUNT:
        try:
            valid_daily = [g for g in daily_grades_values if isinstance(g, (int, float))]
            if valid_daily: avg_daily = sum(valid_daily) / len(valid_daily); fb_percentage = (avg_daily / 5.0) * 100
            else: logger.warning("Расчет ФО: Нет валидных числовых оценок."); fb_percentage = None
        except ZeroDivisionError: logger.warning("Расчет ФО: Деление на ноль."); fb_percentage = None
        except Exception as e: logger.error(f"Ошибка расчета процента ФО: {e}"); fb_percentage = None
    else: logger.info(f"Недостаточно дневных оценок для ФО ({len(daily_grades_values)}/{MIN_DAILY_COUNT}) или список пуст.")
    sor_percentage = None; valid_sor_count = 0; sor_percentages = []
    for sor in sor_grades_list:
        if sor and isinstance(sor.grade, (int, float)) and sor.max_grade and sor.max_grade > 0:
            try: sor_p = (float(sor.grade) / float(sor.max_grade)) * 100; sor_percentages.append(sor_p); valid_sor_count += 1
            except (TypeError, ValueError, ZeroDivisionError) as e: logger.warning(f"Ошибка при расчете процента для СОР ID {sor.pk}: {e}")
        elif sor: logger.warning(f"Некорректные данные для СОР (ID: {sor.pk}): Оценка={sor.grade}, Макс={sor.max_grade}")
    if valid_sor_count >= MIN_SOR_COUNT and sor_percentages:
        try: sor_percentage = sum(sor_percentages) / len(sor_percentages)
        except ZeroDivisionError: logger.error("Расчет СОР: Деление на ноль."); sor_percentage = None
    else: logger.info(f"Недостаточно СОР для расчета ({valid_sor_count}/{MIN_SOR_COUNT}).")
    soch_percentage = None
    if soch_grade_obj and isinstance(soch_grade_obj.grade, (int, float)) and soch_grade_obj.max_grade and soch_grade_obj.max_grade > 0:
        try: soch_percentage = (float(soch_grade_obj.grade) / float(soch_grade_obj.max_grade)) * 100
        except (TypeError, ValueError, ZeroDivisionError) as e: logger.warning(f"Ошибка при расчете процента для СОЧ ID {soch_grade_obj.pk}: {e}")
    elif soch_grade_obj: logger.warning(f"Некорректные данные для СОЧ (ID: {soch_grade_obj.pk}): Оценка={soch_grade_obj.grade}, Макс={soch_grade_obj.max_grade}")
    else: logger.info(f"Нет СОЧ для расчета (требуется {MIN_SOCH_COUNT}).")
    if sor_percentage is None or soch_percentage is None: logger.info("Невозможно рассчитать итоговую оценку: отсутствует СОР или СОЧ."); return None
    if fb_percentage is None: logger.info("Процент ФО не рассчитан, используется 0% в итоговой формуле."); fb_percentage = 0.0
    try: term_score_percentage = (fb_percentage * WEIGHT_FB) + (sor_percentage * WEIGHT_SOR) + (soch_percentage * WEIGHT_SOCH)
    except TypeError as e: logger.error(f"Ошибка TypeError при расчете итога: {e}."); return None
    final_grade = None
    if term_score_percentage >= 85: final_grade = 5
    elif term_score_percentage >= 65: final_grade = 4
    elif term_score_percentage >= 40: final_grade = 3
    elif term_score_percentage >= 0: final_grade = 2
    else: logger.warning(f"Итоговый процент {term_score_percentage} отрицательный.")
    logger.info(f"Расчет итог. оценки: ФО={fb_percentage:.2f}%, СОР={sor_percentage:.2f}%, СОЧ={soch_percentage:.2f}% -> Итог={term_score_percentage:.2f}% -> Оценка={final_grade}")
    return final_grade

# ==================================
# НЕГІЗГІ БЕТТЕР VIEWS
# ==================================
def home(request):
    """Главная страница (для неаутентифицированных) или редирект."""
    if request.user.is_authenticated: return redirect_user_based_on_role(request, request.user)
    return render(request, 'home.html')
def about(request):
    """Страница 'О нас'."""
    return render(request, 'about_us.html')
def recommendations(request):
    """Страница рекомендаций (заглушка)."""
    messages.info(request, "Бұл бет әзірленуде.")
    return render(request, 'recommendations.html')

# ==================================
# АУТЕНТИФИКАЦИЯ VIEWS
# ==================================
def register(request):
    """Регистрация нового пользователя."""
    if request.user.is_authenticated: return redirect_user_based_on_role(request, request.user)
    if request.method == 'POST':
        form = UserRegistrationForm(request.POST, user=request.user)
        if form.is_valid():
            user = form.save(); UserProfile.objects.get_or_create(user=user)
            parent_of_user = form.cleaned_data.get('parent_of')
            if parent_of_user: user.parent_of = parent_of_user; user.save(update_fields=['parent_of'])
            login(request, user)
            messages.success(request, f"Тіркелу сәтті аяқталды! Қош келдіңіз, {user.first_name or user.username}!")
            return redirect_user_based_on_role(request, user)
        else: messages.error(request, "Тіркелу кезінде қателер пайда болды. Форманы тексеріңіз.")
    else: form = UserRegistrationForm(user=request.user)
    return render(request, 'register.html', {'form': form})

def user_login(request):
    """Вход пользователя."""
    if request.user.is_authenticated: return redirect_user_based_on_role(request, request.user)
    if request.method == 'POST':
        form = CustomAuthenticationForm(request, data=request.POST)
        if form.is_valid():
            user = form.get_user(); login(request, user)
            ActivityLog.objects.create(user=user, activity_type='LOGIN')
            messages.success(request, f"Қош келдіңіз, {user.first_name or user.username}!")
            return redirect_user_based_on_role(request, user)
        else: messages.error(request, "Логин немесе құпия сөз қате.")
    else: form = CustomAuthenticationForm()
    return render(request, 'login.html', {'form': form})

def user_logout(request):
    """Выход пользователя."""
    logout(request); messages.info(request, "Сіз жүйеден сәтті шықтыңыз."); return redirect('home')

class CustomPasswordResetView(auth_views.PasswordResetView):
    """Кастомное представление для запроса сброса пароля."""
    template_name = 'password_reset_form.html'; email_template_name = 'password_reset_email.html'
    subject_template_name = 'password_reset_subject.txt'; success_url = reverse_lazy('password_reset_done')

# ==================================
# ПАЙДАЛАНУШЫ ПАНЕЛІ (ДАШБОРД) VIEWS
# ==================================
@login_required
def dashboard_schedule_view(request):
    """Отображает расписание на неделю для текущего пользователя."""
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
            if not target_class: messages.warning(request, "Профиліңізде сынып көрсетілмеген, кесте көрсетілмейді."); schedule_filters = None
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
    except Exception as e: messages.error(request, f"Кестені жүктеу кезінде күтпеген қате: {e}"); logger.exception("Күтпеген қате dashboard_schedule_view ішінде:")
    context = {
        'schedules_by_date': dict(schedules_by_date), 'view_date_start': start_of_week, 'view_date_end': end_of_week,
        'current_view': 'schedule', 'display_role': display_mode, 'target_user': target_user, 'viewing_student': viewing_student,
        'target_class': target_class, 'prev_week_date_str': prev_week_start.strftime('%Y-%m-%d'), 'next_week_date_str': next_week_start.strftime('%Y-%m-%d'),
    }
    return render(request, 'dashboard_schedule.html', context)

@login_required
def profile_edit(request):
    """Профильді және оған қатысты деректерді редакциялау."""
    user = request.user
    try:
        # UserProfile нысанын алу немесе құру (егер жоқ болса)
        user_profile, created = UserProfile.objects.get_or_create(user=user)
        if created:
            logger.info(f"UserProfile создан для пользователя {user.username}")
    except Exception as e:
        # Бұл өте сирек жағдай, бірақ UserProfile-ды құру кезінде қате болса
        logger.error(f"Ошибка при создании UserProfile для {user.username}: {e}")
        messages.error(request, "Профиль деректерін жүктеу кезінде қате пайда болды. Кейінірек қайталап көріңіз.")
        return redirect('dashboard_profile') # Немесе басқа қауіпсіз бетке

    if request.method == 'POST':
        # User формасы (негізгі деректер)
        user_form = UserEditForm(request.POST, instance=user)
        # UserProfile формасы (қосымша деректер, соның ішінде аватар)
        # Файлдарды өңдеу үшін request.FILES параметрін міндетті түрде беру керек
        profile_form = UserProfileEditForm(request.POST, request.FILES, instance=user_profile, user=user)

        if user_form.is_valid() and profile_form.is_valid():
            try:
                with transaction.atomic(): # Екі форманы да бір транзакция ішінде сақтау
                    user_form.save()
                    profile_form.save()

                messages.success(request, 'Профиль сәтті жаңартылды!')
                # МАҢЫЗДЫ: Форма сәтті сақталғаннан кейін профильді көру бетіне redirect жасау
                # Бұл Post/Redirect/Get паттернін қамтамасыз етеді және жаңа аватардың көрсетілуіне көмектеседі
                return redirect('dashboard_profile')  # 'dashboard_profile' - сіздің профильді көру URL атауыңыз
            except Exception as e:
                logger.error(f"Профильді сақтау кезінде күтпеген қате (user: {user.username}): {e}")
                messages.error(request, "Профильді сақтау кезінде күтпеген қате пайда болды.")
        else:
            # Егер формалардың бірі жарамсыз болса
            error_messages = []
            if user_form.errors:
                for field, errors in user_form.errors.items():
                    error_messages.append(f"{user_form.fields[field].label if field != '__all__' else 'Жалпы қате'}: {', '.join(errors)}")
            if profile_form.errors:
                for field, errors in profile_form.errors.items():
                    error_messages.append(f"{profile_form.fields[field].label if field != '__all__' else 'Жалпы қате'}: {', '.join(errors)}")

            if error_messages:
                messages.error(request, f"Профильді жаңарту кезінде қателер пайда болды: {'; '.join(error_messages)}. Форманы тексеріңіз.")
            else:
                messages.error(request, 'Профильді жаңарту кезінде қателер пайда болды. Форманы тексеріңіз.')
    else: # GET сұранысы
        user_form = UserEditForm(instance=user)
        profile_form = UserProfileEditForm(instance=user_profile, user=user)

    context = {
        'user_form': user_form,
        'profile_form': profile_form,
        'current_view': 'profile_edit', # Шаблонда активті меню элементін белгілеу үшін
        'userprofile': user_profile     # Шаблонда ағымдағы аватарды көрсету үшін маңызды
    }
    return render(request, 'profile_edit.html', context)

@login_required
def dashboard_grades_view(request):
    """Отображает итоговые и текущие оценки студента/ребенка."""
    user = request.user
    user_role = getattr(user, 'role', None)
    target_student = None
    student_class = None
    subject_grades_list = []
    student_class_name = "Сынып анықталмаған"
    available_terms = [1, 2, 3, 4]

    # --- Определение выбранного токсана ---
    logger.debug(f"[Grades View] Request GET params: {request.GET}")
    selected_term_str = request.GET.get('term')
    selected_term = None
    if selected_term_str and selected_term_str.isdigit() and int(selected_term_str) in available_terms:
        selected_term = int(selected_term_str)
        logger.info(f"[Grades View] Term selected from GET parameter: {selected_term}")
    else:
        # Если в GET нет или он некорректен, определяем текущий
        selected_term = get_current_term() # Используем функцию определения текущего
        if selected_term:
            logger.info(f"[Grades View] Term determined by get_current_term(): {selected_term}")
        else:
            # Если и текущий токсан не определен (каникулы?), можно взять последний, например
            # selected_term = available_terms[-1] # Показать последний токсан
            # Или показать сообщение об ошибке
            messages.warning(request, "Ағымдағы оқу тоқсаны анықталмады. Бағаларды көру үшін тоқсанды таңдаңыз.")
            logger.warning("[Grades View] Could not determine current term.")
            # В этом случае selected_term останется None

    # --- Определение студента ---
    try:
        if user_role == 'student': target_student = user
        elif user_role == 'parent':
            target_student = getattr(user, 'parent_of', None)
            if not target_student: messages.warning(request, "Сіздің профиліңізге оқушы тіркелмеген.")
        elif is_school_staff(user): messages.info(request, "Бағалар журналын көру үшін 'Баға қою' немесе арнайы есеп беру беттеріне өтіңіз.")
        else: messages.info(request, "Бағаларды көру рөліңіз үшін қолжетімсіз.")

        # --- Получение данных, если студент и токсан определены ---
        if target_student and selected_term is not None: # <-- Проверяем, что selected_term не None
            try:
                student_profile = target_student.userprofile; student_class = student_profile.grade
                if student_class: student_class_name = f"{student_class.name} ({student_class.school.name})"
                else: messages.warning(request, f"Оқушы '{target_student.username}' сыныпқа тіркелмеген.")
            except (UserProfile.DoesNotExist, AttributeError): student_class = None; messages.warning(request, f"Оқушы '{target_student.username}' профилі немесе сыныбы табылмады.")

            if student_class: # Продолжаем, только если класс найден
                subjects_qs = student_class.subjects.all().order_by('name')
                if not subjects_qs.exists(): messages.warning(request, f"{student_class_name} сыныбына пәндер тағайындалмаған.")

                logger.debug(f"[Grades View] Fetching grades for Student: {target_student.pk}, Class: {student_class.pk}, Term: {selected_term}")

                for subject in subjects_qs:
                    # --- Запрос Дневных оценок ---
                    daily_grades_for_subject = DailyGrade.objects.filter(
                        student=target_student, subject=subject, term=selected_term # Фильтр по selected_term
                    ).order_by('date')
                    logger.debug(f"[Grades View] Found {daily_grades_for_subject.count()} daily grades for Student {target_student.pk}, Subject {subject.pk}, Term {selected_term}")
                    daily_grades_data = list(daily_grades_for_subject.values('grade', 'date', 'comment'))
                    daily_grades_values = [g['grade'] for g in daily_grades_data if g.get('grade') is not None]

                    # --- Запрос СОР/СОЧ ---
                    exam_grades_for_subject = ExamGrade.objects.filter(
                        student=target_student, subject=subject, term=selected_term # Фильтр по selected_term
                    )
                    sor_grades_list = list(exam_grades_for_subject.filter(exam_type='SOR'))
                    soch_grade_obj = exam_grades_for_subject.filter(exam_type='SOCH').first()
                    logger.debug(f"[Grades View] Found {len(sor_grades_list)} SOR grades and {1 if soch_grade_obj else 0} SOCH grade for Student {target_student.pk}, Subject {subject.pk}, Term {selected_term}")


                    # --- Расчет итоговой оценки ---
                    term_grade_final_calculated = calculate_term_grade(
                        daily_grades_values, sor_grades_list, soch_grade_obj
                    )

                    sor1_grade_obj = sor_grades_list[0] if len(sor_grades_list) > 0 else None
                    sor2_grade_obj = sor_grades_list[1] if len(sor_grades_list) > 1 else None

                    subject_grades_list.append({
                        'subject_name': subject.name, 'daily_grades_list': daily_grades_data,
                        'sor1_grade': sor1_grade_obj.grade if sor1_grade_obj else None, 'sor1_max_grade': sor1_grade_obj.max_grade if sor1_grade_obj else None,
                        'sor2_grade': sor2_grade_obj.grade if sor2_grade_obj else None, 'sor2_max_grade': sor2_grade_obj.max_grade if sor2_grade_obj else None,
                        'soch_grade': soch_grade_obj.grade if soch_grade_obj else None, 'soch_max_grade': soch_grade_obj.max_grade if soch_grade_obj else None,
                        'term_grade': term_grade_final_calculated
                    })
        elif target_student and selected_term is None:
             # Сообщение уже было выведено выше
             pass

    except Exception as e:
        messages.error(request, f"Бағаларды жүктеу кезінде күтпеген қате: {e}")
        logger.exception("[Grades View] Unexpected error:")

    context = {
        'student': target_student, 'student_class_name': student_class_name,
        'current_term': selected_term, # Передаем выбранный или определенный токсан
        'available_terms': available_terms, 'subject_grades': subject_grades_list,
        'current_view': 'grades', 'display_role': user_role, 'target_user': target_student,
    }
    return render(request, 'daily_grades.html', context)

@login_required
def dashboard_profile_view(request):
    """Отображает страницу профиля пользователя."""
    user = request.user; user_profile = None
    try: user_profile = user.userprofile
    except (UserProfile.DoesNotExist, AttributeError): logger.warning(f"Профиль для пользователя {user.username} не найден.")
    context = {'profile_user': user, 'userprofile': user_profile, 'current_view': 'profile'}
    return render(request, 'profile.html', context)

@login_required
def dashboard_exams_view(request):
    """Перенаправление для раздела 'Экзамены'."""
    if is_student(request.user): return redirect('list_assigned_assessments')
    if is_teacher(request.user): return redirect('list_assessments')
    messages.info(request, "Бағалау (БЖБ/ТЖБ) беті.")
    return redirect('dashboard_schedule')
@login_required
def dashboard_contact_teacher_view(request):
    """Заглушка для 'Связь с учителем'."""
    messages.info(request, "Бұл бөлім ('Мұғаліммен байланыс') әзірленуде.")
    return redirect('dashboard_schedule')
@login_required
def dashboard_settings_view(request):
    """Заглушка для 'Настройки'."""
    messages.info(request, "Бұл бөлім ('Баптаулар') әзірленуде.")
    return redirect('dashboard_profile')
@login_required
def profile_page_view(request):
    """Редирект на основную страницу профиля."""
    return redirect('dashboard_profile')

# ==================================
# ОПЕРАЦИИ ДОБАВЛЕНИЯ (АДМИНКА НА САЙТЕ)
# ==================================
@login_required
@admin_director_required
def add_person(request):
    """Добавление нового пользователя."""
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
    """Добавление новой школы."""
    if request.method == 'POST':
        form = SchoolForm(request.POST)
        if form.is_valid(): form.save(); messages.success(request, "Мектеп сәтті қосылды."); return redirect('add_school')
        else: messages.error(request, "Форма толтыруда қателер бар.")
    else: form = SchoolForm()
    context = {'form': form, 'current_view': 'add_school'}; return render(request, 'add_school.html', context)

@login_required
@admin_director_required
def add_class(request):
    """Добавление нового класса."""
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
                 except Exception as e: logger.error(f"Сыныпты сақтау кезінде қате: {e}"); messages.error(request, f"Сыныпты сақтау кезінде қате: {e}")
        else: messages.error(request, "Форма толтыруда қателер бар.")
    else: form = ClassForm(school=school_filter)
    context = {'form': form, 'current_view': 'add_class'}; return render(request, 'add_class.html', context)

@login_required
@admin_director_required
def add_subject(request):
    """Добавление нового предмета."""
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
                except Exception as e: logger.error(f"Пәнді сақтау кезінде қате: {e}"); messages.error(request, f"Пәнді сақтау кезінде қате: {e}")
        else: messages.error(request, "Форма толтыруда қателер бар.")
    else: form = SubjectForm(school=school_filter)
    context = {'form': form, 'current_view': 'add_subject'}; return render(request, 'add_subject.html', context)

@login_required
@school_staff_required
def add_schedule(request):
    """Добавление элемента расписания."""
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
                     if hasattr(e, 'error_dict'): [form.add_error(field if field != '__all__' else None, errors) for field, errors in e.message_dict.items()]
                     else: form.add_error(None, e.messages)
                messages.error(request, "Кесте элементін сақтау мүмкін болмады. Мәліметтерді тексеріңіз.")
            except Exception as e: logger.error(f"Кестені сақтау кезінде күтпеген қате: {e}"); messages.error(request, f"Кестені сақтау кезінде күтпеген қате: {e}")
        else: messages.error(request, "Форма толтыруда қателер бар. Өрістерді тексеріңіз.")
    else: form = ScheduleForm(initial=initial_data, school=school_filter, user=user)
    context = {'form': form, 'current_view': 'add_schedule'}; return render(request, 'add_schedule.html', context)

# --- ★★★ add_daily_grade (ПОСЛЕДНЯЯ ВЕРСИЯ) ★★★ ---
@login_required
@teacher_required
def add_daily_grade(request):
    """Добавление дневной оценки."""
    user = request.user
    user_school = getattr(user, 'school', None)
    if not user_school:
        messages.error(request, "Баға қою үшін мектепке тіркелуіңіз керек.")
        return redirect('dashboard_profile')

    teacher_classes = Class.objects.filter(school=user_school).order_by('name')
    school_subjects = Subject.objects.filter(school=user_school).order_by('name')

    selected_class_id_str = request.POST.get('class_id') if request.method == 'POST' else request.GET.get('class_id')
    selected_subject_id_str = request.POST.get('subject') if request.method == 'POST' else request.GET.get('subject_id') # Используем subject для POST если шаблон исправлен
    if request.method == 'GET' and not selected_subject_id_str: # Для GET читаем старое имя
        selected_subject_id_str = request.GET.get('subject_id')

    selected_date_str = request.POST.get('date') if request.method == 'POST' else request.GET.get('date')

    logger.debug(f"[Add Daily Grade] Method: {request.method}. Filters - Class: {selected_class_id_str}, Subject ID (from POST/GET): {selected_subject_id_str}, Date: {selected_date_str}")

    selected_class = None
    selected_subject = None
    selected_date = None
    students_queryset = User.objects.none()
    existing_grades = DailyGrade.objects.none()
    show_form = False

    # Обработка фильтров
    if selected_class_id_str and selected_class_id_str.isdigit():
        try: selected_class = Class.objects.get(pk=int(selected_class_id_str), school=user_school)
        except Class.DoesNotExist: messages.error(request, f"Сынып табылмады (ID: {selected_class_id_str})."); logger.warning(f"Class not found: ID={selected_class_id_str}")
    if selected_subject_id_str and selected_subject_id_str.isdigit():
        try: selected_subject = Subject.objects.get(pk=int(selected_subject_id_str), school=user_school)
        except Subject.DoesNotExist: messages.error(request, f"Пән табылмады (ID: {selected_subject_id_str})."); logger.warning(f"Subject not found: ID={selected_subject_id_str}")
    if selected_date_str:
        try: selected_date = datetime.strptime(selected_date_str, '%Y-%m-%d').date()
        except ValueError: messages.error(request, "Күн форматы дұрыс емес (YYYY-MM-DD)."); logger.warning(f"Invalid date format: {selected_date_str}")

    students_count = 0
    if selected_class and selected_subject and selected_date:
        students_queryset = User.objects.filter(
            role='student', school=user_school, userprofile__school_class=selected_class
        ).select_related('userprofile').order_by('last_name', 'first_name')
        students_count = students_queryset.count()
        logger.debug(f"[Add Daily Grade] Filters OK. Class: {selected_class.name}, Subject: {selected_subject.name}, Date: {selected_date}. Found {students_count} students.")
        if students_count > 0:
            show_form = True
            existing_grades = DailyGrade.objects.filter(
                subject=selected_subject, date=selected_date, student__in=students_queryset
            ).select_related('student', 'teacher').order_by('student__last_name')
        else:
            show_form = False
            if not DailyGrade.objects.filter(subject=selected_subject, date=selected_date, student__userprofile__school_class=selected_class).exists():
                 messages.warning(request, f"'{selected_class.name}' сыныбында оқушылар табылмады.")
    else:
        logger.debug("[Add Daily Grade] Filters incomplete or invalid.")

    # Обработка POST запроса
    if request.method == 'POST':
        # Перепроверка возможности показа формы на основе POST данных
        post_class_id_str = request.POST.get('class_id')
        post_students_queryset = User.objects.none()
        rechecked_show_form = False
        if post_class_id_str and post_class_id_str.isdigit():
            try:
                post_selected_class = Class.objects.get(pk=int(post_class_id_str), school=user_school)
                post_students_queryset = User.objects.filter(role='student', school=user_school, userprofile__school_class=post_selected_class).select_related('userprofile').order_by('last_name', 'first_name')
                # Проверяем, что все фильтры из POST корректны
                if post_students_queryset.exists() and selected_subject and selected_date:
                    rechecked_show_form = True
            except Class.DoesNotExist: pass

        if not rechecked_show_form:
             messages.error(request, "Баға қою үшін жарамды сынып, пән және күн таңдалып, сыныпта оқушылар болуы керек.")
             logger.warning("[Add Daily Grade] POST request received, but rechecked show_form is False. Redirecting.")
             redirect_url = reverse('add_daily_grade'); get_params = request.GET.urlencode();
             if get_params: redirect_url += f'?{get_params}'
             return redirect(redirect_url)

        form = DailyGradeForm(request.POST, school=user_school, user=user, students_queryset=post_students_queryset)
        logger.debug(f"[Add Daily Grade] POST request. Instantiating DailyGradeForm. students_queryset count: {post_students_queryset.count()}")
        logger.debug(f"[Add Daily Grade] POST data used for form: {request.POST}") # Логгируем POST данные

        if form.is_valid():
            logger.debug("[Add Daily Grade] DailyGradeForm is valid.")
            grade = form.save(commit=False)
            term_for_date = get_current_term(grade.date)
            if term_for_date is None:
                logger.error(f"[Add Daily Grade] Could not determine term for date {grade.date}.")
                form.add_error('date', _("Таңдалған күн үшін оқу тоқсаны анықталмады."))
                messages.error(request, _("Бағаны сақтау мүмкін болмады: күн үшін тоқсан анықталмады."))
            else:
                grade.term = term_for_date
                logger.debug(f"[Add Daily Grade] Determined term: {grade.term} for date: {grade.date}")
                try:
                    grade.full_clean()
                    grade.save()
                    logger.info(f"[Add Daily Grade] Grade saved: PK={grade.pk}, Student={grade.student.pk}, Sub={grade.subject.pk}, Date={grade.date}, Gr={grade.grade}, Term={grade.term}")
                    messages.success(request, f"Баға ({grade.grade}) оқушы {grade.student.get_full_name()} үшін '{grade.subject.name}' пәнінен ({grade.date}) сәтті қойылды.")
                    # Используем значения из POST для редиректа
                    redirect_url = reverse('add_daily_grade') + f'?class_id={request.POST.get("class_id")}&subject_id={request.POST.get("subject")}&date={request.POST.get("date")}'
                    return redirect(redirect_url)
                except (IntegrityError, ValidationError) as e:
                    logger.warning(f"[Add Daily Grade] Error saving grade (Integrity/Validation): {e}", exc_info=False)
                    if isinstance(e, IntegrityError): form.add_error(None, _('Бұл оқушыға осы пәннен осы күні баға бұрын қойылған болуы мүмкін.'))
                    elif isinstance(e, ValidationError):
                         if hasattr(e, 'error_dict'): [form.add_error(field if field != '__all__' else None, errors) for field, errors in e.message_dict.items()]
                         else: form.add_error(None, e.messages)
                    messages.error(request, _("Бағаны сақтау мүмкін болмады."))
                except Exception as e:
                    logger.exception("[Add Daily Grade] Unexpected error saving grade:")
                    messages.error(request, f"Бағаны сақтау кезінде күтпеген қате: {e}")
        else:
            logger.warning(f"[Add Daily Grade] DailyGradeForm is invalid: {form.errors.as_json()}")
            messages.error(request, "Форма толтыруда қателер бар. Өрістерді тексеріңіз.")
    else: # GET request
        initial_data = {}
        if selected_subject: initial_data['subject'] = selected_subject.pk
        if selected_date: initial_data['date'] = selected_date

        form = DailyGradeForm(initial=initial_data, school=user_school, user=user, students_queryset=students_queryset)
        logger.debug(f"[Add Daily Grade] GET request. Instantiating DailyGradeForm. students_queryset count: {students_queryset.count()}")

    context = {
        'form': form, 'teacher_classes': teacher_classes, 'school_subjects': school_subjects,
        'selected_class': selected_class, 'selected_subject': selected_subject,
        'selected_date_str': selected_date_str, 'selected_date': selected_date,
        'students_count': students_count, 'show_form': show_form,
        'existing_grades': existing_grades, 'current_view': 'add_daily_grade'
        }
    return render(request, 'add_daily_grades.html', context)


# --- ★★★ add_exam_grade (ПОСЛЕДНЯЯ ВЕРСИЯ) ★★★ ---
@login_required
@teacher_required
def add_exam_grade(request):
    """Добавление оценки за СОР/СОЧ."""
    user = request.user
    user_school = getattr(user, 'school', None)
    if not user_school:
        messages.error(request, "Баға қою үшін мектепке тіркелуіңіз керек.")
        return redirect('dashboard_profile')

    teacher_classes = Class.objects.filter(school=user_school).order_by('name')
    school_subjects = Subject.objects.filter(school=user_school).order_by('name')
    exam_type_choices = ExamGrade.EXAM_TYPE_CHOICES

    selected_class_id_str = request.POST.get('class_id') if request.method == 'POST' else request.GET.get('class_id')
    # Используем 'subject' для POST (если шаблон исправлен), 'subject_id' для GET
    selected_subject_id_str = request.POST.get('subject') if request.method == 'POST' else request.GET.get('subject_id')
    if request.method == 'GET' and not selected_subject_id_str:
        selected_subject_id_str = request.GET.get('subject_id')

    selected_term_str = request.POST.get('term') if request.method == 'POST' else request.GET.get('term')
    selected_exam_type = request.POST.get('exam_type') if request.method == 'POST' else request.GET.get('exam_type')

    logger.debug(f"[Add Exam Grade] Method: {request.method}. Filters - Class: {selected_class_id_str}, Subject ID (from POST/GET): {selected_subject_id_str}, Term: {selected_term_str}, Type: {selected_exam_type}")

    selected_class = None
    selected_subject = None
    selected_term = None
    students_queryset = User.objects.none()
    existing_grades = ExamGrade.objects.none()
    show_form = False
    selected_exam_type_display = None

    # Обработка фильтров
    if selected_class_id_str and selected_class_id_str.isdigit():
        try:
            selected_class = Class.objects.get(pk=int(selected_class_id_str), school=user_school)
            students_queryset = User.objects.filter(role='student', school=user_school, userprofile__school_class=selected_class).select_related('userprofile').order_by('last_name', 'first_name')
            if not students_queryset.exists(): messages.warning(request, f"Таңдалған сыныпта ('{selected_class.name}') тіркелген оқушылар табылмады.")
        except Class.DoesNotExist: messages.error(request, f"Сынып табылмады (ID: {selected_class_id_str})."); selected_class = None; students_queryset = User.objects.none(); logger.warning(f"Class not found: ID={selected_class_id_str}")
    if selected_subject_id_str and selected_subject_id_str.isdigit():
        try: selected_subject = Subject.objects.get(pk=int(selected_subject_id_str), school=user_school)
        except Subject.DoesNotExist: messages.error(request, f"Пән табылмады (ID: {selected_subject_id_str})."); selected_subject = None; logger.warning(f"Subject not found: ID={selected_subject_id_str}")
    if selected_term_str and selected_term_str.isdigit():
        term = int(selected_term_str)
        if term in [1, 2, 3, 4]: selected_term = term
        else: messages.error(request, "Тоқсан нөмірі дұрыс емес."); selected_term = None; logger.warning(f"Invalid term: {selected_term_str}")

    if selected_exam_type:
        exam_type_dict = dict(exam_type_choices)
        if selected_exam_type in exam_type_dict:
            selected_exam_type_display = exam_type_dict[selected_exam_type]
        else:
             messages.error(request, "Жұмыс түрі дұрыс емес."); selected_exam_type = None; logger.warning(f"Invalid exam type: {selected_exam_type}")

    students_count = students_queryset.count()
    if selected_class and selected_subject and selected_term and selected_exam_type:
        if students_count > 0:
            show_form = True
            existing_grades = ExamGrade.objects.filter(subject=selected_subject, term=selected_term, exam_type=selected_exam_type, student__in=students_queryset).select_related('student', 'teacher').order_by('student__last_name')
            logger.debug(f"[Add Exam Grade] Filters OK. Found {students_count} students. Show form: {show_form}")
        else: show_form = False; logger.debug(f"[Add Exam Grade] Filters OK, but no students found. Show form: {show_form}")
    else: logger.debug(f"[Add Exam Grade] Filters incomplete or invalid. Students found: {students_count}. Show form: {show_form}")

    # Обработка POST запроса
    if request.method == 'POST':
        # Перепроверка возможности показа формы
        post_class_id_str = request.POST.get('class_id')
        post_students_queryset = User.objects.none()
        rechecked_show_form = False
        if post_class_id_str and post_class_id_str.isdigit():
            try:
                post_selected_class = Class.objects.get(pk=int(post_class_id_str), school=user_school)
                post_students_queryset = User.objects.filter(role='student', school=user_school, userprofile__school_class=post_selected_class).select_related('userprofile').order_by('last_name', 'first_name')
                if post_students_queryset.exists() and selected_subject and selected_term and selected_exam_type:
                    rechecked_show_form = True
            except Class.DoesNotExist: pass

        if not rechecked_show_form:
             messages.error(request, "Баға қою үшін жарамды сынып, пән, тоқсан, жұмыс түрі таңдалып, сыныпта оқушылар болуы керек.")
             logger.warning("[Add Exam Grade] POST request received, but rechecked show_form is False. Redirecting.")
             redirect_url = reverse('add_exam_grade'); get_params = request.GET.urlencode();
             if get_params: redirect_url += f'?{get_params}'
             return redirect(redirect_url)

        form = ExamGradeForm(request.POST, school=user_school, user=user, students_queryset=post_students_queryset)
        logger.debug(f"[Add Exam Grade] POST request. Instantiating ExamGradeForm. students_queryset count: {post_students_queryset.count()}")
        logger.debug(f"[Add Exam Grade] POST data used for form: {request.POST}") # Логгируем POST данные

        if form.is_valid():
            logger.debug("[Add Exam Grade] ExamGradeForm is valid.")
            grade = form.save(commit=False)
            try:
                grade.full_clean()
                grade.save()
                logger.info(f"[Add Exam Grade] Grade saved: PK={grade.pk}, Student={grade.student.pk}, Sub={grade.subject.pk}, Term={grade.term}, Type={grade.exam_type}, Gr={grade.grade}/{grade.max_grade}")
                messages.success(request, f"{grade.get_exam_type_display()} бағасы ({grade.grade}/{grade.max_grade}) оқушы {grade.student.get_full_name()} үшін '{grade.subject.name}' пәнінен ({grade.term}-тоқсан, {grade.date.strftime('%d.%m.%Y')}) сәтті қойылды.")
                # Используем значения из POST для редиректа
                redirect_url = reverse('add_exam_grade') + f'?class_id={request.POST.get("class_id")}&subject_id={request.POST.get("subject")}&term={request.POST.get("term")}&exam_type={request.POST.get("exam_type")}'
                return redirect(redirect_url)
            except (IntegrityError, ValidationError) as e:
                 logger.warning(f"[Add Exam Grade] Error saving grade (Integrity/Validation): {e}", exc_info=False)
                 if isinstance(e, IntegrityError): form.add_error(None, _('Бұл оқушыға осы пәннен осы тоқсанда бұл БЖБ/ТЖБ түріне баға бұрын қойылған болуы мүмкін.'))
                 elif isinstance(e, ValidationError):
                      if hasattr(e, 'error_dict'): [form.add_error(field if field != '__all__' else None, errors) for field, errors in e.message_dict.items()]
                      else: form.add_error(None, e.messages)
                 messages.error(request, _("Бағаны сақтау мүмкін болмады."))
            except Exception as e:
                logger.exception("[Add Exam Grade] Unexpected error saving grade:")
                messages.error(request, f"Бағаны сақтау кезінде күтпеген қате: {e}")
        else:
            logger.warning(f"[Add Exam Grade] ExamGradeForm is invalid: {form.errors.as_json()}")
            messages.error(request, "Форма толтыруда қателер бар. Өрістерді тексеріңіз.")
    else: # GET request
        initial_data = {}
        if selected_subject: initial_data['subject'] = selected_subject.pk
        if selected_term: initial_data['term'] = selected_term
        if selected_exam_type: initial_data['exam_type'] = selected_exam_type
        initial_data['date'] = timezone.localdate().strftime('%Y-%m-%d')

        form = ExamGradeForm(initial=initial_data, school=user_school, user=user, students_queryset=students_queryset)
        logger.debug(f"[Add Exam Grade] GET request. Instantiating ExamGradeForm. students_queryset count: {students_queryset.count()}")

    context = {
        'form': form, 'teacher_classes': teacher_classes, 'school_subjects': school_subjects,
        'selected_class': selected_class, 'selected_subject': selected_subject, 'selected_term': selected_term,
        'selected_exam_type': selected_exam_type, 'exam_type_choices': exam_type_choices,
        'selected_exam_type_display': selected_exam_type_display, 'terms': [1, 2, 3, 4],
        'students_count': students_count, 'show_form': show_form,
        'existing_grades': existing_grades, 'current_view': 'add_exam_grade'
        }
    return render(request, 'add_exam_grades.html', context)


# ==================================
# БЖБ/ТЖБ (ASSESSMENT) VIEWS
# ==================================
# ... (create_assessment, edit_assessment, list_assessments - без изменений) ...
@login_required
@teacher_required
@transaction.atomic
def create_assessment(request):
    user = request.user; user_school = getattr(user, 'school', None)
    if not user_school and not user.is_superuser: messages.error(request, "БЖБ/ТЖБ құру үшін мектепке тіркелуіңіз керек."); return redirect('dashboard_schedule')
    QuestionFormSet = inlineformset_factory(Assessment, Question, form=QuestionForm, formset=BaseQuestionFormSet, fields=('text', 'question_type', 'points', 'order'), extra=1, can_delete=True)
    ChoiceFormSetInline = inlineformset_factory(Question, Choice, form=ChoiceForm, fields=('text', 'is_correct'), extra=1, can_delete=True)
    if request.method == 'POST':
        assessment_form = AssessmentForm(request.POST, school=user_school, user=user)
        question_formset = QuestionFormSet(request.POST, prefix='questions')
        choice_formsets_dict = {}; is_valid_overall = assessment_form.is_valid() and question_formset.is_valid()
        if is_valid_overall:
            for q_form in question_formset:
                if q_form.is_valid() and not q_form.cleaned_data.get('DELETE') and q_form.cleaned_data.get('question_type') in ['MCQ', 'MAQ', 'TF']:
                    prefix = f'choices-{q_form.prefix}'; choice_formset = ChoiceFormSetInline(request.POST, prefix=prefix)
                    choice_formsets_dict[q_form.prefix] = choice_formset
                    if not choice_formset.is_valid(): is_valid_overall = False; logger.warning(f"Choice formset errors (prefix {prefix}): {choice_formset.errors}"); messages.error(request, f"'{q_form.cleaned_data.get('text', 'Сұрақ')}...' сұрағының жауап нұсқаларында қате бар.")
        if is_valid_overall:
            try:
                assessment = assessment_form.save(commit=False); assessment.teacher = user
                if not user_school and user.is_superuser:
                    selected_class = assessment_form.cleaned_data.get('school_class')
                    if not (selected_class and selected_class.school): assessment_form.add_error('school_class', "Мектепті анықтау үшін сыныпты таңдау қажет."); raise ValidationError("Сынып таңдалмаған.")
                elif user_school:
                     selected_class = assessment_form.cleaned_data.get('school_class')
                     if selected_class and selected_class.school != user_school: assessment_form.add_error('school_class', "Бұл сынып сіздің мектебіңізге жатпайды."); raise ValidationError("Сынып сәйкес емес.")
                else: raise ValidationError("Мектеп анықталмаған.")
                assessment.save()
                questions_to_save = question_formset.save(commit=False); saved_questions_map = {}
                for q_form in question_formset:
                    if not q_form.cleaned_data.get('DELETE'): q_instance = q_form.save(commit=False); q_instance.assessment = assessment; q_instance.save(); saved_questions_map[q_form.prefix] = q_instance
                for q_prefix, cfset in choice_formsets_dict.items():
                    target_question = saved_questions_map.get(q_prefix)
                    if target_question: choices = cfset.save(commit=False); [setattr(c, 'question', target_question) or c.save() for c in choices]
                    else:
                        original_q_form = next((form for form in question_formset if form.prefix == q_prefix), None)
                        if not (original_q_form and original_q_form.cleaned_data.get('DELETE')): logger.error(f"КРИТИКАЛЫҚ: Сәйкес сұрақ табылған жоқ (prefix: {q_prefix}) create_assessment кезінде варианттарды сақтау үшін!")
                assessment.recalculate_max_score(); messages.success(request, f"Бағалау '{assessment.title}' сәтті құрылды."); return redirect('edit_assessment', pk=assessment.pk)
            except ValidationError as e: messages.error(request, f"Форма толтыруда қателер бар: {e}")
            except Exception as e: logger.exception("Бағалауды сақтау кезінде күтпеген қате:"); messages.error(request, f"Бағалауды сақтау кезінде күтпеген қате: {e}")
        else:
             if not messages.get_messages(request): messages.error(request, "Форма толтыруда қателер бар. Тексеріңіз.")
    else: assessment_form = AssessmentForm(school=user_school, user=user); question_formset = QuestionFormSet(prefix='questions'); choice_formsets_dict = {}
    questions_with_forms = []
    for q_form in question_formset:
        prefix = f'choices-{q_form.prefix}'; choice_formset_instance = None
        if request.method == 'POST' and q_form.prefix in choice_formsets_dict: choice_formset_instance = choice_formsets_dict[q_form.prefix]
        elif request.method == 'POST': choice_formset_instance = ChoiceFormSetInline(request.POST, prefix=prefix); choice_formset_instance.is_valid()
        else: choice_formset_instance = ChoiceFormSetInline(prefix=prefix)
        questions_with_forms.append({'question_form': q_form, 'choice_formset': choice_formset_instance, 'instance': q_form.instance})
    empty_choice_form_for_template = ChoiceFormSetInline.empty_form
    context = {'assessment_form': assessment_form, 'question_formset': question_formset, 'questions_with_forms': questions_with_forms, 'empty_choice_form_for_template': empty_choice_form_for_template, 'current_view': 'create_assessment', 'page_title': "Жаңа БЖБ/ТЖБ құру"}
    return render(request, 'assessment/assessment_form.html', context)

@login_required
@teacher_required
def edit_assessment(request, pk):
    assessment = get_object_or_404(Assessment, pk=pk)
    if assessment.teacher != request.user and not request.user.is_superuser: messages.error(request, "Бұл бағалауды өңдеуге рұқсатыңыз жоқ."); return redirect('list_assessments')
    user_school = getattr(request.user, 'school', None)
    QuestionFormSet = inlineformset_factory(Assessment, Question, form=QuestionForm, formset=BaseQuestionFormSet, fields=('text', 'question_type', 'points', 'order'), extra=0, can_delete=True)
    ChoiceFormSetInline = inlineformset_factory(Question, Choice, form=ChoiceForm, fields=('text', 'is_correct'), extra=1, can_delete=True)
    if request.method == 'POST':
        assessment_form = AssessmentForm(request.POST, instance=assessment, school=user_school, user=request.user)
        question_formset = QuestionFormSet(request.POST, instance=assessment, prefix='questions')
        choice_formsets_dict = {}; is_valid_overall = assessment_form.is_valid() and question_formset.is_valid()
        if is_valid_overall:
             for q_form in question_formset:
                 if q_form.is_valid() and not q_form.cleaned_data.get('DELETE') and q_form.cleaned_data.get('question_type') in ['MCQ', 'MAQ', 'TF']:
                     prefix = f'choices-{q_form.prefix}'; choice_formset = ChoiceFormSetInline(request.POST, instance=q_form.instance, prefix=prefix)
                     choice_formsets_dict[q_form.prefix] = choice_formset
                     if not choice_formset.is_valid(): is_valid_overall = False; logger.warning(f"Choice formset errors (prefix {prefix}): {choice_formset.errors}"); messages.error(request, f"'{q_form.cleaned_data.get('text', 'Сұрақ')}...' сұрағының жауап нұсқаларында қате бар.")
        if is_valid_overall:
            try:
                with transaction.atomic():
                    saved_assessment = assessment_form.save(); question_formset.save()
                    for q_prefix, cfset in choice_formsets_dict.items():
                         original_q_form = next((form for form in question_formset if form.prefix == q_prefix), None)
                         if original_q_form and original_q_form.instance and original_q_form.instance.pk: cfset.instance = original_q_form.instance; cfset.save()
                         elif not (original_q_form and original_q_form.cleaned_data.get('DELETE')): logger.error(f"КРИТИКАЛЫҚ: Сәйкес сұрақ instance табылған жоқ (prefix: {q_prefix}) edit_assessment кезінде варианттарды сақтау үшін!")
                    saved_assessment.recalculate_max_score()
                messages.success(request, f"Бағалау '{saved_assessment.title}' сәтті жаңартылды."); return redirect('edit_assessment', pk=saved_assessment.pk)
            except Exception as e: logger.exception("Бағалауды сақтау кезінде күтпеген қате:"); messages.error(request, f"Бағалауды сақтау кезінде күтпеген қате: {e}")
        else:
             if not messages.get_messages(request): messages.error(request, "Форма толтыруда қателер бар. Тексеріңіз.")
    else: assessment_form = AssessmentForm(instance=assessment, school=user_school, user=request.user); question_formset = QuestionFormSet(instance=assessment, prefix='questions'); choice_formsets_dict = {}
    questions_with_forms = []
    for q_form in question_formset:
        prefix_for_choices = f'choices-{q_form.prefix}'; choice_formset_instance = None
        question_instance = q_form.instance if q_form.instance and q_form.instance.pk else None
        question_type = q_form.initial.get('question_type', getattr(question_instance, 'question_type', None))
        if request.method == 'POST' and q_form.prefix in choice_formsets_dict: choice_formset_instance = choice_formsets_dict[q_form.prefix]
        elif request.method == 'POST' and question_type in ['MCQ', 'MAQ', 'TF']: choice_formset_instance = ChoiceFormSetInline(request.POST, instance=question_instance, prefix=prefix_for_choices); choice_formset_instance.is_valid()
        elif request.method != 'POST' and question_instance and question_type in ['MCQ', 'MAQ', 'TF']: choice_formset_instance = ChoiceFormSetInline(instance=question_instance, prefix=prefix_for_choices)
        questions_with_forms.append({'question_form': q_form, 'choice_formset': choice_formset_instance, 'instance': question_instance})
    empty_choice_form_for_template = ChoiceFormSetInline.empty_form
    context = {'assessment': assessment, 'assessment_form': assessment_form, 'question_formset': question_formset, 'questions_with_forms': questions_with_forms, 'empty_choice_form_for_template': empty_choice_form_for_template, 'current_view': 'edit_assessment', 'page_title': f"Бағалауды өңдеу: {assessment.title}"}
    return render(request, 'assessment/assessment_edit_form.html', context)

@login_required
@teacher_required
def list_assessments(request):
    user = request.user; assessments = Assessment.objects.filter(teacher=user).select_related('subject', 'school_class', 'subject__school').order_by('-created_at')
    context = { 'assessments': assessments, 'current_view': 'list_assessments', 'page_title': "Менің бағалауларым (БЖБ/ТЖБ)"}
    return render(request, 'assessment/assessment_list.html', context)

# ==================================
# ОҚУШЫ ҮШІН БЖБ/ТЖБ VIEWS - без изменений
# ==================================
@login_required
@user_passes_test(is_student)
def list_assigned_assessments(request):
    student = request.user; student_class = None
    try: student_class = student.userprofile.grade
    except (UserProfile.DoesNotExist, AttributeError): messages.warning(request, "Профиліңізде сынып көрсетілмеген."); return redirect('dashboard_profile')
    if not student_class: messages.warning(request, "Сіз ешқандай сыныпқа тіркелмегенсіз."); return redirect('dashboard_profile')
    now = timezone.now(); assessments = Assessment.objects.filter(school_class=student_class, is_active=True,).select_related('subject', 'teacher').order_by('-created_at', 'subject')
    submissions = Submission.objects.filter(student=student, assessment__in=assessments).values('assessment_id', 'pk', 'is_graded', 'score')
    submitted_map = {s['assessment_id']: s for s in submissions}
    context = {'assessments': assessments, 'submitted_map': submitted_map, 'now': now, 'current_view': 'list_assigned_assessments', 'page_title': "Маған тағайындалған БЖБ/ТЖБ"}
    return render(request, 'assessment/assessment_assigned_list.html', context)

@login_required
@user_passes_test(is_student)
@transaction.atomic
def take_assessment(request, pk):
    student = request.user; assessment = get_object_or_404(Assessment.objects.select_related('school_class', 'subject'), pk=pk, is_active=True)
    try:
        profile = student.userprofile
        if not profile or profile.grade != assessment.school_class: messages.error(request, "Сіз бұл тапсырманы орындай алмайсыз (басқа сынып немесе профиль қатесі)."); return redirect('list_assigned_assessments')
    except UserProfile.DoesNotExist: messages.error(request, "Профиліңіз табылмады. Администраторға хабарласыңыз."); return redirect('list_assigned_assessments')
    except AttributeError: messages.error(request, "Профиліңізде сынып көрсетілмеген."); return redirect('dashboard_profile')
    existing_submission = Submission.objects.filter(assessment=assessment, student=student).first()
    if existing_submission: messages.info(request, f"Сіз бұл тапсырманы ('{assessment.title}') бұрын тапсырғансыз."); return redirect('view_submission_result', pk=existing_submission.pk)
    if assessment.due_date and timezone.now() > assessment.due_date: messages.error(request, f"Тапсырманы ('{assessment.title}') орындау мерзімі өтіп кетті."); return redirect('list_assigned_assessments')
    questions = assessment.questions.order_by('order')
    if request.method == 'POST':
        form = SubmissionForm(request.POST, request.FILES, assessment=assessment, student=student)
        if form.is_valid():
            try:
                submission = form.save(commit=True)
                if submission: ActivityLog.objects.create(user=student, activity_type='SUBMIT_ASSESSMENT', details={'assessment_id': assessment.pk, 'submission_id': submission.pk}); messages.success(request, f"Тапсырма ('{assessment.title}') сәтті тапсырылды!"); return redirect('view_submission_result', pk=submission.pk)
                else: messages.error(request, "Тапсырманы сақтау кезінде белгісіз қате."); logger.error(f"SubmissionForm.save вернул None для assessment {assessment.pk} и student {student.pk}")
            except Exception as e: logger.exception(f"Тапсырманы {assessment.pk} сақтау кезінде қате:"); messages.error(request, f"Тапсырманы сақтау кезінде қате: {e}")
        else: messages.error(request, "Форма толтыруда қателер бар. Жауаптарыңызды тексеріңіз.")
    else: form = SubmissionForm(assessment=assessment, student=student)
    questions_with_fields = []
    for question in questions:
        q_fields = {}; field_key_base = f'question_{question.pk}'
        try:
            if question.question_type in ['MCQ', 'TF']: q_fields['choice'] = form[f'{field_key_base}_choice']
            elif question.question_type == 'MAQ': q_fields['choices'] = form[f'{field_key_base}_choices']
            elif question.question_type == 'OPEN': q_fields['text'] = form[f'{field_key_base}_text']; q_fields['file'] = form[f'{field_key_base}_file']
        except KeyError: logger.error(f"Ескерту: SubmissionForm ішінде {question.pk} (тип: {question.question_type}) сұрағы үшін өріс табылмады.")
        questions_with_fields.append({'question': question, 'fields': q_fields})
    context = {'assessment': assessment, 'form': form, 'questions_with_fields': questions_with_fields, 'current_view': 'take_assessment', 'page_title': f"БЖБ/ТЖБ өту: {assessment.title}"}
    return render(request, 'assessment/assessment_take.html', context)

@login_required
def view_submission_result(request, pk):
    submission = get_object_or_404(Submission.objects.select_related('assessment', 'assessment__subject', 'student', 'student__userprofile', 'student__userprofile__school_class'), pk=pk)
    assessment = submission.assessment
    if request.user != submission.student and request.user != assessment.teacher and not is_admin_or_director(request.user): raise PermissionDenied("Бұл тапсырма нәтижесін көруге рұқсатыңыз жоқ.")
    answers = Answer.objects.filter(submission=submission).select_related('question', 'selected_choice').prefetch_related('selected_choices', 'question__choices').order_by('question__order')
    correct_choices_ids = set(Choice.objects.filter(question__assessment=assessment, is_correct=True).values_list('id', flat=True))
    selected_choices_map = defaultdict(set); threshold_80, threshold_50 = None, None
    for ans in answers:
        if ans.question.question_type == 'MAQ': selected_choices_map[ans.question.pk] = set(choice.pk for choice in ans.selected_choices.all())
    if assessment.max_score is not None and assessment.max_score > 0:
        try: max_score_float = float(assessment.max_score); threshold_80 = max_score_float * 0.85; threshold_50 = max_score_float * 0.65
        except (TypeError, ValueError): logger.warning(f"Не удалось рассчитать пороги для assessment {assessment.pk}")
    context = {'submission': submission, 'assessment': assessment, 'answers': answers, 'correct_choices_ids': correct_choices_ids, 'selected_choices_map': selected_choices_map, 'threshold_80': threshold_80, 'threshold_50': threshold_50, 'current_view': 'view_submission_result', 'page_title': f"Нәтиже: {assessment.title} ({submission.student.get_full_name()})"}
    return render(request, 'assessment/submission_result.html', context)

# ==================================
# МҰҒАЛІМ ҮШІН БЖБ/ТЖБ БАҒАЛАУ VIEWS - без изменений
# ==================================
@login_required
@teacher_required
def view_submissions(request, assessment_id):
    assessment = get_object_or_404(Assessment.objects.select_related('school_class', 'subject', 'teacher'), pk=assessment_id)
    if assessment.teacher != request.user and not request.user.is_superuser: raise PermissionDenied("Бұл бағалаудың тапсырмаларын көруге рұқсатыңыз жоқ.")
    submissions = Submission.objects.filter(assessment=assessment).select_related('student', 'student__userprofile').order_by('student__last_name', 'student__first_name')
    context = { 'assessment': assessment, 'submissions': submissions, 'current_view': 'view_submissions', 'page_title': f"Тапсырмалар: {assessment.title}" }
    return render(request, 'assessment/submission_list.html', context)

@login_required
@teacher_required
@transaction.atomic
def grade_submission(request, submission_id):
    submission = get_object_or_404(Submission.objects.select_related('assessment', 'assessment__subject', 'student', 'student__userprofile'), pk=submission_id)
    assessment = submission.assessment; student = submission.student
    if assessment.teacher != request.user and not is_admin_or_director(request.user):
         if not (request.user.role in ['admin', 'director'] and request.user.school == student.school): raise PermissionDenied("Бұл тапсырманы бағалауға рұқсатыңыз жоқ.")
    answers = Answer.objects.filter(submission=submission).select_related('question', 'selected_choice').prefetch_related('selected_choices', 'question__choices').order_by('question__order')
    correct_choices_ids = set(Choice.objects.filter(question__assessment=assessment, is_correct=True).values_list('id', flat=True))
    selected_choices_map = defaultdict(set)
    for ans in answers:
        if ans.question.question_type == 'MAQ': selected_choices_map[ans.question.pk] = set(choice.pk for choice in ans.selected_choices.all())
    if request.method == 'POST':
        form = GradeSubmissionForm(request.POST, instance=submission)
        if form.is_valid():
            updated_submission = form.save(commit=False); updated_submission.is_graded = True; updated_submission.graded_at = timezone.now()
            updated_submission.save(update_fields=['score', 'is_graded', 'graded_at'])
            exam_grade, created = ExamGrade.objects.update_or_create(
                student=student, subject=assessment.subject, term=assessment.term, exam_type=assessment.exam_type,
                defaults={'teacher': request.user, 'grade': updated_submission.score, 'max_grade': assessment.max_score, 'date': updated_submission.graded_at.date(), 'comment': f"Балл БЖБ/ТЖБ '{assessment.title}' тапсырмасынан алынды."})
            logger.info(f"ExamGrade запись {'создана' if created else 'обновлена'} для student {student.pk}, assessment {assessment.pk}")
            messages.success(request, f"{student.get_full_name()} оқушысының жұмысы бағаланды ({updated_submission.score}/{assessment.max_score}). ExamGrade жазбасы {'құрылды' if created else 'жаңартылды'}.")
            return redirect('view_submissions', assessment_id=assessment.id)
        else: messages.error(request, "Форма толтыруда қателер бар. Баллды тексеріңіз.")
    else: form = GradeSubmissionForm(instance=submission)
    context = {'submission': submission, 'assessment': assessment, 'student': student, 'answers': answers, 'correct_choices_ids': correct_choices_ids, 'selected_choices_map': selected_choices_map, 'form': form, 'current_view': 'grade_submission', 'page_title': f"Бағалау: {assessment.title} ({student.get_full_name()})"}
    return render(request, 'assessment/grade_submission.html', context)

# ==================================
# ОҚУШЫ БЕЛСЕНДІЛІГІ VIEWS (ЖАҢА) - без изменений
# ==================================
@login_required
@school_staff_required
def select_student_for_activity_view(request):
    viewer = request.user; user_school = getattr(viewer, 'school', None)
    if not user_school and not viewer.is_superuser: messages.error(request, "Оқушылар тізімін көру үшін мектепке тіркелуіңіз керек."); return redirect('dashboard_profile')
    students_in_school = User.objects.filter(role='student')
    if not viewer.is_superuser: students_in_school = students_in_school.filter(school=user_school)
    students_in_school = students_in_school.select_related('userprofile__school_class').order_by('userprofile__school_class__name', 'last_name', 'first_name')
    context = {'students_in_school': students_in_school, 'current_view': 'select_student_activity', 'page_title': "Белсенділігін көру үшін оқушыны таңдаңыз"}
    return render(request, 'kundelik/select_student_activity.html', context)

@login_required
def view_student_activity(request, student_id):
    viewer = request.user; student = get_object_or_404(User, pk=student_id, role='student')
    can_view = False; viewer_role = getattr(viewer, 'role', None); viewer_school = getattr(viewer, 'school', None); student_school = getattr(student, 'school', None)
    if viewer.is_superuser: can_view = True
    elif viewer_role in ['admin', 'director']:
         if viewer_school and viewer_school == student_school: can_view = True
    elif viewer_role == 'teacher':
         if viewer_school and viewer_school == student_school: can_view = True
    if not can_view: raise PermissionDenied("Бұл оқушының белсенділігін көруге рұқсатыңыз жоқ.")
    try: period_days = int(request.GET.get('days', '7')); period_days = 7 if period_days not in [7, 14, 30] else period_days
    except (ValueError, TypeError): period_days = 7
    start_date = timezone.now().date() - timedelta(days=period_days - 1)
    activities = ActivityLog.objects.filter(user=student, timestamp__date__gte=start_date).annotate(date=TruncDate('timestamp')).values('date', 'activity_type').annotate(count=Count('id')).order_by('date', 'activity_type')
    dates = [start_date + timedelta(days=i) for i in range(period_days)]; labels = [d.strftime('%d.%m') for d in dates]
    datasets_data = defaultdict(lambda: [0] * len(labels)); activity_type_map = dict(ActivityLog.ACTIVITY_TYPES); has_activity = False
    for activity in activities:
        try: label_index = labels.index(activity['date'].strftime('%d.%m')); activity_label = activity_type_map.get(activity['activity_type'], activity['activity_type']); datasets_data[activity_label][label_index] = activity['count']; has_activity = True
        except ValueError: logger.warning(f"Дата {activity['date']} из лога активности не найдена в метках графика."); pass
    chart_datasets = []; colors = ['rgba(54, 162, 235, 0.6)', 'rgba(75, 192, 192, 0.6)', 'rgba(255, 159, 64, 0.6)', 'rgba(255, 99, 132, 0.6)', 'rgba(153, 102, 255, 0.6)']; color_index = 0
    for activity_label in datasets_data.keys():
        if activity_label in datasets_data:
            data = datasets_data[activity_label]; current_color = colors[color_index % len(colors)]
            chart_datasets.append({'label': activity_label, 'data': data, 'backgroundColor': current_color, 'borderColor': current_color.replace('0.6', '1'), 'borderWidth': 1}); color_index += 1
    chart_title = f"{student.get_full_name() or student.username} - Соңғы {period_days} күндегі белсенділік"
    context = {'student': student, 'period_days': period_days, 'chart_labels_json': json.dumps(labels), 'chart_datasets_json': json.dumps(chart_datasets), 'chart_title': chart_title, 'has_activity': has_activity, 'current_view': 'view_student_activity', 'page_title': f"{student.get_full_name()} белсенділігі"}
    return render(request, 'kundelik/student_activity.html', context)

# ==================================
# БАҒАНЫ ӨҢДЕУ VIEWS (ЖАҢА)
# ==================================
@login_required
@teacher_required
def edit_daily_grade(request, pk):
    """Редактирование дневной оценки."""
    grade_object = get_object_or_404(DailyGrade, pk=pk)
    editor_user = request.user
    student_obj = grade_object.student
    student_school = getattr(student_obj, 'school', None)
    can_edit = False
    editor_role = getattr(editor_user, 'role', None)
    editor_school = getattr(editor_user, 'school', None)

    if grade_object.teacher == editor_user: can_edit = True
    elif editor_role in ['admin', 'director'] and editor_school and editor_school == student_school: can_edit = True
    elif editor_user.is_superuser: can_edit = True

    if not can_edit:
        messages.error(request, _("Бұл бағаны өңдеуге рұқсатыңыз жоқ."))
        # Мүмкін, оны қайда бағыттау керектігін ойластырған жөн, мысалы, баға қою бетіне немесе дашбордқа
        return redirect(reverse('add_daily_grade') + f'?class_id={grade_object.student.userprofile.school_class.pk}&subject_id={grade_object.subject.pk}&date={grade_object.date.strftime("%Y-%m-%d")}' if grade_object.student.userprofile and grade_object.student.userprofile.school_class else 'dashboard_schedule')

    students_queryset_for_edit = User.objects.filter(pk=student_obj.pk)

    if request.method == 'POST':
        form = DailyGradeForm(request.POST, instance=grade_object, school=student_school, user=editor_user, students_queryset=students_queryset_for_edit)
        # Форма өрістерін өшіру (disable)
        for field_name in ['student', 'subject', 'date', 'teacher']:
            if field_name in form.fields:
                form.fields[field_name].disabled = True

        if form.is_valid():
            try:
                edited_grade = form.save(commit=True) # term өрісі формада өңделеді деп есептейміз
                messages.success(request, _(f"{edited_grade.student.get_full_name()} оқушысының {edited_grade.subject.name} пәнінен ({edited_grade.date.strftime('%d.%m.%Y')}) алған бағасы сәтті өзгертілді."))
                redirect_url = reverse('add_daily_grade')
                try:
                     grade_date_str = edited_grade.date.strftime("%Y-%m-%d")
                     student_class_pk = edited_grade.student.userprofile.school_class.pk
                     subject_pk = edited_grade.subject.pk
                     redirect_url += f'?class_id={student_class_pk}&subject_id={subject_pk}&date={grade_date_str}'
                except Exception as e:
                    logger.warning(f"Не удалось сформировать URL для редиректа в edit_daily_grade: {e}")
                    # Егер URL құрастырылмаса, жай ғана 'add_daily_grade' бетіне бағыттау
                return redirect(redirect_url)
            except ValidationError as e:
                 logger.warning(f"[Edit Daily Grade] Validation error on save: {e}")
                 if hasattr(e, 'error_dict'):
                     for field, errors in e.message_dict.items():
                         form.add_error(field if field != '__all__' else None, errors)
                 else:
                     form.add_error(None, e.messages)
                 messages.error(request, _("Бағаны сақтау мүмкін болмады. Деректерді тексеріңіз."))
            except Exception as e:
                logger.exception("[Edit Daily Grade] Unexpected error saving grade:")
                messages.error(request, _(f"Бағаны сақтау кезінде күтпеген қате: {e}"))
        else:
             messages.error(request, _("Форма толтыруда қателер бар. Өрістерді тексеріңіз."))
             logger.warning(f"[Edit Daily Grade] Form is invalid: {form.errors.as_json()}")
             # Қате болған жағдайда да өрістер өшірулі қалуы керек
             for field_name in ['student', 'subject', 'date', 'teacher']:
                 if field_name in form.fields:
                     form.fields[field_name].disabled = True
    else: # GET request
        form = DailyGradeForm(instance=grade_object, school=student_school, user=editor_user, students_queryset=students_queryset_for_edit)
        # Форма өрістерін өшіру (disable)
        for field_name in ['student', 'subject', 'date', 'teacher']:
            if field_name in form.fields:
                form.fields[field_name].disabled = True

    context = {
        'form': form,
        'grade': grade_object,
        'current_view': 'edit_daily_grade', # Дашбордта активті меню үшін
        'page_title': _(f"{grade_object.student.get_full_name()} бағасын өңдеу ({grade_object.date.strftime('%d.%m.%Y')})")
    }
    # --- ШАБЛОН ЖОЛЫ ӨЗГЕРТІЛДІ ---
    return render(request, 'kundelik/daily_grade_edit.html', context)


@login_required
@teacher_required
def edit_exam_grade(request, pk):
    """Редактирование оценки за СОР/СОЧ."""
    grade_object = get_object_or_404(ExamGrade, pk=pk)
    editor_user = request.user
    student_obj = grade_object.student
    student_school = getattr(student_obj, 'school', None)
    can_edit = False
    editor_role = getattr(editor_user, 'role', None)
    editor_school = getattr(editor_user, 'school', None)

    if grade_object.teacher == editor_user: can_edit = True
    elif editor_role in ['admin', 'director'] and editor_school and editor_school == student_school: can_edit = True
    elif editor_user.is_superuser: can_edit = True

    if not can_edit:
        messages.error(request, _("Бұл бағаны өңдеуге рұқсатыңыз жоқ."))
        return redirect(reverse('add_exam_grade') + f'?class_id={grade_object.student.userprofile.school_class.pk}&subject_id={grade_object.subject.pk}&term={grade_object.term}&exam_type={grade_object.exam_type}' if grade_object.student.userprofile and grade_object.student.userprofile.school_class else 'dashboard_schedule')

    students_queryset_for_edit = User.objects.filter(pk=student_obj.pk)

    if request.method == 'POST':
        form = ExamGradeForm(request.POST, instance=grade_object, school=student_school, user=editor_user, students_queryset=students_queryset_for_edit)
        # Форма өрістерін өшіру (disable)
        for field_name in ['student', 'subject', 'date', 'term', 'exam_type', 'teacher']:
            if field_name in form.fields:
                form.fields[field_name].disabled = True

        if form.is_valid():
            try:
                edited_grade = form.save(commit=True)
                messages.success(request, _(f"{edited_grade.student.get_full_name()} оқушысының {edited_grade.subject.name} пәнінен ({edited_grade.get_exam_type_display()}, {edited_grade.term}-тоқсан) алған бағасы сәтті өзгертілді."))
                redirect_url = reverse('add_exam_grade')
                try:
                     student_class_pk = edited_grade.student.userprofile.school_class.pk
                     subject_pk = edited_grade.subject.pk
                     term = edited_grade.term
                     exam_type = edited_grade.exam_type
                     redirect_url += f'?class_id={student_class_pk}&subject_id={subject_pk}&term={term}&exam_type={exam_type}'
                except Exception as e:
                    logger.warning(f"Не удалось сформировать URL для редиректа в edit_exam_grade: {e}")
                return redirect(redirect_url)
            except Exception as e:
                logger.exception("[Edit Exam Grade] Unexpected error saving grade:")
                messages.error(request, _(f"Бағаны сақтау кезінде күтпеген қате: {e}"))
        else:
             messages.error(request, _("Форма толтыруда қателер бар. Өрістерді тексеріңіз."))
             logger.warning(f"[Edit Exam Grade] Form is invalid: {form.errors.as_json()}")
             # Қате болған жағдайда да өрістер өшірулі қалуы керек
             for field_name in ['student', 'subject', 'date', 'term', 'exam_type', 'teacher']:
                 if field_name in form.fields:
                     form.fields[field_name].disabled = True
    else: # GET request
        form = ExamGradeForm(instance=grade_object, school=student_school, user=editor_user, students_queryset=students_queryset_for_edit)
        # Форма өрістерін өшіру (disable)
        for field_name in ['student', 'subject', 'date', 'term', 'exam_type', 'teacher']:
            if field_name in form.fields:
                form.fields[field_name].disabled = True

    context = {
        'form': form,
        'grade': grade_object,
        'current_view': 'edit_exam_grade', # Дашбордта активті меню үшін
        'page_title': _(f"{grade_object.student.get_full_name()} {grade_object.get_exam_type_display()} бағасын өңдеу")
    }
    # --- ШАБЛОН ЖОЛЫ ӨЗГЕРТІЛДІ ---
    return render(request, 'kundelik/exam_grade_edit.html', context)


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
    elif is_student(request.user) or is_parent(request.user): return redirect('dashboard_grades')
    else: return redirect('dashboard_schedule')
@login_required
def teacher_schedule(request): messages.info(request, "Сіздің кестеңіз енді жеке кабинетте ('Дашборд') қолжетімді."); return redirect('dashboard_schedule')