from django.contrib.auth import login, logout, authenticate
from django.shortcuts import render, redirect, get_object_or_404  # Добавили get_object_or_404
from django.contrib.auth.forms import AuthenticationForm
from .models import Schedule, DailyGrade, ExamGrade, Class, Subject
from .forms import *
from django.contrib.auth.decorators import login_required
from django.http import HttpResponseForbidden

def home(request):
    return render(request, 'home.html')

@login_required
def schedule(request):
    user = request.user
    if user.role == 'student':
        schedules = Schedule.objects.filter(student=user).order_by('date', 'lesson_number')
    elif user.role == 'teacher':
        schedules = Schedule.objects.filter(teacher=user).order_by('date', 'lesson_number')
    elif user.role == 'parent':
        schedules = Schedule.objects.filter(student=user.parent_of).order_by('date', 'lesson_number')
    else:  # admin, director
        schedules = Schedule.objects.all().order_by('date', 'lesson_number')
    return render(request, 'schedule.html', {'schedules': schedules})

@login_required
def daily_grades(request, class_id=None):  # Изменено: принимаем class_id
    user = request.user
    if class_id:
        # Оценки для конкретного класса
        selected_class = get_object_or_404(Class, pk=class_id)
        if user.role == 'teacher':
            grades = DailyGrade.objects.filter(teacher=user, student__schedule__school_class=selected_class) #исправление
        elif user.role in ['admin', 'director']:
             grades = DailyGrade.objects.filter(student__schedule__school_class=selected_class) #исправление
        else:
            return HttpResponseForbidden("У вас нет прав для просмотра оценок этого класса.")
        return render(request, 'daily_grades.html', {'grades': grades, 'selected_class': selected_class})
    else:
        # Оценки текущего пользователя (как раньше)
        if user.role == 'student':
            grades = DailyGrade.objects.filter(student=user)
        elif user.role == 'teacher':
            grades = DailyGrade.objects.filter(teacher=user)
        elif user.role == 'parent':
            grades = DailyGrade.objects.filter(student=user.parent_of)
        else:
            grades = DailyGrade.objects.all()
        return render(request, 'daily_grades.html', {'grades': grades})


@login_required
def exam_grades(request, class_id=None):  # Изменено: принимаем class_id
    user = request.user
    if class_id:
        # Оценки за контрольные для конкретного класса
        selected_class = get_object_or_404(Class, pk=class_id)
        if user.role == 'teacher':
            grades = ExamGrade.objects.filter(teacher=user,  student__schedule__school_class=selected_class)  #исправил
        elif user.role in ['admin', 'director']:
            grades = ExamGrade.objects.filter( student__schedule__school_class=selected_class) #исправил
        else:
            return HttpResponseForbidden("У вас нет прав для просмотра оценок этого класса.")
        return render(request, 'exam_grades.html', {'grades': grades, 'selected_class': selected_class})
    else:
        # Оценки текущего пользователя (как раньше)
        if user.role == 'student':
            grades = ExamGrade.objects.filter(student=user)
        elif user.role == 'teacher':
            grades = ExamGrade.objects.filter(teacher=user)
        elif user.role == 'parent':
            grades = ExamGrade.objects.filter(student=user.parent_of)
        else:
            grades = ExamGrade.objects.all()
        return render(request, 'exam_grades.html', {'grades': grades})


@login_required
def add_person(request):
    if request.user.role not in ['admin', 'director']:
        return HttpResponseForbidden("У вас нет прав для добавления пользователей.")

    if request.method == 'POST':
        form = UserRegistrationForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect('home')
    else:
        form = UserRegistrationForm()
    return render(request, 'add_person.html', {'form': form})

@login_required
def add_school(request):
    if request.user.role != 'admin':
        return HttpResponseForbidden("У вас нет прав для добавления школ.")

    if request.method == 'POST':
        form = SchoolForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect('home')
    else:
        form = SchoolForm()
    return render(request, 'add_school.html', {'form': form})

@login_required
def add_class(request):
    if request.user.role not in ['admin', 'director']:
        return HttpResponseForbidden("У вас нет прав для добавления классов.")

    if request.method == 'POST':
        form = ClassForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect('home')  # Или на страницу списка классов
    else:
        form = ClassForm()
    return render(request, 'add_class.html', {'form': form})

@login_required
def add_subject(request):
     if request.user.role not in ['admin', 'director']:
        return HttpResponseForbidden("У вас нет прав для добавления предметов.")

     if request.method == 'POST':
        form = SubjectForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect('home')
     else:
        form = SubjectForm()
     return render(request, 'add_subject.html', {'form':form})

def register(request):
    if request.method == 'POST':
        form = UserRegistrationForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            return redirect('home')
    else:
        form = UserRegistrationForm()
    return render(request, 'register.html', {'form': form})

def user_login(request):
    if request.method == 'POST':
        form = AuthenticationForm(data=request.POST)
        if form.is_valid():
            user = form.get_user()
            login(request, user)
            return redirect('home')
    else:
        form = AuthenticationForm()
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
            schedule = form.save(commit=False)
            if request.user.role == 'teacher':
                schedule.teacher = request.user
            schedule.save()
            return redirect('schedule')
    else:
        form = ScheduleForm()
        if request.user.role == 'teacher':
            form.fields['teacher'].initial = request.user
            form.fields['teacher'].widget = forms.HiddenInput()

    return render(request, 'add_schedule.html', {'form': form})

@login_required
def add_daily_grade(request):
    if request.user.role not in ['teacher', 'admin', 'director']:
         return HttpResponseForbidden("У вас нет прав для выставления оценок.")

    if request.method == 'POST':
        form = DailyGradeForm(request.POST)
        if form.is_valid():
            grade = form.save(commit=False)
            if request.user.role == 'teacher':
                grade.teacher = request.user
            grade.save()
            return redirect('daily_grades')  # Перенаправляем на страницу с ежедневными оценками
    else:
        form = DailyGradeForm()
        if request.user.role == 'teacher':
            form.fields['teacher'].initial = request.user
            form.fields['teacher'].widget = forms.HiddenInput()

    return render(request, 'add_daily_grade.html', {'form': form})

@login_required
def add_exam_grade(request):
    if request.user.role not in ['teacher', 'admin', 'director']:
        return HttpResponseForbidden("У вас нет прав для выставления оценок.")

    if request.method == 'POST':
        form = ExamGradeForm(request.POST)
        if form.is_valid():
            grade = form.save(commit=False)
            if request.user.role == 'teacher':
                grade.teacher = request.user
            grade.save()
            return redirect('exam_grades')
    else:
        form = ExamGradeForm()
        if request.user.role == 'teacher':
            form.fields['teacher'].initial = request.user
            form.fields['teacher'].widget = forms.HiddenInput()
    return render(request, 'add_exam_grade.html', {'form': form})

@login_required
def class_list(request):
    if request.user.role not in ['teacher', 'admin', 'director', 'parent']:
        return HttpResponseForbidden("У вас нет прав для просмотра списка классов.")
    classes = Class.objects.all()
    return render(request, 'class_list.html', {'classes': classes})