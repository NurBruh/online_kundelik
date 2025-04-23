# kundelik/forms.py

from django import forms
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm
from django.contrib.auth import get_user_model
from .models import UserProfile, School, Schedule, DailyGrade, ExamGrade, Class, Subject
from django.forms.widgets import DateInput, TimeInput # TimeInput қосылды
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _

User = get_user_model()

# --- ФОРМА РЕГИСТРАЦИИ ---
# (Өзгеріссіз қалды)
class UserRegistrationForm(UserCreationForm):
    role = forms.ChoiceField(choices=User.ROLE_CHOICES, label="Рөл", widget=forms.Select(attrs={'class': 'form-select mb-3'}))
    school = forms.ModelChoiceField(
        queryset=School.objects.all().order_by('name'), required=False, label="Мектеп",
        widget=forms.Select(attrs={'class': 'form-select mb-3'})
    )
    first_name = forms.CharField(max_length=150, label="Аты", widget=forms.TextInput(attrs={'class': 'form-control mb-3'}))
    last_name = forms.CharField(max_length=150, label="Тегі", widget=forms.TextInput(attrs={'class': 'form-control mb-3'}))
    parent_of = forms.ModelChoiceField(
        queryset=User.objects.filter(role='student').order_by('last_name', 'first_name'),
        required=False, label="Оқушы (ата-ана үшін)",
        widget=forms.Select(attrs={'class': 'form-select mb-3'})
    )
    email = forms.EmailField(required=True, label="Электрондық пошта", widget=forms.EmailInput(attrs={'class': 'form-control mb-3'}))
    iin = forms.CharField(required=False, label="ЖСН", max_length=12, widget=forms.TextInput(attrs={'class': 'form-control mb-3'}))

    class Meta(UserCreationForm.Meta):
        model = User
        fields = UserCreationForm.Meta.fields + ('email', 'role', 'school', 'first_name', 'last_name', 'parent_of', 'iin')

    def __init__(self, *args, **kwargs):
        self.requesting_user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        if self.requesting_user and not self.requesting_user.is_superuser and getattr(self.requesting_user, 'role', None) in ['admin', 'director']:
            user_school = getattr(self.requesting_user, 'school', None)
            if user_school:
                self.fields['school'].queryset = School.objects.filter(pk=user_school.pk)
                self.fields['school'].initial = user_school
                self.fields['school'].disabled = True
                self.fields['parent_of'].queryset = User.objects.filter(role='student', school=user_school).order_by('last_name', 'first_name')
            else:
                self.fields['school'].queryset = School.objects.none()
                self.fields['parent_of'].queryset = User.objects.none()

# --- ФОРМА ШКОЛЫ ---
# (Өзгеріссіз қалды)
class SchoolForm(forms.ModelForm):
    class Meta:
        model = School
        fields = ['name']
        widgets = {'name': forms.TextInput(attrs={'class': 'form-control'})}

# --- ФОРМА КЛАССА ---
# (Өзгеріссіз қалды)
class ClassForm(forms.ModelForm):
    subjects = forms.ModelMultipleChoiceField(
        queryset=Subject.objects.all(),
        widget=forms.CheckboxSelectMultiple(attrs={'class': 'form-check-input'}),
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
        school = kwargs.pop('school', None)
        super().__init__(*args, **kwargs)
        current_school = school
        if not current_school and self.instance and self.instance.pk:
            current_school = self.instance.school
        if current_school:
            self.fields['school'].queryset = School.objects.filter(pk=current_school.pk)
            self.fields['school'].initial = current_school
            self.fields['school'].disabled = True
            self.fields['teacher'].queryset = User.objects.filter(school=current_school, role__in=['teacher', 'director', 'admin']).order_by('last_name', 'first_name')
            self.fields['subjects'].queryset = Subject.objects.filter(school=current_school).order_by('name')
        else:
            self.fields['school'].queryset = School.objects.all().order_by('name')
            self.fields['teacher'].queryset = User.objects.filter(role__in=['teacher', 'director', 'admin']).select_related('school').order_by('school__name', 'last_name', 'first_name')
            self.fields['subjects'].queryset = Subject.objects.all().select_related('school').order_by('school__name', 'name')

# --- ФОРМА ПРЕДМЕТА ---
# (Өзгеріссіз қалды)
class SubjectForm(forms.ModelForm):
    class Meta:
        model = Subject
        fields = ['name', 'school']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'school': forms.Select(attrs={'class': 'form-select'}),
        }

    def __init__(self, *args, **kwargs):
        school = kwargs.pop('school', None)
        super().__init__(*args, **kwargs)
        current_school = school
        if not current_school and self.instance and self.instance.pk:
            current_school = self.instance.school
        if current_school:
            self.fields['school'].queryset = School.objects.filter(pk=current_school.pk)
            self.fields['school'].initial = current_school
            self.fields['school'].disabled = True
        else:
            self.fields['school'].queryset = School.objects.all().order_by('name')

# --- ФОРМА РАСПИСАНИЯ (УАҚЫТ ҚОСЫЛҒАН) ---
class ScheduleForm(forms.ModelForm):
    class Meta:
        model = Schedule
        # --- fields-ке time_start, time_end қосылды ---
        fields = ['date', 'lesson_number', 'time_start', 'time_end', 'school_class', 'subject', 'teacher', 'room', 'topic', 'task', 'status']
        widgets = {
            'date': DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'lesson_number': forms.Select(choices=Schedule.LESSON_NUMBER_CHOICES, attrs={'class': 'form-select'}),
            # --- Уақыт виджеттері ---
            'time_start': TimeInput(attrs={'type': 'time', 'class': 'form-control'}),
            'time_end': TimeInput(attrs={'type': 'time', 'class': 'form-control'}),
            # --- ---
            'school_class': forms.Select(attrs={'class': 'form-select'}),
            'subject': forms.Select(attrs={'class': 'form-select'}),
            'teacher': forms.Select(attrs={'class': 'form-select'}),
            'room': forms.TextInput(attrs={'class': 'form-control'}),
            'topic': forms.TextInput(attrs={'class': 'form-control'}),
            'task': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'status': forms.Select(attrs={'class': 'form-select'}),
        }

    # __init__ және clean методтары өзгеріссіз қалады (алдыңғы жауаптағыдай)
    def __init__(self, *args, **kwargs):
        school = kwargs.pop('school', None)
        user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        current_school = school
        if not current_school and self.instance and self.instance.pk and hasattr(self.instance.school_class, 'school'):
            current_school = self.instance.school_class.school
        if current_school:
            self.fields['school_class'].queryset = Class.objects.filter(school=current_school).order_by('name')
            self.fields['teacher'].queryset = User.objects.filter(school=current_school, role__in=['teacher', 'director', 'admin']).order_by('last_name', 'first_name')
            self.fields['subject'].queryset = Subject.objects.filter(school=current_school).order_by('name')
        else:
            self.fields['school_class'].queryset = Class.objects.all().select_related('school').order_by('school__name', 'name')
            self.fields['teacher'].queryset = User.objects.filter(role__in=['teacher', 'director', 'admin']).select_related('school').order_by('school__name', 'last_name', 'first_name')
            self.fields['subject'].queryset = Subject.objects.all().select_related('school').order_by('school__name', 'name')
        if user and getattr(user, 'role', None) == 'teacher':
             if 'teacher' in self.fields:
                 self.fields['teacher'].initial = user
                 self.fields['teacher'].disabled = True

    def clean(self):
        # Модельдің clean() методын шақыру маңызды, ол жерде негізгі валидациялар бар
        super().clean() # Бұл модельдегі ValidationError-ді көтереді
        cleaned_data = self.cleaned_data # Модельдің clean() методынан кейін тазартылған деректер

        # Форма деңгейінде қосымша, тек интерфейске қатысты тексерулер қосуға болады,
        # бірақ дерекқор логикасын (unique_together, time_end > time_start) модельде қалдырған дұрыс.
        # Мысалы:
        # time_start = cleaned_data.get("time_start")
        # time_end = cleaned_data.get("time_end")
        # if time_start and not time_end:
        #    self.add_error('time_end', _("Басталу уақыты көрсетілсе, аяқталу уақыты да міндетті."))

        return cleaned_data # Тазартылған деректерді қайтару керек

# --- ФОРМА ДНЕВНЫХ ОЦЕНОК ---
# (Өзгеріссіз қалды)
class DailyGradeForm(forms.ModelForm):
    class Meta:
        model = DailyGrade
        fields = ['student', 'teacher', 'subject', 'date', 'term', 'grade', 'comment']
        widgets = {
            'student': forms.Select(attrs={'class': 'form-select'}),
            'teacher': forms.HiddenInput(),
            'subject': forms.Select(attrs={'class': 'form-select'}),
            'date': DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'term': forms.NumberInput(attrs={'class': 'form-control', 'min': '1', 'max': '4'}),
            'grade': forms.NumberInput(attrs={'class': 'form-control', 'min': '1', 'max': '5'}),
            'comment': forms.TextInput(attrs={'class': 'form-control'}),
        }

    def __init__(self, *args, **kwargs):
        school = kwargs.pop('school', None)
        user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        if school:
            self.fields['student'].queryset = User.objects.none()
            self.fields['subject'].queryset = Subject.objects.filter(school=school).order_by('name')
        else:
             self.fields['student'].queryset = User.objects.none()
             self.fields['subject'].queryset = Subject.objects.none()
        if user:
             self.fields['teacher'].initial = user

# --- ФОРМА ЭКЗАМЕНАЦИОННЫХ ОЦЕНОК ---
# (Өзгеріссіз қалды)
class ExamGradeForm(forms.ModelForm):
    class Meta:
        model = ExamGrade
        fields = ['student', 'teacher', 'subject', 'date', 'term', 'exam_type', 'grade', 'max_grade', 'comment']
        widgets = {
            'student': forms.Select(attrs={'class': 'form-select'}),
            'teacher': forms.HiddenInput(),
            'subject': forms.Select(attrs={'class': 'form-select'}),
            'date': DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'term': forms.NumberInput(attrs={'class': 'form-control', 'min': '1', 'max': '4'}),
            'exam_type': forms.Select(attrs={'class': 'form-select'}),
            'grade': forms.NumberInput(attrs={'class': 'form-control', 'min':'0'}),
            'max_grade': forms.NumberInput(attrs={'class': 'form-control', 'min':'1'}),
            'comment': forms.TextInput(attrs={'class': 'form-control'}),
        }

    def __init__(self, *args, **kwargs):
        school = kwargs.pop('school', None)
        user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        if school:
             self.fields['student'].queryset = User.objects.none()
             self.fields['subject'].queryset = Subject.objects.filter(school=school).order_by('name')
        else:
             self.fields['student'].queryset = User.objects.none()
             self.fields['subject'].queryset = Subject.objects.none()
        if user:
             self.fields['teacher'].initial = user

# --- ФОРМЫ РЕДАКТИРОВАНИЯ ПРОФИЛЯ ---
# (Өзгеріссіз қалды)
class UserEditForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ('first_name', 'last_name', 'email', 'iin')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['first_name'].widget.attrs.update({'class': 'form-control mb-3'})
        self.fields['last_name'].widget.attrs.update({'class': 'form-control mb-3'})
        self.fields['email'].widget.attrs.update({'class': 'form-control mb-3'})
        self.fields['email'].required = True
        self.fields['iin'].widget.attrs.update({'class': 'form-control mb-3'})
        self.fields['iin'].required = False

class UserProfileEditForm(forms.ModelForm):
    date_of_birth = forms.DateField(
        widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
        required=False, label="Туған күні"
    )
    avatar = forms.ImageField(
        widget=forms.ClearableFileInput(attrs={'class': 'form-control'}),
        required=False, label="Профиль суреті (жаңа)"
    )
    school_class = forms.ModelChoiceField(
        queryset=Class.objects.none(),
        required=False, widget=forms.Select(attrs={'class': 'form-select'}), label="Сыныбы"
    )

    class Meta:
        model = UserProfile
        fields = ('patronymic', 'date_of_birth', 'gender', 'school_class', 'avatar')

    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        self.fields['patronymic'].widget.attrs.update({'class': 'form-control mb-3'})
        self.fields['patronymic'].required = False
        self.fields['gender'].widget.attrs.update({'class': 'form-select mb-3'})
        self.fields['gender'].required = False
        if user and getattr(user, 'role', None) == 'student':
            self.fields['school_class'].widget.attrs.update({'class': 'form-select mb-3'})
            self.fields['school_class'].required = False
            user_school = getattr(user, 'school', None)
            if user_school:
                self.fields['school_class'].queryset = Class.objects.filter(school=user_school).order_by('name')
            else:
                self.fields['school_class'].queryset = Class.objects.none()
        elif 'school_class' in self.fields:
            del self.fields['school_class']

# --- ФОРМА АУТЕНТИФИКАЦИИ ---
# (Өзгеріссіз қалды)
class CustomAuthenticationForm(AuthenticationForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['username'].widget = forms.TextInput(attrs={
            'class': 'form-control mb-3', 'placeholder': 'Логин', 'autofocus': True
        })
        self.fields['password'].widget = forms.PasswordInput(attrs={
            'class': 'form-control mb-3', 'placeholder': 'Құпия сөз'
        })