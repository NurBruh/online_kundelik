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

User = get_user_model()

# --- Бұрынғы формалар (Өзгеріссіз) ---
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

class SchoolForm(forms.ModelForm):
    class Meta: model = School; fields = ['name']; widgets = {'name': TextInput(attrs={'class': 'form-control'})}
class ClassForm(forms.ModelForm):
    subjects = forms.ModelMultipleChoiceField(queryset=Subject.objects.all(), widget=CheckboxSelectMultiple(attrs={'class': 'form-check-input'}), required=False, label="Осы сыныптың пәндері")
    class Meta: model = Class; fields = ['name', 'school', 'teacher', 'subjects']; widgets = {'name': TextInput(attrs={'class': 'form-control'}),'school': Select(attrs={'class': 'form-select'}),'teacher': Select(attrs={'class': 'form-select'}),}
    def __init__(self, *args, **kwargs):
        school = kwargs.pop('school', None); super().__init__(*args, **kwargs); current_school = school
        if not current_school and self.instance and self.instance.pk: current_school = self.instance.school
        if current_school: self.fields['school'].queryset = School.objects.filter(pk=current_school.pk); self.fields['school'].initial = current_school; self.fields['school'].disabled = True; self.fields['teacher'].queryset = User.objects.filter(school=current_school, role__in=['teacher', 'director', 'admin']).order_by('last_name', 'first_name'); self.fields['subjects'].queryset = Subject.objects.filter(school=current_school).order_by('name')
        else: self.fields['school'].queryset = School.objects.all().order_by('name'); self.fields['teacher'].queryset = User.objects.filter(role__in=['teacher', 'director', 'admin']).select_related('school').order_by('school__name', 'last_name', 'first_name'); self.fields['subjects'].queryset = Subject.objects.all().select_related('school').order_by('school__name', 'name')

class SubjectForm(forms.ModelForm):
    class Meta: model = Subject; fields = ['name', 'school']; widgets = {'name': TextInput(attrs={'class': 'form-control'}),'school': Select(attrs={'class': 'form-select'}),}
    def __init__(self, *args, **kwargs):
        school = kwargs.pop('school', None); super().__init__(*args, **kwargs); current_school = school
        if not current_school and self.instance and self.instance.pk: current_school = self.instance.school
        if current_school: self.fields['school'].queryset = School.objects.filter(pk=current_school.pk); self.fields['school'].initial = current_school; self.fields['school'].disabled = True
        else: self.fields['school'].queryset = School.objects.all().order_by('name')

class ScheduleForm(forms.ModelForm):
    class Meta: model = Schedule; fields = ['date', 'lesson_number', 'time_start', 'time_end', 'school_class', 'subject', 'teacher', 'room', 'topic', 'task', 'status']; widgets = {'date': DateInput(attrs={'type': 'date', 'class': 'form-control'}),'lesson_number': Select(choices=Schedule.LESSON_NUMBER_CHOICES, attrs={'class': 'form-select'}),'time_start': TimeInput(attrs={'type': 'time', 'class': 'form-control'}),'time_end': TimeInput(attrs={'type': 'time', 'class': 'form-control'}),'school_class': Select(attrs={'class': 'form-select'}),'subject': Select(attrs={'class': 'form-select'}),'teacher': Select(attrs={'class': 'form-select'}),'room': TextInput(attrs={'class': 'form-control'}),'topic': TextInput(attrs={'class': 'form-control'}),'task': Textarea(attrs={'class': 'form-control', 'rows': 3}),'status': Select(attrs={'class': 'form-select'}),}
    def __init__(self, *args, **kwargs):
        school = kwargs.pop('school', None); user = kwargs.pop('user', None); super().__init__(*args, **kwargs); current_school = school
        if not current_school and self.instance and self.instance.pk and hasattr(self.instance.school_class, 'school'): current_school = self.instance.school_class.school
        if current_school: self.fields['school_class'].queryset = Class.objects.filter(school=current_school).order_by('name'); self.fields['teacher'].queryset = User.objects.filter(school=current_school, role__in=['teacher', 'director', 'admin']).order_by('last_name', 'first_name'); self.fields['subject'].queryset = Subject.objects.filter(school=current_school).order_by('name')
        else: self.fields['school_class'].queryset = Class.objects.all().select_related('school').order_by('school__name', 'name'); self.fields['teacher'].queryset = User.objects.filter(role__in=['teacher', 'director', 'admin']).select_related('school').order_by('school__name', 'last_name', 'first_name'); self.fields['subject'].queryset = Subject.objects.all().select_related('school').order_by('school__name', 'name')
        if user and getattr(user, 'role', None) == 'teacher':
             if 'teacher' in self.fields: self.fields['teacher'].initial = user; self.fields['teacher'].disabled = True
    def clean(self): super().clean(); cleaned_data = self.cleaned_data; return cleaned_data

class DailyGradeForm(forms.ModelForm):
    class Meta: model = DailyGrade; fields = ['student', 'teacher', 'subject', 'date', 'term', 'grade', 'comment']; widgets = {'student': Select(attrs={'class': 'form-select'}),'teacher': HiddenInput(),'subject': Select(attrs={'class': 'form-select'}),'date': DateInput(attrs={'type': 'date', 'class': 'form-control'}),'term': NumberInput(attrs={'class': 'form-control', 'min': '1', 'max': '4'}),'grade': NumberInput(attrs={'class': 'form-control', 'min': '1', 'max': '5'}),'comment': TextInput(attrs={'class': 'form-control'}),}
    def __init__(self, *args, **kwargs):
        school = kwargs.pop('school', None); user = kwargs.pop('user', None); super().__init__(*args, **kwargs)
        if school: self.fields['student'].queryset = User.objects.none(); self.fields['subject'].queryset = Subject.objects.filter(school=school).order_by('name')
        else: self.fields['student'].queryset = User.objects.none(); self.fields['subject'].queryset = Subject.objects.none()
        if user: self.fields['teacher'].initial = user

class ExamGradeForm(forms.ModelForm):
    class Meta: model = ExamGrade; fields = ['student', 'teacher', 'subject', 'date', 'term', 'exam_type', 'grade', 'max_grade', 'comment']; widgets = {'student': Select(attrs={'class': 'form-select'}),'teacher': HiddenInput(),'subject': Select(attrs={'class': 'form-select'}),'date': DateInput(attrs={'type': 'date', 'class': 'form-control'}),'term': NumberInput(attrs={'class': 'form-control', 'min': '1', 'max': '4'}),'exam_type': Select(attrs={'class': 'form-select'}),'grade': NumberInput(attrs={'class': 'form-control', 'min':'0'}),'max_grade': NumberInput(attrs={'class': 'form-control', 'min':'1'}),'comment': TextInput(attrs={'class': 'form-control'}),}
    def __init__(self, *args, **kwargs):
        school = kwargs.pop('school', None); user = kwargs.pop('user', None); super().__init__(*args, **kwargs)
        if school: self.fields['student'].queryset = User.objects.none(); self.fields['subject'].queryset = Subject.objects.filter(school=school).order_by('name')
        else: self.fields['student'].queryset = User.objects.none(); self.fields['subject'].queryset = Subject.objects.none()
        if user: self.fields['teacher'].initial = user

class UserEditForm(forms.ModelForm):
    class Meta: model = User; fields = ('first_name', 'last_name', 'email', 'iin')
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs); self.fields['first_name'].widget.attrs.update({'class': 'form-control mb-3'}); self.fields['last_name'].widget.attrs.update({'class': 'form-control mb-3'}); self.fields['email'].widget.attrs.update({'class': 'form-control mb-3'}); self.fields['email'].required = True; self.fields['iin'].widget.attrs.update({'class': 'form-control mb-3'}); self.fields['iin'].required = False

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
        elif 'school_class' in self.fields: del self.fields['school_class']

class CustomAuthenticationForm(AuthenticationForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs); self.fields['username'].widget = TextInput(attrs={'class': 'form-control mb-3', 'placeholder': 'Логин', 'autofocus': True}); self.fields['password'].widget = PasswordInput(attrs={'class': 'form-control mb-3', 'placeholder': 'Құпия сөз'})


# ==================================================
# --- ЖАҢА ФОРМАЛАР: БЖБ/ТЖБ (ASSESSMENT) ---
# ==================================================

class AssessmentForm(forms.ModelForm):
    class Meta:
        model = Assessment
        fields = ['title', 'subject', 'school_class', 'term', 'exam_type', 'due_date', 'is_active', 'instructions']
        widgets = {
            'title': TextInput(attrs={'class': 'form-control'}),
            'subject': Select(attrs={'class': 'form-select'}),
            'school_class': Select(attrs={'class': 'form-select'}),
            'term': NumberInput(attrs={'class': 'form-control', 'min': '1', 'max': '4'}),
            'exam_type': Select(attrs={'class': 'form-select'}),
            'due_date': forms.DateTimeInput(attrs={'type': 'datetime-local', 'class': 'form-control'}),
            'is_active': CheckboxInput(attrs={'class': 'form-check-input'}),
            'instructions': Textarea(attrs={'class': 'form-control', 'rows': 4}),
        }
        labels = {'is_active': _("Белсенді (Оқушыларға көрсету)")}

    def __init__(self, *args, **kwargs):
        school = kwargs.pop('school', None); user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs); current_school = school
        if not current_school and self.instance and self.instance.pk and hasattr(self.instance, 'school_class') and self.instance.school_class: current_school = self.instance.school_class.school
        if current_school: self.fields['subject'].queryset = Subject.objects.filter(school=current_school).order_by('name'); self.fields['school_class'].queryset = Class.objects.filter(school=current_school).order_by('name')
        elif user and user.is_superuser: self.fields['subject'].queryset = Subject.objects.all().select_related('school').order_by('school__name', 'name'); self.fields['school_class'].queryset = Class.objects.all().select_related('school').order_by('school__name', 'name')
        else: self.fields['subject'].queryset = Subject.objects.none(); self.fields['school_class'].queryset = Class.objects.none()

class QuestionForm(forms.ModelForm):
    class Meta:
        model = Question
        fields = ['text', 'question_type', 'points', 'order']
        widgets = {
            # 'text' виджеті қажет емес, егер Question.text = RichTextUploadingField болса
            'question_type': Select(attrs={'class': 'form-select form-select-sm question-type'}),
            'points': NumberInput(attrs={'class': 'form-control form-control-sm question-points', 'min': '0'}),
            'order': NumberInput(attrs={'class': 'form-control form-control-sm question-order'}),
        }
        labels = { 'text': _("Сұрақ мәтіні (сурет қоюға болады)"), 'question_type': _("Түрі"), 'points': _("Балл"), 'order': _("Рет"), }

class BaseQuestionFormSet(BaseInlineFormSet):
    def clean(self):
        super().clean(); question_orders = []
        for form in self.forms:
            if not form.is_valid() or (not form.cleaned_data and not form.errors): continue
            if form.cleaned_data and not form.cleaned_data.get('DELETE', False):
                order = form.cleaned_data.get('order')
                if order is not None:
                    if order in question_orders: form.add_error('order', forms.ValidationError(_("Сұрақтың реттік нөмірі қайталанбауы керек.")))
                    question_orders.append(order)

class ChoiceForm(forms.ModelForm):
     class Meta:
        model = Choice; fields = ['text', 'is_correct']
        widgets = {'text': TextInput(attrs={'class': 'form-control form-control-sm'}), 'is_correct': CheckboxInput(attrs={'class': 'form-check-input'}),}
        labels = {'text': _("Нұсқа"), 'is_correct': _("Дұрыс")}

ChoiceFormSet = inlineformset_factory(Question, Choice, form=ChoiceForm, fields=('text', 'is_correct'), extra=1, can_delete=True, can_order=False)

# --- ★★★ SubmissionForm ӨЗГЕРТІЛДІ ★★★ ---
class SubmissionForm(forms.ModelForm):
    class Meta: model = Submission; fields = [] # Тапсырманы жіберу үшін тікелей өрістер жоқ

    def __init__(self, *args, **kwargs):
        self.assessment = kwargs.pop('assessment'); self.student = kwargs.pop('student')
        super().__init__(*args, **kwargs)

        # Бағалаудағы әр сұрақ үшін динамикалық өріс қосамыз
        for question in self.assessment.questions.order_by('order'):
            field_name_base = f'question_{question.pk}'

            # Сұрақтың таңдау нұсқаларын алу
            try:
                choices_queryset = question.choices.all()
                choices_list = [(choice.pk, choice.text) for choice in choices_queryset]
            except Exception as e:
                 print(f"ERROR getting choices for Question PK {question.pk}: {e}")
                 choices_list = [] # Қате болса, бос тізім

            # Сұрақ түріне байланысты өріс түрін анықтау
            if question.question_type in ['MCQ', 'TF']:
                self.fields[f'{field_name_base}_choice'] = forms.ChoiceField(
                    label="", # Label-ді шаблонда көрсеткен дұрыс
                    required=True,
                    choices=choices_list,
                    # ★★★ ВИДЖЕТКЕ КЛАСС ОСЫ ЖЕРДЕ ҚОСЫЛДЫ ★★★
                    widget=RadioSelect(attrs={'class': 'form-check-input'})
                )
            elif question.question_type == 'MAQ':
                self.fields[f'{field_name_base}_choices'] = forms.MultipleChoiceField(
                    label="", # Label-ді шаблонда көрсеткен дұрыс
                    required=True, # Немесе False, егер міндетті емес болса
                    choices=choices_list,
                    # ★★★ ВИДЖЕТКЕ КЛАСС ОСЫ ЖЕРДЕ ҚОСЫЛДЫ ★★★
                    widget=CheckboxSelectMultiple(attrs={'class': 'form-check-input'})
                )
            elif question.question_type == 'OPEN':
                # Ашық сұрақтар үшін текст және файл өрістері
                self.fields[f'{field_name_base}_text'] = forms.CharField(
                    label="", # Label-ді шаблонда көрсеткен дұрыс
                    required=False, # Мәтін де, файл да міндетті емес
                    widget=Textarea(attrs={'class': 'form-control', 'rows': 4})
                )
                self.fields[f'{field_name_base}_file'] = forms.FileField(
                    label="", # Label-ді шаблонда көрсеткен дұрыс
                    required=False,
                    widget=ClearableFileInput(attrs={'class': 'form-control form-control-sm mt-2'}), # Файл өрісіне стильдер
                    help_text=_("Немесе файл тіркеңіз (сурет, видео, құжат).") # Көмекші мәтін
                )

            # Балл туралы көмекші мәтінді қосу (бұрынғыдай)
            if question.points:
                 field_key = None
                 if question.question_type in ['MCQ', 'TF']: field_key = f'{field_name_base}_choice'
                 elif question.question_type == 'MAQ': field_key = f'{field_name_base}_choices'
                 elif question.question_type == 'OPEN': field_key = f'{field_name_base}_text' # Мәтіндік өріске қоямыз
                 if field_key and field_key in self.fields: self.fields[field_key].help_text = _("(%s балл)") % question.points

    def clean(self):
        cleaned_data = super().clean()
        # Ашық сұрақтарды тексеру: екеуі де толтырылмауын қадағалау
        for question in self.assessment.questions.filter(question_type='OPEN'):
            text_field_name = f'question_{question.pk}_text'
            file_field_name = f'question_{question.pk}_file'
            text_value = cleaned_data.get(text_field_name)
            file_value = cleaned_data.get(file_field_name)

            # Тек екеуі бірдей толтырылса ғана қате
            if text_value and file_value:
                 self.add_error(text_field_name, _("Тек мәтіндік жауапты немесе файлды ғана жібере аласыз, екеуін бірге емес."))
                 self.add_error(file_field_name, '') # Екінші өріске бос қате

            # Міндеттілік тексеруі (қажет болса):
            # Егер OPEN сұрағына жауап беру міндетті болса (мысалы, required=True қойылса),
            # осы жерге тексеру қосуға болады:
            # elif not text_value and not file_value and self.fields[text_field_name].required: # Егер өріс required=True болса
            #     self.add_error(text_field_name, _("Осы сұраққа жауап беру міндетті (мәтін немесе файл)."))

        return cleaned_data

    @transaction.atomic # Сақтау операциялары үшін транзакция
    def save(self, commit=True):
        # Тапсырманы жасау (әлі DB-ға жазылмаған)
        submission = Submission(assessment=self.assessment, student=self.student)

        # Егер commit=True болса ғана DB операцияларын жасаймыз
        if commit:
            # Тапсырма бұрыннан бар-жоғын тексереміз
            existing_submission, created = Submission.objects.get_or_create(
                assessment=self.assessment,
                student=self.student,
                defaults={'submitted_at': timezone.now()} # Жаңадан құрылса, уақытын белгілеу
            )

            # Егер тапсырма жаңадан құрылса (created=True), онда жауаптарды сақтаймыз
            if created:
                submission = existing_submission # Жаңадан құрылған объектіні аламыз
                # Әр сұрақ бойынша жауаптарды (Answer) сақтаймыз
                for question in self.assessment.questions.all():
                    answer = Answer(submission=submission, question=question)
                    field_name_base = f'question_{question.pk}'
                    has_answer = False # Бұл сұраққа жауап берілді ме?

                    if question.question_type in ['MCQ', 'TF']:
                        choice_pk = self.cleaned_data.get(f'{field_name_base}_choice')
                        if choice_pk:
                            try:
                                answer.selected_choice = Choice.objects.get(pk=int(choice_pk))
                                has_answer = True
                            except (Choice.DoesNotExist, ValueError, TypeError): pass # Қате болса, жауап жоқ деп есептейміз
                    elif question.question_type == 'MAQ':
                        selected_pks = self.cleaned_data.get(f'{field_name_base}_choices', [])
                        if selected_pks:
                            # ManyToMany өрісі кейінірек бөлек сақталады
                            answer._selected_choice_pks = [int(pk) for pk in selected_pks if pk.isdigit()]
                            if answer._selected_choice_pks: has_answer = True
                    elif question.question_type == 'OPEN':
                        text_data = self.cleaned_data.get(f'{field_name_base}_text')
                        file_data = self.cleaned_data.get(f'{field_name_base}_file')
                        if text_data:
                            answer.text_answer = text_data
                            has_answer = True
                        if file_data:
                            answer.attached_file = file_data # Файл объектісі
                            has_answer = True

                    # Егер жауап берілген болса ғана Answer объектісін сақтаймыз
                    if has_answer:
                        # Файлмен жұмыс істеу ерекшелігі:
                        if question.question_type == 'OPEN' and answer.attached_file:
                            temp_file = answer.attached_file
                            answer.attached_file = None # Файлды уақытша алып тастау
                            answer.save() # Алдымен файлсыз сақтау
                            answer.attached_file = temp_file # Файлды қайта қосу
                            answer.save(update_fields=['attached_file']) # Тек файл өрісін жаңарту
                        else:
                            answer.save() # Файлсыз немесе басқа типтегі сұрақтарды бірден сақтау

                        # MAQ үшін ManyToMany байланысын орнату
                        if question.question_type == 'MAQ' and hasattr(answer, '_selected_choice_pks'):
                            try:
                                choices = Choice.objects.filter(pk__in=answer._selected_choice_pks)
                                answer.selected_choices.set(choices)
                            except (ValueError, TypeError): pass

                # Соңында баллды есептеп, қажет болса is_graded белгісін қоямыз
                submission.score = submission.calculate_score()
                # Егер ашық сұрақтар болмаса, бірден бағаланды деп белгілейміз
                if not self.assessment.questions.filter(question_type='OPEN').exists():
                    submission.is_graded = True
                    submission.graded_at = timezone.now()
                submission.save() # Тапсырманың соңғы өзгерістерін сақтау

                return submission # Жаңадан сақталған тапсырманы қайтару

            else:
                # Егер тапсырма бұрыннан бар болса, ескерту беріп, сол тапсырманы қайтару
                print(f"Warning: Submission already exists for student {self.student} and assessment {self.assessment}. Returning existing.")
                return existing_submission # Бұрыннан бар тапсырманы қайтару

        # Егер commit=False болса, жай ғана жаңа Submission объектісін қайтару
        return submission

class GradeSubmissionForm(forms.ModelForm):
    class Meta: model = Submission; fields = ['score']; widgets = {'score': NumberInput(attrs={'class': 'form-control', 'step': '1'})}
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.assessment:
             max_score = self.instance.assessment.max_score
             if max_score is not None:
                 self.fields['score'].widget.attrs['max'] = max_score
                 self.fields['score'].widget.attrs['placeholder'] = _(f"Макс: {max_score}")
                 self.fields['score'].validators = [MaxValueValidator(max_score), MinValueValidator(0)]
             else:
                 self.fields['score'].validators = [MinValueValidator(0)]

             # Егер бағаланбаса және автоматты есептеу мүмкін болса, бастапқы мән беру
             if not self.instance.is_graded and self.instance.pk:
                try:
                    auto_score = self.instance.calculate_score()
                    if auto_score is not None: self.fields['score'].initial = auto_score
                except Exception as e: print(f"Error calculating auto score for submission {self.instance.pk}: {e}")

    def clean_score(self):
        score = self.cleaned_data.get('score')
        if score is None: return score # Міндетті емес болса, None рұқсат етіледі

        if self.instance and hasattr(self.instance, 'assessment') and self.instance.assessment:
            max_score = self.instance.assessment.max_score
            if max_score is not None and score > max_score:
                raise ValidationError(_("Балл максималды баллдан жоғары бола алмайды (Макс: %(max_score)s)."), params={'max_score': max_score})
        if score < 0: raise ValidationError(_("Балл теріс бола алмайды."))
        return score