from django import forms
from django.contrib.auth.forms import UserCreationForm
from .models import User, School, Schedule, DailyGrade, ExamGrade, Class, Subject
from django.forms.widgets import DateInput, TimeInput

class UserRegistrationForm(UserCreationForm):
    role = forms.ChoiceField(choices=User.ROLE_CHOICES)
    school = forms.ModelChoiceField(queryset=School.objects.all(), required=False)
    first_name = forms.CharField(max_length=150)
    last_name = forms.CharField(max_length=150)
    parent_of = forms.ModelChoiceField(queryset=User.objects.filter(role='student'), required=False, label="Ученик (для родителя)")

    class Meta(UserCreationForm.Meta):  # Исправлено
        model = User
        fields = UserCreationForm.Meta.fields + ('role', 'school', 'first_name', 'last_name', 'surname' , 'parent_of')

class SchoolForm(forms.ModelForm):
    class Meta:
        model = School
        fields = ['name']

class ClassForm(forms.ModelForm):
    class Meta:
        model = Class
        fields = ['name', 'school', 'teacher']

class SubjectForm(forms.ModelForm):
    class Meta:
        model = Subject
        fields = ['name', 'school']

class ScheduleForm(forms.ModelForm):
    class Meta:
        model = Schedule
        fields = ['teacher', 'student', 'subject', 'date', 'time', 'task', 'status', 'lesson_number', 'school_class']
        widgets = {
            'date': DateInput(attrs={'type': 'date'}),
            'time': TimeInput(attrs={'type': 'time'}),
        }

class DailyGradeForm(forms.ModelForm):
    class Meta:
        model = DailyGrade
        fields = ['student', 'teacher', 'subject', 'date', 'grade']
        widgets = {
            'date': DateInput(attrs={'type': 'date'}),
        }

class ExamGradeForm(forms.ModelForm):
    class Meta:
        model = ExamGrade
        fields = ['student', 'teacher', 'subject', 'date', 'grade', 'max_grade']
        widgets = {
            'date': DateInput(attrs={'type': 'date'}),
        }