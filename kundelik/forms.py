# kundelik/forms.py

from django import forms
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm
from django.contrib.auth import get_user_model
from .models import (UserProfile, School, Schedule, DailyGrade, ExamGrade, Class, Subject,
                    Assessment, Question, Choice, Submission, Answer)
from django.forms.widgets import (DateInput, TimeInput, Textarea, NumberInput, Select,
                                 TextInput, CheckboxSelectMultiple, ClearableFileInput,
                                 EmailInput, HiddenInput, PasswordInput, RadioSelect,
                                 CheckboxInput, SelectMultiple, FileInput)
from django.forms import inlineformset_factory, BaseInlineFormSet
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import transaction
from django.utils import timezone # timezone импортын қосу керек (GradeSubmissionForm ішінде)
import logging

logger = logging.getLogger(__name__)

User = get_user_model()

# --- UserRegistrationForm ---
class UserRegistrationForm(UserCreationForm):
    role = forms.ChoiceField(choices=User.ROLE_CHOICES, label="Рөл", widget=Select(attrs={'class': 'form-select mb-3'}))
    school = forms.ModelChoiceField(queryset=School.objects.all().order_by('name'), required=False, label="Мектеп", widget=Select(attrs={'class': 'form-select mb-3'}))
    first_name = forms.CharField(max_length=150, label="Аты", widget=TextInput(attrs={'class': 'form-control mb-3'}))
    last_name = forms.CharField(max_length=150, label="Тегі", widget=TextInput(attrs={'class': 'form-control mb-3'}))
    parent_of = forms.ModelChoiceField(queryset=User.objects.filter(role='student').order_by('last_name', 'first_name'), required=False, label="Оқушы (ата-ана үшін)", widget=Select(attrs={'class': 'form-select mb-3'}))
    email = forms.EmailField(required=True, label="Электрондық пошта", widget=EmailInput(attrs={'class': 'form-control mb-3'}))
    iin = forms.CharField(required=False, label="ЖСН", max_length=12, widget=TextInput(attrs={'class': 'form-control mb-3'}))
    class Meta(UserCreationForm.Meta): model = User; fields = UserCreationForm.Meta.fields + ('email', 'role', 'school', 'first_name', 'last_name', 'parent_of', 'iin')
    def __init__(self, *args, **kwargs):
        self.requesting_user = kwargs.pop('user', None); super().__init__(*args, **kwargs)
        if self.requesting_user and not self.requesting_user.is_superuser and getattr(self.requesting_user, 'role', None) in ['admin', 'director']:
            user_school = getattr(self.requesting_user, 'school', None)
            if user_school: self.fields['school'].queryset = School.objects.filter(pk=user_school.pk); self.fields['school'].initial = user_school; self.fields['school'].disabled = True; self.fields['parent_of'].queryset = User.objects.filter(role='student', school=user_school).order_by('last_name', 'first_name')
            else: self.fields['school'].queryset = School.objects.none(); self.fields['parent_of'].queryset = User.objects.none()

# --- SchoolForm ---
class SchoolForm(forms.ModelForm):
    class Meta: model = School; fields = ['name']; widgets = {'name': TextInput(attrs={'class': 'form-control'})}

# --- ClassForm ---
class ClassForm(forms.ModelForm):
    subjects = forms.ModelMultipleChoiceField(queryset=Subject.objects.all(), widget=CheckboxSelectMultiple(attrs={'class': 'form-check-input'}), required=False, label="Осы сыныптың пәндері")
    class Meta: model = Class; fields = ['name', 'school', 'teacher', 'subjects']; widgets = {'name': TextInput(attrs={'class': 'form-control'}),'school': Select(attrs={'class': 'form-select'}),'teacher': Select(attrs={'class': 'form-select'}),}
    def __init__(self, *args, **kwargs):
        school = kwargs.pop('school', None); super().__init__(*args, **kwargs); current_school = school
        if not current_school and self.instance and self.instance.pk: current_school = self.instance.school
        if current_school: self.fields['school'].queryset = School.objects.filter(pk=current_school.pk); self.fields['school'].initial = current_school; self.fields['school'].disabled = True; self.fields['teacher'].queryset = User.objects.filter(school=current_school, role__in=['teacher', 'director', 'admin']).order_by('last_name', 'first_name'); self.fields['subjects'].queryset = Subject.objects.filter(school=current_school).order_by('name')
        else: self.fields['school'].queryset = School.objects.all().order_by('name'); self.fields['teacher'].queryset = User.objects.filter(role__in=['teacher', 'director', 'admin']).select_related('school').order_by('school__name', 'last_name', 'first_name'); self.fields['subjects'].queryset = Subject.objects.all().select_related('school').order_by('school__name', 'name')

# --- SubjectForm ---
class SubjectForm(forms.ModelForm):
    class Meta: model = Subject; fields = ['name', 'school']; widgets = {'name': TextInput(attrs={'class': 'form-control'}),'school': Select(attrs={'class': 'form-select'}),}
    def __init__(self, *args, **kwargs):
        school = kwargs.pop('school', None); super().__init__(*args, **kwargs); current_school = school
        if not current_school and self.instance and self.instance.pk: current_school = self.instance.school
        if current_school: self.fields['school'].queryset = School.objects.filter(pk=current_school.pk); self.fields['school'].initial = current_school; self.fields['school'].disabled = True
        else: self.fields['school'].queryset = School.objects.all().order_by('name')

# --- ScheduleForm ---
class ScheduleForm(forms.ModelForm):
    class Meta: model = Schedule; fields = ['date', 'lesson_number', 'time_start', 'time_end', 'school_class', 'subject', 'teacher', 'room', 'topic', 'task', 'status']; widgets = {'date': DateInput(attrs={'type': 'date', 'class': 'form-control'}),'lesson_number': Select(choices=Schedule.LESSON_NUMBER_CHOICES, attrs={'class': 'form-select'}),'time_start': TimeInput(attrs={'type': 'time', 'class': 'form-control'}),'time_end': TimeInput(attrs={'type': 'time', 'class': 'form-control'}),'school_class': Select(attrs={'class': 'form-select'}),'subject': Select(attrs={'class': 'form-select'}),'teacher': Select(attrs={'class': 'form-select'}),'room': TextInput(attrs={'class': 'form-control'}),'topic': TextInput(attrs={'class': 'form-control'}),'task': Textarea(attrs={'class': 'form-control', 'rows': 3}),'status': Select(attrs={'class': 'form-select'}),}
    def __init__(self, *args, **kwargs):
        school = kwargs.pop('school', None); user = kwargs.pop('user', None); super().__init__(*args, **kwargs); current_school = school
        if not current_school and self.instance and self.instance.pk and hasattr(self.instance.school_class, 'school'): current_school = self.instance.school_class.school
        if current_school: self.fields['school_class'].queryset = Class.objects.filter(school=current_school).order_by('name'); self.fields['teacher'].queryset = User.objects.filter(school=current_school, role__in=['teacher', 'director', 'admin']).order_by('last_name', 'first_name'); self.fields['subject'].queryset = Subject.objects.filter(school=current_school).order_by('name')
        else: self.fields['school_class'].queryset = Class.objects.all().select_related('school').order_by('school__name', 'name'); self.fields['teacher'].queryset = User.objects.filter(role__in=['teacher', 'director', 'admin']).select_related('school').order_by('school__name', 'last_name', 'first_name'); self.fields['subject'].queryset = Subject.objects.all().select_related('school').order_by('school__name', 'name')
        if user and getattr(user, 'role', None) == 'teacher':
             if 'teacher' in self.fields: self.fields['teacher'].initial = user; self.fields['teacher'].disabled = True


# --- ★★★ DailyGradeForm (ПОСЛЕДНЯЯ ВЕРСИЯ) ★★★ ---
class DailyGradeForm(forms.ModelForm):
    class Meta:
        model = DailyGrade
        fields = ['student', 'subject', 'date', 'grade', 'comment'] # term удален
        widgets = {
            'student': Select(attrs={'class': 'form-select form-select-sm'}),
            'subject': Select(attrs={'class': 'form-select form-select-sm'}),
            'date': DateInput(attrs={'type': 'date', 'class': 'form-control form-control-sm'}),
            'grade': NumberInput(attrs={'class': 'form-control form-control-sm', 'min': '1', 'max': '5'}),
            'comment': TextInput(attrs={'class': 'form-control form-control-sm'}),
        }
        labels = {
            'student': _('Оқушы'),
            'subject': _('Пән'),
            'date': _('Күні'),
            'grade': _('Баға'),
            'comment': _('Комментарий'),
        }

    def __init__(self, *args, **kwargs):
        students_queryset = kwargs.pop('students_queryset', None)
        school = kwargs.pop('school', None)
        user = kwargs.pop('user', None)
        kwargs.pop('teacher', None)
        super().__init__(*args, **kwargs)

        if user:
            self.fields['teacher'] = forms.ModelChoiceField(
                queryset=User.objects.filter(pk=user.pk), initial=user,
                widget=HiddenInput(), disabled=True, required=False
            )
            if not self.instance.pk: self.instance.teacher = user
        else:
            logger.warning("DailyGradeForm инициализирована без user (teacher).")
            current_teacher = getattr(self.instance, 'teacher', None)
            self.fields['teacher'] = forms.ModelChoiceField(
                queryset=User.objects.filter(pk=current_teacher.pk) if current_teacher else User.objects.none(),
                initial=current_teacher, widget=HiddenInput(), disabled=True, required=False
            )

        effective_school = school
        if not effective_school and self.instance and self.instance.pk and self.instance.subject:
            effective_school = self.instance.subject.school

        if effective_school:
            self.fields['subject'].queryset = Subject.objects.filter(school=effective_school).order_by('name')
        else:
            logger.warning("[DailyGradeForm Init] School not determined for subject filtering.")
            self.fields['subject'].queryset = Subject.objects.none()

        if students_queryset is not None:
            self.fields['student'].queryset = students_queryset
        else:
            if self.instance and self.instance.pk:
                self.fields['student'].queryset = User.objects.filter(pk=self.instance.student_id)
            else:
                logger.warning("[DailyGradeForm Init] students_queryset is None for a new instance.")
                self.fields['student'].queryset = User.objects.none()

    def save(self, commit=True):
        if not self.instance.teacher and 'teacher' in self.fields and self.fields['teacher'].initial:
             self.instance.teacher = self.fields['teacher'].initial
        elif not self.instance.teacher and not self.instance.pk:
             logger.error("ПОПЫТКА СОХРАНИТЬ НОВУЮ DailyGrade БЕЗ УЧИТЕЛЯ!")
             # raise ValidationError("Не удалось определить учителя для новой оценки.")
        # Определение Term перенесено в view
        return super().save(commit=commit)


# --- ★★★ ExamGradeForm (ПОСЛЕДНЯЯ ВЕРСИЯ) ★★★ ---
class ExamGradeForm(forms.ModelForm):
    class Meta:
        model = ExamGrade
        fields = ['student', 'subject', 'date', 'term', 'exam_type', 'grade', 'max_grade', 'comment'] # teacher удален
        widgets = {
            'student': Select(attrs={'class': 'form-select form-select-sm'}),
            'subject': Select(attrs={'class': 'form-select form-select-sm'}),
            'date': DateInput(attrs={'type': 'date', 'class': 'form-control form-control-sm'}),
            'term': NumberInput(attrs={'class': 'form-control form-control-sm', 'min': '1', 'max': '4'}),
            'exam_type': Select(attrs={'class': 'form-select form-select-sm'}),
            'grade': NumberInput(attrs={'class': 'form-control form-control-sm', 'min':'0'}),
            'max_grade': NumberInput(attrs={'class': 'form-control form-control-sm', 'min':'1'}),
            'comment': TextInput(attrs={'class': 'form-control form-control-sm'}),
        }
        labels = {
            'student': _('Оқушы'),
            'subject': _('Пән'),
            'date': _('Күні'),
            'term': _('Тоқсан'),
            'exam_type': _('Жұмыс түрі'),
            'grade': _('Алынған балл'),
            'max_grade': _('Макс. балл'),
            'comment': _('Комментарий'),
        }

    def __init__(self, *args, **kwargs):
        students_queryset = kwargs.pop('students_queryset', None)
        school = kwargs.pop('school', None)
        user = kwargs.pop('user', None)
        kwargs.pop('teacher', None)
        super().__init__(*args, **kwargs)

        if user:
            self.fields['teacher'] = forms.ModelChoiceField(
                queryset=User.objects.filter(pk=user.pk), initial=user,
                widget=HiddenInput(), disabled=True, required=False
            )
            if not self.instance.pk: self.instance.teacher = user
        else:
            logger.warning("ExamGradeForm инициализирована без user (teacher).")
            current_teacher = getattr(self.instance, 'teacher', None)
            self.fields['teacher'] = forms.ModelChoiceField(
                queryset=User.objects.filter(pk=current_teacher.pk) if current_teacher else User.objects.none(),
                initial=current_teacher, widget=HiddenInput(), disabled=True, required=False
            )

        effective_school = school
        if not effective_school and self.instance and self.instance.pk and self.instance.subject:
            effective_school = self.instance.subject.school

        if effective_school:
            self.fields['subject'].queryset = Subject.objects.filter(school=effective_school).order_by('name')
        else:
            logger.warning("[ExamGradeForm Init] School not determined for subject filtering.")
            self.fields['subject'].queryset = Subject.objects.none()

        if students_queryset is not None:
            self.fields['student'].queryset = students_queryset
        else:
            if self.instance and self.instance.pk:
                self.fields['student'].queryset = User.objects.filter(pk=self.instance.student_id)
            else:
                logger.warning("[ExamGradeForm Init] students_queryset is None for a new instance.")
                self.fields['student'].queryset = User.objects.none()

    def save(self, commit=True):
        if not self.instance.teacher and 'teacher' in self.fields and self.fields['teacher'].initial:
             self.instance.teacher = self.fields['teacher'].initial
        elif not self.instance.teacher and not self.instance.pk:
             logger.error("ПОПЫТКА СОХРАНИТЬ НОВУЮ ExamGrade БЕЗ УЧИТЕЛЯ!")
             # raise ValidationError("Не удалось определить учителя для новой оценки.")
        return super().save(commit=commit)

    def clean(self):
        cleaned_data = super().clean()
        grade = cleaned_data.get("grade")
        max_grade = cleaned_data.get("max_grade")
        if grade is not None and max_grade is not None:
            try:
                num_grade = float(grade); num_max_grade = float(max_grade)
                if num_grade > num_max_grade:
                    raise ValidationError(
                        _("Алынған балл (%(grade)s) максималды баллдан (%(max_grade)s) жоғары бола алмайды."),
                        code='grade_exceeds_max', params={'grade': grade, 'max_grade': max_grade},
                    )
            except (ValueError, TypeError): raise ValidationError(_("Балл сандық мән болуы керек."))
        elif grade is not None and grade < 0: raise ValidationError(_("Алынған балл теріс бола алмайды."))
        elif max_grade is not None and max_grade <= 0: raise ValidationError(_("Максималды балл оң сан болуы керек."))
        return cleaned_data

# --- UserEditForm ---
class UserEditForm(forms.ModelForm):
    class Meta: model = User; fields = ('first_name', 'last_name', 'email', 'iin')
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs); self.fields['first_name'].widget.attrs.update({'class': 'form-control mb-3'}); self.fields['last_name'].widget.attrs.update({'class': 'form-control mb-3'}); self.fields['email'].widget.attrs.update({'class': 'form-control mb-3'}); self.fields['email'].required = True; self.fields['iin'].widget.attrs.update({'class': 'form-control mb-3'}); self.fields['iin'].required = False

# --- UserProfileEditForm ---
class UserProfileEditForm(forms.ModelForm):
    date_of_birth = forms.DateField(widget=DateInput(attrs={'type': 'date', 'class': 'form-control'}), required=False, label="Туған күні")
    avatar = forms.ImageField(widget=ClearableFileInput(attrs={'class': 'form-control'}), required=False, label="Профиль суреті (жаңа)")
    school_class = forms.ModelChoiceField(queryset=Class.objects.none(), required=False, widget=Select(attrs={'class': 'form-select'}), label="Сыныбы")
    class Meta: model = UserProfile; fields = ('patronymic', 'date_of_birth', 'gender', 'school_class', 'avatar')
    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None); super().__init__(*args, **kwargs)
        self.fields['patronymic'].widget.attrs.update({'class': 'form-control mb-3'}); self.fields['patronymic'].required = False
        self.fields['gender'].widget.attrs.update({'class': 'form-select mb-3'}); self.fields['gender'].required = False
        if user and getattr(user, 'role', None) == 'student':
            self.fields['school_class'].widget.attrs.update({'class': 'form-select mb-3'}); self.fields['school_class'].required = False
            user_school = getattr(user, 'school', None)
            if user_school: self.fields['school_class'].queryset = Class.objects.filter(school=user_school).order_by('name')
            else: self.fields['school_class'].queryset = Class.objects.none()
            if self.instance and self.instance.pk and self.instance.school_class: self.fields['school_class'].initial = self.instance.school_class
        elif 'school_class' in self.fields: del self.fields['school_class']

# --- CustomAuthenticationForm ---
class CustomAuthenticationForm(AuthenticationForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs); self.fields['username'].widget = TextInput(attrs={'class': 'form-control mb-3', 'placeholder': 'Логин', 'autofocus': True}); self.fields['password'].widget = PasswordInput(attrs={'class': 'form-control mb-3', 'placeholder': 'Құпия сөз'})

# ==================================================
# --- ASSESSMENT FORMS ---
# ==================================================

class AssessmentForm(forms.ModelForm):
    class Meta: model = Assessment; fields = ['title', 'subject', 'school_class', 'term', 'exam_type', 'due_date', 'is_active', 'instructions']; widgets = { 'title': TextInput(attrs={'class': 'form-control'}), 'subject': Select(attrs={'class': 'form-select'}), 'school_class': Select(attrs={'class': 'form-select'}), 'term': NumberInput(attrs={'class': 'form-control', 'min': '1', 'max': '4'}), 'exam_type': Select(attrs={'class': 'form-select'}), 'due_date': forms.DateTimeInput(attrs={'type': 'datetime-local', 'class': 'form-control'}), 'is_active': CheckboxInput(attrs={'class': 'form-check-input'}), 'instructions': Textarea(attrs={'class': 'form-control', 'rows': 4}), }; labels = {'is_active': _("Белсенді (Оқушыларға көрсету)")}
    def __init__(self, *args, **kwargs):
        school = kwargs.pop('school', None); user = kwargs.pop('user', None); super().__init__(*args, **kwargs); current_school = school
        if not current_school and self.instance and self.instance.pk:
             if hasattr(self.instance, 'subject') and self.instance.subject: current_school = self.instance.subject.school
             elif hasattr(self.instance, 'school_class') and self.instance.school_class: current_school = self.instance.school_class.school
        if current_school: self.fields['subject'].queryset = Subject.objects.filter(school=current_school).order_by('name'); self.fields['school_class'].queryset = Class.objects.filter(school=current_school).order_by('name')
        elif user and user.is_superuser: self.fields['subject'].queryset = Subject.objects.all().select_related('school').order_by('school__name', 'name'); self.fields['school_class'].queryset = Class.objects.all().select_related('school').order_by('school__name', 'name')
        else: self.fields['subject'].queryset = Subject.objects.none(); self.fields['school_class'].queryset = Class.objects.none()

class QuestionForm(forms.ModelForm):
    class Meta: model = Question; fields = ['text', 'question_type', 'points', 'order']; widgets = { 'question_type': Select(attrs={'class': 'form-select form-select-sm question-type'}), 'points': NumberInput(attrs={'class': 'form-control form-control-sm question-points', 'min': '0'}), 'order': NumberInput(attrs={'class': 'form-control form-control-sm question-order'}), }; labels = { 'text': _("Сұрақ мәтіні (сурет қоюға болады)"), 'question_type': _("Түрі"), 'points': _("Балл"), 'order': _("Рет"), }

class BaseQuestionFormSet(BaseInlineFormSet):
    def clean(self):
        super().clean(); question_orders = []
        for form in self.forms:
            if not form.is_valid(): continue
            if form.cleaned_data.get('DELETE', False): continue
            if not form.has_changed() and not form.instance.pk: continue
            order = form.cleaned_data.get('order')
            if order is not None:
                if order in question_orders: form.add_error('order', forms.ValidationError(_("Сұрақтың реттік нөмірі қайталанбауы керек.")))
                else: question_orders.append(order)
            else:
                 if not form.cleaned_data.get('DELETE', False): form.add_error('order', forms.ValidationError(_("Сұрақтың реттік нөмірін көрсетіңіз.")))

class ChoiceForm(forms.ModelForm):
     class Meta: model = Choice; fields = ['text', 'is_correct']; widgets = {'text': TextInput(attrs={'class': 'form-control form-control-sm'}), 'is_correct': CheckboxInput(attrs={'class': 'form-check-input'}),}; labels = {'text': _("Нұсқа"), 'is_correct': _("Дұрыс")}

ChoiceFormSet = inlineformset_factory(Question, Choice, form=ChoiceForm, fields=('text', 'is_correct'), extra=1, can_delete=True, can_order=False)

class SubmissionForm(forms.ModelForm):
    class Meta: model = Submission; fields = []
    def __init__(self, *args, **kwargs):
        self.assessment = kwargs.pop('assessment'); self.student = kwargs.pop('student'); super().__init__(*args, **kwargs)
        if not self.assessment: logger.error("SubmissionForm initialized without an assessment."); return
        for question in self.assessment.questions.order_by('order'):
            field_name_base = f'question_{question.pk}'; choices_list = []
            if question.question_type in ['MCQ', 'TF', 'MAQ']:
                try: choices_queryset = question.choices.all().order_by('pk'); choices_list = [(choice.pk, choice.text) for choice in choices_queryset]
                except Exception as e: logger.error(f"Error getting choices for Question PK {question.pk}: {e}"); choices_list = []
            field_label = ""
            if question.question_type in ['MCQ', 'TF']: self.fields[f'{field_name_base}_choice'] = forms.ChoiceField(label=field_label, required=True, choices=[('', '---------')] + choices_list, widget=RadioSelect(attrs={'class': 'form-check-input'}))
            elif question.question_type == 'MAQ': self.fields[f'{field_name_base}_choices'] = forms.MultipleChoiceField(label=field_label, required=True, choices=choices_list, widget=CheckboxSelectMultiple(attrs={'class': 'form-check-input'}))
            elif question.question_type == 'OPEN':
                self.fields[f'{field_name_base}_text'] = forms.CharField(label=field_label, required=False, widget=Textarea(attrs={'class': 'form-control', 'rows': 4}))
                self.fields[f'{field_name_base}_file'] = forms.FileField(label="", required=False, widget=ClearableFileInput(attrs={'class': 'form-control form-control-sm mt-2'}), help_text=_("Немесе файл тіркеңіз (сурет, видео, құжат)."))
            if question.points:
                 help_text = _("(%s балл)") % question.points; field_key_to_update = None
                 if question.question_type in ['MCQ', 'TF']: field_key_to_update = f'{field_name_base}_choice'
                 elif question.question_type == 'MAQ': field_key_to_update = f'{field_name_base}_choices'
                 elif question.question_type == 'OPEN': field_key_to_update = f'{field_name_base}_text'
                 if field_key_to_update and field_key_to_update in self.fields:
                     existing_help = getattr(self.fields[field_key_to_update], 'help_text', ''); self.fields[field_key_to_update].help_text = f"{existing_help} {help_text}".strip()
    def clean(self):
        cleaned_data = super().clean()
        if not self.assessment: raise ValidationError(_("Бағалау табылмады."))
        for question in self.assessment.questions.filter(question_type='OPEN'):
            text_field_name = f'question_{question.pk}_text'; file_field_name = f'question_{question.pk}_file'
            text_value = cleaned_data.get(text_field_name); file_value = cleaned_data.get(file_field_name)
            if text_value and file_value: self.add_error(text_field_name, _("Тек мәтіндік жауапты немесе файлды ғана жібере аласыз, екеуін бірге емес.")); self.add_error(file_field_name, '')
        return cleaned_data
    @transaction.atomic
    def save(self, commit=True):
        if not self.assessment or not self.student: logger.error("Cannot save submission without assessment or student."); raise ValueError("Assessment and Student are required to save a Submission.")
        submission, created = Submission.objects.get_or_create(assessment=self.assessment, student=self.student, defaults={'submitted_at': timezone.now()})
        if created and commit:
            for question in self.assessment.questions.all():
                answer = Answer(submission=submission, question=question); field_name_base = f'question_{question.pk}'; has_answer_data = False
                try:
                    if question.question_type in ['MCQ', 'TF']:
                        choice_pk = self.cleaned_data.get(f'{field_name_base}_choice')
                        if choice_pk:
                            try: answer.selected_choice = Choice.objects.get(pk=int(choice_pk)); has_answer_data = True
                            except (Choice.DoesNotExist, ValueError, TypeError) as e: logger.warning(f"Invalid or missing Choice PK '{choice_pk}' for question {question.pk} in submission {submission.pk}. Error: {e}")
                    elif question.question_type == 'MAQ':
                        selected_pks = self.cleaned_data.get(f'{field_name_base}_choices', []); valid_pks = []
                        if selected_pks:
                            for pk in selected_pks:
                                try: valid_pks.append(int(pk))
                                except (ValueError, TypeError): logger.warning(f"Invalid PK '{pk}' found in MAQ choices for question {question.pk} in submission {submission.pk}.")
                            if valid_pks: answer._selected_choice_pks = valid_pks; has_answer_data = True
                    elif question.question_type == 'OPEN':
                        text_data = self.cleaned_data.get(f'{field_name_base}_text'); file_data = self.cleaned_data.get(f'{field_name_base}_file')
                        if text_data: answer.text_answer = text_data; has_answer_data = True
                        if file_data: answer._temp_file = file_data; has_answer_data = True
                    if has_answer_data:
                        try:
                            temp_file = getattr(answer, '_temp_file', None)
                            if temp_file: answer.attached_file = None; answer.save(); answer.attached_file = temp_file; answer.save(update_fields=['attached_file'])
                            else: answer.save()
                            if question.question_type == 'MAQ' and hasattr(answer, '_selected_choice_pks'):
                                try: choices = Choice.objects.filter(pk__in=answer._selected_choice_pks); answer.selected_choices.set(choices)
                                except (ValueError, TypeError) as e_maq: logger.error(f"Error setting MAQ choices for answer {answer.pk} (Question {question.pk}, Submission {submission.pk}): {e_maq}")
                        except Exception as save_error: logger.error(f"Error saving answer for question {question.pk}, submission {submission.pk}: {save_error}")
                except Exception as processing_error: logger.error(f"Error processing answer data for question {question.pk}, submission {submission.pk}: {processing_error}")
            try:
                final_score = submission.calculate_score(); submission.score = final_score if final_score is not None else 0
                if not self.assessment.questions.filter(question_type='OPEN').exists(): submission.is_graded = True; submission.graded_at = timezone.now()
                submission.save()
            except Exception as score_error: logger.error(f"Error calculating/saving score for submission {submission.pk}: {score_error}")
            return submission
        elif not created: logger.warning(f"Submission already exists for student {self.student.pk} and assessment {self.assessment.pk}. Returning existing submission {submission.pk}."); return submission
        return submission

class GradeSubmissionForm(forms.ModelForm):
    class Meta: model = Submission; fields = ['score']; widgets = {'score': NumberInput(attrs={'class': 'form-control', 'step': '1'})}
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs); max_score = None
        if self.instance and self.instance.pk and hasattr(self.instance, 'assessment') and self.instance.assessment:
             max_score = self.instance.assessment.max_score
             if max_score is not None: self.fields['score'].widget.attrs['max'] = max_score; self.fields['score'].widget.attrs['placeholder'] = _(f"Макс: {max_score}"); self.fields['score'].validators.append(MaxValueValidator(max_score))
             else: logger.warning(f"Assessment {self.instance.assessment.pk} has no max_score defined."); self.fields['score'].widget.attrs['placeholder'] = _(f"Балл енгізіңіз")
             self.fields['score'].validators.append(MinValueValidator(0))
             if not self.instance.is_graded:
                 try:
                     auto_score = self.instance.calculate_score()
                     if auto_score is not None: self.initial['score'] = min(auto_score, max_score) if max_score is not None else auto_score
                 except Exception as e: logger.error(f"Error calculating auto score for submission {self.instance.pk}: {e}")
        else: self.fields['score'].disabled = True; self.fields['score'].widget.attrs['placeholder'] = _("Бағалау мүмкін емес")
    def clean_score(self):
        score = self.cleaned_data.get('score')
        if score is None: raise ValidationError(_("Баллды енгізу қажет."))
        max_score = None
        if self.instance and hasattr(self.instance, 'assessment') and self.instance.assessment: max_score = self.instance.assessment.max_score
        if max_score is not None:
             if score > max_score: raise ValidationError(_("Балл максималды баллдан жоғары бола алмайды (Макс: %(max_score)s)."), params={'max_score': max_score}, code='score_exceeds_max')
        if score < 0: raise ValidationError(_("Балл теріс бола алмайды."), code='score_negative')
        return score
    def save(self, commit=True):
         if self.instance and self.instance.pk: self.instance.is_graded = True; self.instance.graded_at = timezone.now()
         return super().save(commit=commit)