# kundelik/views.py

from django.contrib.auth import login, logout, authenticate
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.forms import AuthenticationForm, PasswordResetForm
from django.urls import reverse_lazy
from django import forms # Добавь импорт forms
from django.views.decorators.csrf import csrf_exempt

from .models import Schedule, DailyGrade, ExamGrade, Class, Subject, User # Убедись, что User импортирован
from .forms import *
from django.contrib.auth.decorators import login_required
from django.http import HttpResponseForbidden
from collections import defaultdict
from django.contrib.auth.views import PasswordResetView

def home(request):
    # Используем home.html из startup/templates/
    return render(request, 'home.html')

@login_required
def schedule(request):
    user = request.user
    schedules = None # Инициализируем
    if user.role == 'student':
        schedules = Schedule.objects.filter(student=user).order_by('date', 'lesson_number')
    elif user.role == 'teacher':
        # Для учителя нужно показывать расписание для его классов
         classes_taught = Class.objects.filter(teacher=user)
         schedules = Schedule.objects.filter(school_class__in=classes_taught).order_by('date', 'lesson_number')
        # Или если ты хочешь показывать только те записи, где он явно указан как учитель урока:
        # schedules = Schedule.objects.filter(teacher=user).order_by('date', 'lesson_number')
    elif user.role == 'parent':
        # Убедись, что у родителя есть ссылка на ребенка в parent_of
        if user.parent_of:
             schedules = Schedule.objects.filter(student=user.parent_of).order_by('date', 'lesson_number')
        else:
             schedules = Schedule.objects.none() # Пустой queryset, если ребенок не привязан
    elif user.role in ['admin', 'director']:
        # Показываем всё расписание для школы админа/директора
        if user.school:
             schedules = Schedule.objects.filter(school_class__school=user.school).order_by('date', 'lesson_number')
        else:
             schedules = Schedule.objects.all().order_by('date', 'lesson_number') # Или всё, если школы нет
    else:
        schedules = Schedule.objects.none()

    # Предполагаем, что есть шаблон parents.html для родителей и учеников,
    # и teachers_list.html для учителей (хотя он выглядит как профиль учителя)
    # Создадим общий шаблон 'schedule_display.html' или используем разные
    # В parents.html логика отображения расписания
    template_name = 'parents.html' # По умолчанию используем родительский/ученический вид
    if user.role == 'teacher':
         template_name = 'teachers_list.html' # Используем вид учителя (возможно, нужно создать отдельный шаблон)

    # Если нужен общий шаблон для всех:
    # template_name = 'schedule_display.html' # Создай этот файл

    # Пока используем parents.html и teachers_list.html как примеры
    return render(request, template_name, {'schedules': schedules})


@login_required
def daily_grades(request, class_id=None):
    user = request.user
    grades = DailyGrade.objects.none()
    selected_class = None
    classes_available = Class.objects.none()

    if user.school:
        classes_available = Class.objects.filter(school=user.school)

    if class_id:
        selected_class = get_object_or_404(Class, pk=class_id, school=user.school) # Убедимся, что класс из школы юзера
        if user.role == 'teacher':
            # Учитель видит оценки только своего класса или всех, если он директор/админ?
            # Пока оставим логику, что учитель видит оценки учеников своего класса
            grades = DailyGrade.objects.filter(subject__school=user.school, student__school=user.school, student__school_class=selected_class).distinct() # Фильтруем по классу
        elif user.role in ['admin', 'director']:
             grades = DailyGrade.objects.filter(subject__school=user.school, student__school=user.school, student__school_class=selected_class).distinct()
        else: # Студент или родитель не должны видеть оценки по классу напрямую тут
            return HttpResponseForbidden("У вас нет прав для просмотра оценок этого класса.")

    else: # Если class_id не указан
        if user.role == 'student':
            grades = DailyGrade.objects.filter(student=user)
        elif user.role == 'teacher':
            # Учитель видит оценки, которые он поставил
            grades = DailyGrade.objects.filter(teacher=user)
            # Или оценки всех учеников его классов? Зависит от ТЗ.
            # classes_taught = Class.objects.filter(teacher=user)
            # grades = DailyGrade.objects.filter(student__school_class__in=classes_taught)
        elif user.role == 'parent':
            if user.parent_of:
                 grades = DailyGrade.objects.filter(student=user.parent_of)
        elif user.role in ['admin', 'director']:
            if user.school:
                 grades = DailyGrade.objects.filter(subject__school=user.school, student__school=user.school)
            else:
                 grades = DailyGrade.objects.all()

    # Нужен шаблон для отображения оценок, например, 'grades_display.html'
    # Пока используем 'parents.html' как плейсхолдер, нужно будет создать/адаптировать
    return render(request, 'parents.html', { # Замени 'parents.html' на актуальный шаблон
        'grades': grades,
        'selected_class': selected_class,
        'classes_available': classes_available, # Для выбора класса
        'grade_type': 'daily'
    })


@login_required
def exam_grades(request, class_id=None):
    user = request.user
    grades = ExamGrade.objects.none()
    selected_class = None
    classes_available = Class.objects.none()

    if user.school:
        classes_available = Class.objects.filter(school=user.school)

    if class_id:
        selected_class = get_object_or_404(Class, pk=class_id, school=user.school)
        if user.role == 'teacher':
             grades = ExamGrade.objects.filter(subject__school=user.school, student__school=user.school, student__school_class=selected_class).distinct()
        elif user.role in ['admin', 'director']:
             grades = ExamGrade.objects.filter(subject__school=user.school, student__school=user.school, student__school_class=selected_class).distinct()
        else:
             return HttpResponseForbidden("У вас нет прав для просмотра оценок этого класса.")
    else:
        if user.role == 'student':
            grades = ExamGrade.objects.filter(student=user)
        elif user.role == 'teacher':
            grades = ExamGrade.objects.filter(teacher=user)
        elif user.role == 'parent':
             if user.parent_of:
                 grades = ExamGrade.objects.filter(student=user.parent_of)
        elif user.role in ['admin', 'director']:
             if user.school:
                 grades = ExamGrade.objects.filter(subject__school=user.school, student__school=user.school)
             else:
                 grades = ExamGrade.objects.all()

    # Используем тот же шаблон, что и для дневных оценок, или отдельный
    return render(request, 'parents.html', { # Замени 'parents.html' на актуальный шаблон
         'grades': grades,
         'selected_class': selected_class,
         'classes_available': classes_available,
         'grade_type': 'exam'
    })


@login_required
def add_person(request):
    if request.user.role not in ['admin', 'director']:
        return HttpResponseForbidden("У вас нет прав для добавления пользователей.")

    if request.method == 'POST':
        form = UserRegistrationForm(request.POST)
        if form.is_valid():
            user = form.save(commit=False)
            user.school = request.user.school # Присваиваем школу текущего админа/директора
            user.save()
            # Если создается родитель, нужно связать его с ребенком
            # Это лучше делать на этапе редактирования пользователя или отдельной формой
            return redirect('home') # Или на страницу списка пользователей
    else:
        form = UserRegistrationForm()
        # Ограничиваем выбор школы, если это директор
        if request.user.role == 'director' and request.user.school:
             form.fields['school'].queryset = School.objects.filter(pk=request.user.school.pk)
             form.fields['school'].initial = request.user.school
             form.fields['school'].widget = forms.HiddenInput() # Скрываем поле школы для директора
        elif request.user.role == 'admin':
             form.fields['school'].queryset = School.objects.all() # Админ видит все школы

        # Ограничиваем выбор учеников для родителя только учениками из той же школы
        if request.user.school:
             form.fields['parent_of'].queryset = User.objects.filter(role='student', school=request.user.school)
        else: # Если админ без школы (суперюзер), показываем всех студентов
             form.fields['parent_of'].queryset = User.objects.filter(role='student')


    # Нужен шаблон 'add_person.html'
    return render(request, 'add_person.html', {'form': form}) # Создай этот шаблон

@login_required
def add_school(request):
    if request.user.role != 'admin':
        return HttpResponseForbidden("У вас нет прав для добавления школ.")

    if request.method == 'POST':
        form = SchoolForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect('home') # Или на список школ
    else:
        form = SchoolForm()
    # Нужен шаблон 'add_school.html'
    return render(request, 'add_school.html', {'form': form}) # Создай этот шаблон

@login_required
def add_class(request):
    if request.user.role not in ['admin', 'director']:
        return HttpResponseForbidden("У вас нет прав для добавления классов.")

    if request.method == 'POST':
        form = ClassForm(request.POST)
        if form.is_valid():
            class_instance = form.save(commit=False)
            if request.user.role == 'director':
                class_instance.school = request.user.school # Директор добавляет класс в свою школу
            # Убедимся, что выбранный учитель из той же школы
            if class_instance.teacher and class_instance.teacher.school != class_instance.school:
                 form.add_error('teacher', 'Учитель должен быть из той же школы, что и класс.')
            else:
                class_instance.save()
                return redirect('home') # Или на страницу списка классов
    else:
        form = ClassForm()
        # Ограничиваем выбор школы и учителя для директора
        if request.user.role == 'director' and request.user.school:
            form.fields['school'].queryset = School.objects.filter(pk=request.user.school.pk)
            form.fields['school'].initial = request.user.school
            form.fields['school'].widget = forms.HiddenInput()
            form.fields['teacher'].queryset = User.objects.filter(role='teacher', school=request.user.school)
        elif request.user.role == 'admin':
            # Админ может выбрать любую школу, учителя фильтруются динамически (сложнее) или после выбора школы
            # Пока оставим выбор всех учителей
            form.fields['teacher'].queryset = User.objects.filter(role='teacher')


    # Нужен шаблон 'add_class.html'
    return render(request, 'add_class.html', {'form': form}) # Создай этот шаблон

@login_required
def add_subject(request):
     if request.user.role not in ['admin', 'director']:
        return HttpResponseForbidden("У вас нет прав для добавления предметов.")

     if request.method == 'POST':
        form = SubjectForm(request.POST)
        if form.is_valid():
            subject = form.save(commit=False)
            if request.user.role == 'director':
                 subject.school = request.user.school # Директор добавляет предмет в свою школу
            subject.save()
            return redirect('home') # Или на список предметов
     else:
        form = SubjectForm()
        if request.user.role == 'director' and request.user.school:
             form.fields['school'].queryset = School.objects.filter(pk=request.user.school.pk)
             form.fields['school'].initial = request.user.school
             form.fields['school'].widget = forms.HiddenInput()

     # Нужен шаблон 'add_subject.html'
     return render(request, 'add_subject.html', {'form':form}) # Создай этот шаблон

def register(request):
    if request.method == 'POST':
        form = UserRegistrationForm(request.POST) # Используем нашу форму
        if form.is_valid():
            user = form.save()
            login(request, user)
            return redirect('home')
    else:
        form = UserRegistrationForm()
    # Нужен шаблон 'register.html'
    return render(request, 'register.html', {'form': form}) # Создай этот шаблон

@csrf_exempt
def user_login(request):
    if request.user.is_authenticated: # Если уже вошел, перенаправляем
         return redirect('home')
    if request.method == 'POST':
        form = CustomAuthenticationForm(data=request.POST) # Используем нашу кастомную форму
        if form.is_valid():
            user = form.get_user()
            login(request, user)
            # Перенаправление в зависимости от роли?
            # if user.role == 'student': return redirect('student_dashboard')
            return redirect('home') # Пока на главную
    else:
        form = CustomAuthenticationForm()
    # Используем login.html из startup/templates/
    return render(request, 'login.html', {'form': form})

def user_logout(request):
    logout(request)
    return redirect('home')

@login_required
def add_schedule(request):
    if request.user.role not in ['teacher', 'admin', 'director']:
        return HttpResponseForbidden("У вас нет прав для добавления расписания.")

    if request.method == 'POST':
        form = ScheduleForm(request.POST)
        if form.is_valid():
            schedule_item = form.save(commit=False)
            # Проверка: учитель, студент и класс должны быть из одной школы
            is_valid = True
            if schedule_item.teacher.school != schedule_item.student.school or \
               schedule_item.student.school != schedule_item.school_class.school:
                is_valid = False
                # Можно добавить конкретные ошибки к полям формы
                form.add_error(None, "Учитель, ученик и класс должны принадлежать одной школе.")

            if request.user.role == 'teacher':
                schedule_item.teacher = request.user # Учитель добавляет запись от своего имени
                if schedule_item.teacher.school != schedule_item.student.school:
                     is_valid = False
                     form.add_error('student', "Выбранный ученик не из вашей школы.")
                if schedule_item.teacher.school != schedule_item.school_class.school:
                     is_valid = False
                     form.add_error('school_class', "Выбранный класс не из вашей школы.")

            if is_valid:
                schedule_item.save()
                return redirect('schedule') # Перенаправление на страницу расписания
        # Если форма невалидна, рендерим её снова с ошибками
    else:
        form = ScheduleForm()
        user_school = request.user.school
        if user_school:
            # Фильтруем поля формы по школе текущего пользователя
            form.fields['teacher'].queryset = User.objects.filter(role='teacher', school=user_school)
            form.fields['student'].queryset = User.objects.filter(role='student', school=user_school)
            form.fields['subject'].queryset = Subject.objects.filter(school=user_school)
            form.fields['school_class'].queryset = Class.objects.filter(school=user_school)

        if request.user.role == 'teacher':
            form.fields['teacher'].initial = request.user
            form.fields['teacher'].widget = forms.HiddenInput() # Скрываем поле учителя

    # Нужен шаблон 'add_schedule.html'
    return render(request, 'add_schedule.html', {'form': form}) # Создай этот шаблон

@login_required
def add_daily_grade(request):
    if request.user.role not in ['teacher', 'admin', 'director']:
         return HttpResponseForbidden("У вас нет прав для выставления оценок.")

    if request.method == 'POST':
        form = DailyGradeForm(request.POST)
        if form.is_valid():
            grade = form.save(commit=False)
            # Проверка: учитель, студент и предмет должны быть из одной школы
            is_valid = True
            if grade.teacher.school != grade.student.school or \
               grade.student.school != grade.subject.school:
                 is_valid = False
                 form.add_error(None, "Учитель, ученик и предмет должны принадлежать одной школе.")

            if request.user.role == 'teacher':
                 grade.teacher = request.user # Учитель ставит оценку от своего имени
                 if grade.teacher.school != grade.student.school:
                     is_valid = False
                     form.add_error('student', "Выбранный ученик не из вашей школы.")
                 if grade.teacher.school != grade.subject.school:
                     is_valid = False
                     form.add_error('subject', "Выбранный предмет не из вашей школы.")

            if is_valid:
                grade.save()
                # Перенаправление на страницу оценок, возможно, с фильтром по классу
                return redirect('daily_grades') # Или daily_grades_by_class, если оценка ставилась для класса
        # Если форма невалидна
    else:
        form = DailyGradeForm()
        user_school = request.user.school
        if user_school:
            form.fields['teacher'].queryset = User.objects.filter(role='teacher', school=user_school)
            form.fields['student'].queryset = User.objects.filter(role='student', school=user_school)
            form.fields['subject'].queryset = Subject.objects.filter(school=user_school)

        if request.user.role == 'teacher':
            form.fields['teacher'].initial = request.user
            form.fields['teacher'].widget = forms.HiddenInput()

    # Нужен шаблон 'add_daily_grade.html'
    return render(request, 'add_daily_grade.html', {'form': form}) # Создай этот шаблон

@login_required
def add_exam_grade(request):
    if request.user.role not in ['teacher', 'admin', 'director']:
        return HttpResponseForbidden("У вас нет прав для выставления оценок.")

    if request.method == 'POST':
        form = ExamGradeForm(request.POST)
        if form.is_valid():
            grade = form.save(commit=False)
            # Аналогичные проверки школы
            is_valid = True
            if grade.teacher.school != grade.student.school or \
               grade.student.school != grade.subject.school:
                 is_valid = False
                 form.add_error(None, "Учитель, ученик и предмет должны принадлежать одной школе.")

            if request.user.role == 'teacher':
                 grade.teacher = request.user
                 if grade.teacher.school != grade.student.school:
                     is_valid = False
                     form.add_error('student', "Выбранный ученик не из вашей школы.")
                 if grade.teacher.school != grade.subject.school:
                     is_valid = False
                     form.add_error('subject', "Выбранный предмет не из вашей школы.")

            if is_valid:
                 grade.save()
                 return redirect('exam_grades') # Или exam_grades_by_class
        # Если форма невалидна
    else:
        form = ExamGradeForm()
        user_school = request.user.school
        if user_school:
             form.fields['teacher'].queryset = User.objects.filter(role='teacher', school=user_school)
             form.fields['student'].queryset = User.objects.filter(role='student', school=user_school)
             form.fields['subject'].queryset = Subject.objects.filter(school=user_school)

        if request.user.role == 'teacher':
             form.fields['teacher'].initial = request.user
             form.fields['teacher'].widget = forms.HiddenInput()

    # Нужен шаблон 'add_exam_grade.html'
    return render(request, 'add_exam_grade.html', {'form': form}) # Создай этот шаблон

@login_required
def class_list(request):
    # Доступ могут иметь все, кто привязан к школе, но для родителей/учеников показывать только их класс?
    # Пока оставим показ всех классов школы
    user = request.user
    classes = Class.objects.none()
    if user.school:
        classes = Class.objects.filter(school=user.school)
    elif user.is_superuser: # Суперпользователь видит все классы
         classes = Class.objects.all()
    else: # Пользователь без школы (или не разрешенная роль) не видит классы
        return HttpResponseForbidden("У вас нет прав для просмотра списка классов или вы не привязаны к школе.")

    # Нужен шаблон 'class_list.html'
    return render(request, 'class_list.html', {'classes': classes}) # Создай этот шаблон

@login_required
def journal(request):
    user = request.user
    schedules = Schedule.objects.none()
    # Логика получения расписания как в view 'schedule', но для journal.html
    if user.role == 'student':
        schedules = Schedule.objects.filter(student=user).order_by('date', 'lesson_number')
    elif user.role == 'teacher':
         classes_taught = Class.objects.filter(teacher=user)
         schedules = Schedule.objects.filter(school_class__in=classes_taught).order_by('date', 'lesson_number')
    elif user.role == 'parent':
        if user.parent_of:
             schedules = Schedule.objects.filter(student=user.parent_of).order_by('date', 'lesson_number')
    elif user.role in ['admin', 'director']:
        if user.school:
             schedules = Schedule.objects.filter(school_class__school=user.school).order_by('date', 'lesson_number')
        else:
             schedules = Schedule.objects.all().order_by('date', 'lesson_number')

    # Группировка по дате для удобного отображения в шаблоне
    schedules_by_date = defaultdict(list)
    for s in schedules:
        schedules_by_date[s.date].append(s)

    # Используем journal.html из startup/templates/
    return render(request, 'journal.html', {'schedules_by_date': dict(schedules_by_date)}) # Преобразуем в dict для шаблона

@login_required
def teacher_schedule(request):
    # Эта view, возможно, дублирует логику schedule() для учителя.
    # Можно либо удалить ее и использовать schedule(), либо сделать ее специфичной для учителя.
    # Пока оставляем как есть, но рендерит шаблон teachers_list.html
    if request.user.role != 'teacher':
        return HttpResponseForbidden("У вас нет прав для просмотра этого расписания.")

    schedules = Schedule.objects.filter(teacher=request.user).order_by('date', 'lesson_number')
    # Используем teachers_list.html из startup/templates/
    return render(request, 'teachers_list.html', {'schedules': schedules})

def about(request):
    # Используем about_us.html из startup/templates/
    return render(request, 'about_us.html')

def recommendations(request):
    # Используем recommendations.html из startup/templates/
    return render(request, 'recommendations.html')

# Представление для сброса пароля
class CustomPasswordResetView(PasswordResetView):
    # Используем recovery.html из startup/templates/
    template_name = 'recovery.html'
    email_template_name = 'password_reset_email.html' # Создай этот шаблон для текста письма
    subject_template_name = 'password_reset_subject.txt' # Создай этот шаблон для темы письма
    success_url = reverse_lazy('password_reset_done')
    # Можно добавить форму, если нужна кастомизация
    # form_class = CustomPasswordResetForm

# Представления для страниц после сброса пароля (используют стандартные шаблоны Django или твои)
# Убедись, что эти шаблоны существуют в startup/templates/ или настрой пути:
# password_reset_done.html
# password_reset_confirm.html
# password_reset_complete.html
# password_reset_email.html
# password_reset_subject.txt