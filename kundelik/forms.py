# kundelik/forms.py

from django import forms
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm
from django.contrib.auth import get_user_model
from .models import UserProfile, School, Schedule, DailyGrade, ExamGrade, Class, Subject
from django.forms.widgets import DateInput # Убрали TimeInput

User = get_user_model()

# --- ФОРМА РЕГИСТРАЦИИ ---
class UserRegistrationForm(UserCreationForm):
    role = forms.ChoiceField(choices=User.ROLE_CHOICES, label="Рөл")
    school = forms.ModelChoiceField(queryset=School.objects.all(), required=False, label="Мектеп")
    first_name = forms.CharField(max_length=150, label="Аты")
    last_name = forms.CharField(max_length=150, label="Тегі")
    # Отчество будет в UserProfileEditForm
    parent_of = forms.ModelChoiceField(
        queryset=User.objects.filter(role='student'), required=False, label="Оқушы (ата-ана үшін)"
    )
    email = forms.EmailField(required=False, label="Электрондық пошта") # Сделали необязательным

    class Meta(UserCreationForm.Meta):
        model = User
        # Убрали surname, добавили email и доп поля
        fields = UserCreationForm.Meta.fields + ('role', 'school', 'first_name', 'last_name', 'parent_of', 'email')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field_name, field in self.fields.items():
            field_widget = field.widget
            css_class = 'form-control'
            if isinstance(field_widget, forms.Select):
                css_class = 'form-select'
            elif isinstance(field_widget, forms.CheckboxInput):
                css_class = 'form-check-input'
            # Добавляем отступ снизу
            field_widget.attrs.update({'class': f'{css_class} mb-3'})

# --- ФОРМА ШКОЛЫ ---
class SchoolForm(forms.ModelForm):
    class Meta:
        model = School
        fields = ['name']
        widgets = {'name': forms.TextInput(attrs={'class': 'form-control'})}

# --- ФОРМА КЛАССА ---
class ClassForm(forms.ModelForm):
    subjects = forms.ModelMultipleChoiceField(
        queryset=Subject.objects.all(), widget=forms.CheckboxSelectMultiple,
        required=False, label="Осы сыныптың пәндері"
    )

    class Meta:
        model = Class
        fields = ['name', 'school', 'teacher', 'subjects']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'school': forms.Select(attrs={'class': 'form-select'}),
            'teacher': forms.Select(attrs={'class': 'form-select'}),
        }

    def __init__(self, *args, **kwargs):
        school = kwargs.pop('school', None) # Извлекаем школу для фильтрации
        super().__init__(*args, **kwargs)
        # Фильтруем queryset'ы
        if school:
            self.fields['teacher'].queryset = User.objects.filter(school=school, role__in=['teacher', 'director', 'admin'])
            self.fields['subjects'].queryset = Subject.objects.filter(school=school)
        elif self.instance and self.instance.school: # Если редактируем существующий класс
             self.fields['teacher'].queryset = User.objects.filter(school=self.instance.school, role__in=['teacher', 'director', 'admin'])
             self.fields['subjects'].queryset = Subject.objects.filter(school=self.instance.school)
        else: # Если новая запись и школа не передана (напр., для суперюзера)
            self.fields['teacher'].queryset = User.objects.filter(role__in=['teacher', 'director', 'admin'])
            self.fields['subjects'].queryset = Subject.objects.all()


# --- ФОРМА ПРЕДМЕТА ---
class SubjectForm(forms.ModelForm):
    class Meta:
        model = Subject
        fields = ['name', 'school']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'school': forms.Select(attrs={'class': 'form-select'}),
        }

# --- ФОРМА РАСПИСАНИЯ (БЕЗ ВРЕМЕНИ) ---
class ScheduleForm(forms.ModelForm):
    class Meta:
        model = Schedule
        # Убрали time_start, time_end, student. Добавили topic, school_class
        fields = ['date', 'lesson_number', 'school_class', 'subject', 'teacher', 'topic', 'task', 'status']
        widgets = {
            'date': DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'lesson_number': forms.NumberInput(attrs={'class': 'form-control'}),
            'school_class': forms.Select(attrs={'class': 'form-select'}),
            'subject': forms.Select(attrs={'class': 'form-select'}),
            'teacher': forms.Select(attrs={'class': 'form-select'}),
            'topic': forms.TextInput(attrs={'class': 'form-control'}),
            'task': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'status': forms.Select(attrs={'class': 'form-select'}),
        }

    def __init__(self, *args, **kwargs):
        # Фильтрация по школе пользователя (передается из view)
        school = kwargs.pop('school', None)
        user = kwargs.pop('user', None) # Получаем пользователя для установки учителя по умолч.
        super().__init__(*args, **kwargs)

        if school:
            self.fields['school_class'].queryset = Class.objects.filter(school=school)
            self.fields['teacher'].queryset = User.objects.filter(school=school, role__in=['teacher', 'director', 'admin'])
            self.fields['subject'].queryset = Subject.objects.filter(school=school)
        # Если пользователь - учитель, ставим его по умолчанию
        if user and getattr(user, 'role', None) == 'teacher':
             self.fields['teacher'].initial = user
             # self.fields['teacher'].widget = forms.HiddenInput() # Можно скрыть


# --- ФОРМА ДНЕВНЫХ ОЦЕНОК ---
class DailyGradeForm(forms.ModelForm):
    class Meta:
        model = DailyGrade
        fields = ['student', 'teacher', 'subject', 'date', 'term', 'grade', 'comment']
        widgets = {
            'student': forms.Select(attrs={'class': 'form-select'}),
            'teacher': forms.Select(attrs={'class': 'form-select'}), # Будет скрыто во view
            'subject': forms.Select(attrs={'class': 'form-select'}),
            'date': DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'term': forms.NumberInput(attrs={'class': 'form-control', 'min': '1', 'max': '4'}),
            'grade': forms.NumberInput(attrs={'class': 'form-control', 'min': '1', 'max': '5'}),
            'comment': forms.TextInput(attrs={'class': 'form-control'}),
        }

    def __init__(self, *args, **kwargs):
        # Фильтрация по школе учителя (передается из view)
        school = kwargs.pop('school', None)
        user = kwargs.pop('user', None) # Получаем учителя
        super().__init__(*args, **kwargs)

        if school:
            self.fields['student'].queryset = User.objects.filter(school=school, role='student').order_by('last_name', 'first_name')
            # TODO: Фильтровать предметы по учителю, если есть связь
            self.fields['subject'].queryset = Subject.objects.filter(school=school)
        # Устанавливаем учителя и скрываем поле
        if user:
             self.fields['teacher'].initial = user
             self.fields['teacher'].widget = forms.HiddenInput()


# --- ФОРМА ЭКЗАМЕНАЦИОННЫХ ОЦЕНОК ---
class ExamGradeForm(forms.ModelForm):
    class Meta:
        model = ExamGrade
        fields = ['student', 'teacher', 'subject', 'date', 'term', 'exam_type', 'grade', 'max_grade', 'comment']
        widgets = {
            'student': forms.Select(attrs={'class': 'form-select'}),
            'teacher': forms.Select(attrs={'class': 'form-select'}), # Будет скрыто во view
            'subject': forms.Select(attrs={'class': 'form-select'}),
            'date': DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'term': forms.NumberInput(attrs={'class': 'form-control', 'min': '1', 'max': '4'}),
            'exam_type': forms.Select(attrs={'class': 'form-select'}),
            'grade': forms.NumberInput(attrs={'class': 'form-control'}),
            'max_grade': forms.NumberInput(attrs={'class': 'form-control'}),
            'comment': forms.TextInput(attrs={'class': 'form-control'}),
        }

    def __init__(self, *args, **kwargs):
        # Фильтрация по школе учителя (передается из view)
        school = kwargs.pop('school', None)
        user = kwargs.pop('user', None) # Получаем учителя
        super().__init__(*args, **kwargs)

        if school:
            self.fields['student'].queryset = User.objects.filter(school=school, role='student').order_by('last_name', 'first_name')
             # TODO: Фильтровать предметы по учителю
            self.fields['subject'].queryset = Subject.objects.filter(school=school)
        # Устанавливаем учителя и скрываем поле
        if user:
             self.fields['teacher'].initial = user
             self.fields['teacher'].widget = forms.HiddenInput()


# --- ФОРМЫ РЕДАКТИРОВАНИЯ ПРОФИЛЯ ---
class UserEditForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ('first_name', 'last_name', 'email') # Только эти поля User

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['first_name'].widget.attrs.update({'class': 'form-control mb-3'})
        self.fields['last_name'].widget.attrs.update({'class': 'form-control mb-3'})
        self.fields['email'].widget.attrs.update({'class': 'form-control mb-3'})
        self.fields['email'].required = False

class UserProfileEditForm(forms.ModelForm):
    date_of_birth = forms.DateField(
        widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
        required=False, label="Туған күні"
    )
    avatar = forms.ImageField(
        widget=forms.ClearableFileInput(attrs={'class': 'form-control'}),
        required=False, label="Профиль суреті (жаңа)"
    )
    grade = forms.ModelChoiceField(
        queryset=Class.objects.none(), # Будет отфильтровано во view/init
        required=False, widget=forms.Select(attrs={'class': 'form-select'}), label="Сыныбы"
    )

    class Meta:
        model = UserProfile
        fields = ('patronymic', 'date_of_birth', 'gender', 'grade', 'avatar')
        # 'user' исключать не нужно, т.к. его нет в fields

    def __init__(self, *args, **kwargs):
        # Получаем пользователя из instance связанного профиля
        user = kwargs.get('instance').user if kwargs.get('instance') else None
        super().__init__(*args, **kwargs)

        self.fields['patronymic'].widget.attrs.update({'class': 'form-control mb-3'})
        self.fields['patronymic'].required = False
        self.fields['gender'].widget.attrs.update({'class': 'form-select mb-3'})
        self.fields['gender'].required = False
        self.fields['grade'].widget.attrs.update({'class': 'form-select mb-3'})
        self.fields['grade'].required = False
        # Фильтруем классы по школе пользователя
        if user and hasattr(user, 'school') and user.school:
            self.fields['grade'].queryset = Class.objects.filter(school=user.school)
        else:
             # Если школа не определена, оставляем пустым или показываем все классы
             self.fields['grade'].queryset = Class.objects.all()


# --- ФОРМА АУТЕНТИФИКАЦИИ ---
class CustomAuthenticationForm(AuthenticationForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['username'].widget = forms.TextInput(attrs={
            'class': 'form-control mb-3', 'placeholder': 'Логин', 'autofocus': True
        })
        self.fields['password'].widget = forms.PasswordInput(attrs={
            'class': 'form-control mb-3', 'placeholder': 'Құпия сөз'
        })