# kundelik/models.py

import uuid
import os
from django.contrib.auth.models import AbstractUser
from django.db import models
from django.db.models import Sum, Count
from django.core.validators import MaxValueValidator, MinValueValidator
from django.core.exceptions import ValidationError
from django.conf import settings
from django.utils.translation import gettext_lazy as _
from django.utils.deconstruct import deconstructible
from django.utils import timezone
from ckeditor_uploader.fields import RichTextUploadingField

# --- Файл атауын қауіпсіздендіруге арналған функция ---
@deconstructible
class RandomFileName(object):
    def __init__(self, path):
        # path 'avatars/' немесе 'answers/' сияқты болуы керек (алдында / белгісінсіз)
        self.path = path.strip('/') # Алдыңғы және соңғы '/' белгілерін алып тастау

    def __call__(self, instance, filename):
        extension = os.path.splitext(filename)[1].lower() # кеңейтімді кіші әріптермен алу
        # Қауіпсіз кеңейтімдер тізімі (қажет болса кеңейтуге болады)
        allowed_extensions = ['.jpg', '.jpeg', '.png', '.gif']
        if extension not in allowed_extensions:
            # Бұл жерде ValidationError шығаруға болады немесе файл атын өзгертпеуге болады
            # Бірақ файлды сақтамау дұрысырақ. Бұл логиканы формада тексерген жөн.
            # Пока, файл атын қалыпты түрде генерациялаймыз.
            # Немесе: raise ValidationError(f"Рұқсат етілмеген файл кеңейтімі: {extension}")
            pass

        filename_uuid = str(uuid.uuid4())
        # self.path дұрыс форматта болуын қамтамасыз ету
        return os.path.join(self.path, f"{filename_uuid}{extension}")

# Модель Школы (Өзгеріссіз)
class School(models.Model):
    name = models.CharField("Атауы", max_length=255, unique=True)
    class Meta: verbose_name = "Мектеп"; verbose_name_plural = "Мектептер"; ordering = ['name']
    def __str__(self): return self.name

# Модель Пользователя (Өзгеріссіз)
class User(AbstractUser):
    ROLE_CHOICES = [('admin', 'Администратор'),('director', 'Директор'),('teacher', 'Мұғалім'),('student', 'Оқушы'),('parent', 'Ата-ана'),]
    email = models.EmailField(_('email address'), unique=True, blank=False, null=False)
    role = models.CharField("Рөлі", max_length=20, choices=ROLE_CHOICES, null=False, blank=False)
    school = models.ForeignKey(School, verbose_name="Мектеп", on_delete=models.SET_NULL, null=True, blank=True, related_name='users')
    parent_of = models.ForeignKey('self', verbose_name="Оқушы (ата-ана үшін)", on_delete=models.SET_NULL, null=True, blank=True, related_name='parents', limit_choices_to={'role': 'student'})
    first_name = models.CharField(_('first name'), max_length=150, blank=False, null=False)
    last_name = models.CharField(_('last name'), max_length=150, blank=False, null=False)
    iin = models.CharField("ЖСН", max_length=12, unique=True, blank=True, null=True)
    USERNAME_FIELD = 'username'; REQUIRED_FIELDS = ['email', 'first_name', 'last_name', 'role']
    class Meta: verbose_name = "Пайдаланушы"; verbose_name_plural = "Пайдаланушылар"; ordering = ['last_name', 'first_name']
    def __str__(self): full_name = self.get_full_name(); role_display = self.get_role_display() if self.role else "Рөл жоқ"; return f"{full_name if full_name else self.username} ({role_display})"

# Модель Профиля Пользователя (МАҢЫЗДЫ ӨЗГЕРІСТЕР)
class UserProfile(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, primary_key=True, verbose_name="Пайдаланушы", related_name="userprofile")
    patronymic = models.CharField("Әкесінің аты", max_length=100, blank=True, null=True)
    date_of_birth = models.DateField("Туған күні", blank=True, null=True)
    GENDER_CHOICES = [('M', 'Ер'), ('F', 'Әйел')]
    gender = models.CharField("Жынысы", max_length=1, choices=GENDER_CHOICES, blank=True, null=True)
    school_class = models.ForeignKey('Class', verbose_name="Сыныбы", on_delete=models.SET_NULL, null=True, blank=True, related_name='student_profiles')

    # --- AVATAR ӨРІСІ ҮШІН ӨЗГЕРІСТЕР ---
    # RandomFileName класы 'avatars' деген жолды күтеді (алдыңғы '/' белгісінсіз)
    avatar = models.ImageField(
        "Аватар",
        upload_to=RandomFileName('avatars'), # Тек папка аты
        default='avatars/default_avatar.png', # MEDIA_ROOT ішіндегі относительный жол
        blank=True,
        null=True
    )
    # --- AVATAR ӨЗГЕРІСТЕРІ АЯҚТАЛДЫ ---

    class Meta: verbose_name = "Пайдаланушы профилі"; verbose_name_plural = "Пайдаланушы профильдері"
    def __str__(self): return f"Профиль: {self.user.username}"

    @property
    def grade(self): return self.school_class

    # Аватар URL-ін алу үшін қауіпсіз әдіс (егер файл жоқ болса да қате шығармайды)
    @property
    def get_avatar_url(self):
        if self.avatar and hasattr(self.avatar, 'url'):
            try:
                # Файлдың бар-жоғын тексеру (production режимінде маңызды)
                # if default_storage.exists(self.avatar.name):
                return self.avatar.url
            except Exception: # Мысалы, ValueError егер файл жоқ болса
                pass # Төмендегі default суретті қайтарады
        # settings.STATIC_URL қолдану дұрыс емес, себебі default аватар MEDIA-да болуы мүмкін
        # Егер default аватар static-те болса, онда STATIC_URL + 'image/default_avatar.png'
        # Бірақ модельдегі default жолы MEDIA_ROOT-қа қатысты
        # Сондықтан, MEDIA_URL + default жолын қолданған дұрыс, егер default сурет MEDIA ішінде болса
        # Немесе, default суреттің статикалық жолын көрсету:
        # from django.templatetags.static import static
        # return static('image/default_avatar.png') # Егер default_avatar.png static/image/ ішінде болса

        # Ең дұрысы, default мәнін модельде көрсеткендей, сол жолды MEDIA_URL-мен біріктіру
        if self._meta.get_field('avatar').default:
             default_path = str(self._meta.get_field('avatar').default)
             # Егер default_path 'avatars/default_avatar.png' болса, ал MEDIA_URL '/media/' болса,
             # нәтижесі '/media/avatars/default_avatar.png' болады.
             # settings.MEDIA_URL дұрыс конфигурацияланған болуы керек.
             return f"{settings.MEDIA_URL.rstrip('/')}/{default_path.lstrip('/')}"
        return None # Егер default та көрсетілмесе

# Модель Предмета (Өзгеріссіз)
class Subject(models.Model):
    name = models.CharField("Атауы", max_length=100)
    school = models.ForeignKey(School, verbose_name="Мектеп", on_delete=models.CASCADE, related_name='subjects', null=False, blank=False)
    class Meta: verbose_name = "Пән"; verbose_name_plural = "Пәндер"; ordering = ['school', 'name']; unique_together = ('name', 'school')
    def __str__(self): return f"{self.name} ({self.school.name})"

# Модель Класса (Өзгеріссіз)
class Class(models.Model):
    name = models.CharField("Атауы (мысалы, 10А)", max_length=10)
    school = models.ForeignKey(School, verbose_name="Мектеп", on_delete=models.CASCADE, related_name='classes', null=False, blank=False)
    teacher = models.ForeignKey(settings.AUTH_USER_MODEL, verbose_name="Сынып жетекшісі", on_delete=models.SET_NULL, null=True, blank=True, related_name='classes_supervised', limit_choices_to={'role__in': ['teacher', 'director', 'admin']})
    subjects = models.ManyToManyField(Subject, verbose_name="Осы сыныптың пәндері", blank=True, related_name='classes_taught_in')
    class Meta: verbose_name = "Сынып"; verbose_name_plural = "Сыныптар"; ordering = ['school', 'name']; unique_together = ('name', 'school')
    def __str__(self): return f"{self.name} ({self.school.name})"

# Модель Расписания/Задания (Өзгеріссіз)
class Schedule(models.Model):
    STATUS_CHOICES = [('assigned', 'Берілді'), ('completed', 'Орындалды'),('not_completed', 'Орындалмады'), ('checked', 'Тексерілді'),]
    LESSON_NUMBER_CHOICES = [(i, str(i)) for i in range(1, 11)]
    date = models.DateField("Күні", null=False, blank=False)
    lesson_number = models.PositiveSmallIntegerField("Сабақ нөмірі", choices=LESSON_NUMBER_CHOICES, null=False, blank=False)
    time_start = models.TimeField("Басталу уақыты", null=True, blank=True)
    time_end = models.TimeField("Аяқталу уақыты", null=True, blank=True)
    school_class = models.ForeignKey(Class, verbose_name="Сынып", on_delete=models.CASCADE, related_name='schedule_entries', null=False, blank=False)
    subject = models.ForeignKey(Subject, verbose_name="Пән", on_delete=models.PROTECT, related_name='schedules', null=False, blank=False)
    teacher = models.ForeignKey(settings.AUTH_USER_MODEL, verbose_name="Мұғалім", on_delete=models.SET_NULL, null=True, blank=True, related_name='lessons', limit_choices_to={'role__in': ['teacher', 'director', 'admin']})
    room = models.CharField("Кабинет", max_length=50, blank=True, null=True)
    topic = models.CharField("Сабақ тақырыбы", max_length=255, blank=True, null=True)
    task = models.TextField("Үй тапсырмасы", blank=True, null=True)
    status = models.CharField("Статус", max_length=20, choices=STATUS_CHOICES, default='assigned', blank=True, null=True)
    class Meta: verbose_name = "Сабақ кестесі/Тапсырма"; verbose_name_plural = "Сабақ кестелері/Тапсырмалар"; ordering = ['date', 'lesson_number', 'time_start']; unique_together = [('date', 'school_class', 'lesson_number'),('date', 'teacher', 'lesson_number'),]
    def __str__(self): class_str = str(self.school_class.name) if self.school_class else "Сынып жоқ"; subject_str = str(self.subject.name) if self.subject else "Пән жоқ"; time_str = f"({self.time_start.strftime('%H:%M')})" if self.time_start else ""; return f"{self.date} - {self.lesson_number}. {time_str} {class_str} - {subject_str}"
    def clean(self):
        super().clean()
        if self.time_start and self.time_end and self.time_start >= self.time_end: raise ValidationError(_('Сабақтың аяқталу уақыты басталу уақытынан кейін болуы керек.'))
        # Бұл clean методтарындағы тексерулер бұрынғыдай жақсы.

# Модель Дневной Оценки (Өзгеріссіз)
class DailyGrade(models.Model):
    student = models.ForeignKey(settings.AUTH_USER_MODEL, verbose_name="Оқушы", on_delete=models.CASCADE, related_name='daily_grades_received', limit_choices_to={'role': 'student'})
    teacher = models.ForeignKey(settings.AUTH_USER_MODEL, verbose_name="Мұғалім", on_delete=models.SET_NULL, null=True, related_name='daily_grades_given', limit_choices_to={'role__in': ['teacher', 'director', 'admin']})
    subject = models.ForeignKey(Subject, verbose_name="Пән", on_delete=models.PROTECT, related_name='daily_grades')
    term = models.PositiveSmallIntegerField("Тоқсан", validators=[MinValueValidator(1), MaxValueValidator(4)], null=False, blank=False)
    grade = models.PositiveSmallIntegerField("Баға", validators=[MinValueValidator(1), MaxValueValidator(5)])
    date = models.DateField("Күні", null=False, blank=False)
    comment = models.CharField("Комментарий", max_length=255, blank=True, null=True)
    class Meta: verbose_name = "Күнделікті баға"; verbose_name_plural = "Күнделікті бағалар"; ordering = ['-date', 'subject', 'student']; unique_together = ('student', 'subject', 'date')
    def __str__(self): student_name = self.student.get_full_name() or self.student.username; subject_name = self.subject.name if self.subject else "Пән жоқ"; return f"{subject_name}: {self.grade} ({self.date}) - {student_name}"

# Модель Оценки за Контрольную (СОР/СОЧ) (Өзгеріссіз)
class ExamGrade(models.Model):
    EXAM_TYPE_CHOICES = [('SOR', 'БЖБ (СОР)'), ('SOCH', 'ТЖБ (СОЧ)'), ('EXAM', 'Емтихан'), ('OTHER', 'Басқа'),]
    student = models.ForeignKey(settings.AUTH_USER_MODEL, verbose_name="Оқушы", on_delete=models.CASCADE, related_name='exam_grades_received', limit_choices_to={'role': 'student'})
    teacher = models.ForeignKey(settings.AUTH_USER_MODEL, verbose_name="Мұғалім", on_delete=models.SET_NULL, null=True, related_name='exam_grades_given', limit_choices_to={'role__in': ['teacher', 'director', 'admin']})
    subject = models.ForeignKey(Subject, verbose_name="Пән", on_delete=models.PROTECT, related_name='exam_grades')
    term = models.PositiveSmallIntegerField("Тоқсан", validators=[MinValueValidator(1), MaxValueValidator(4)], null=False, blank=False)
    exam_type = models.CharField("Жұмыс түрі", max_length=10, choices=EXAM_TYPE_CHOICES, default='SOR')
    grade = models.PositiveIntegerField("Алынған балл")
    max_grade = models.PositiveIntegerField("Макс. балл")
    date = models.DateField("Күні")
    comment = models.CharField("Комментарий", max_length=255, blank=True, null=True)
    class Meta: verbose_name = "БЖБ/ТЖБ бағасы"; verbose_name_plural = "БЖБ/ТЖБ бағалары"; ordering = ['-date', 'subject', 'student']; unique_together = ('student', 'subject', 'term', 'exam_type')
    def __str__(self): student_name = self.student.get_full_name() or self.student.username; subject_name = self.subject.name if self.subject else "Пән жоқ"; return f"{subject_name} ({self.get_exam_type_display()}): {self.grade}/{self.max_grade} ({self.date}) - {student_name}"
    def get_percentage(self):
        if self.max_grade and self.max_grade > 0:
            try:
                if isinstance(self.grade, (int, float)): return round((float(self.grade) / float(self.max_grade)) * 100)
            except (TypeError, ValueError): return None
        return None

# ==================================================
# --- БЖБ/ТЖБ (ASSESSMENT) МОДЕЛЬДЕРІ ---
# ==================================================
# Assessment, Question, Choice, Submission, Answer, ActivityLog модельдері бұрынғыдай жақсы.
# Calculate_score әдісіне кішігірім түзету енгізілді.

class Assessment(models.Model):
    title = models.CharField("Атауы", max_length=255)
    subject = models.ForeignKey(Subject, verbose_name="Пән", on_delete=models.PROTECT, related_name='assessments')
    school_class = models.ForeignKey(Class, verbose_name="Сынып", on_delete=models.CASCADE, related_name='assessments')
    term = models.PositiveSmallIntegerField("Тоқсан", validators=[MinValueValidator(1), MaxValueValidator(4)])
    exam_type = models.CharField("Жұмыс түрі", max_length=10, choices=ExamGrade.EXAM_TYPE_CHOICES, default='SOR')
    teacher = models.ForeignKey(settings.AUTH_USER_MODEL, verbose_name="Мұғалім (Автор)", on_delete=models.SET_NULL, null=True, related_name='created_assessments', limit_choices_to={'role__in': ['teacher', 'director', 'admin']})
    max_score = models.PositiveIntegerField("Максималды балл", default=0, help_text="Сұрақтардан автоматты түрде есептеледі немесе қолмен қойылады")
    created_at = models.DateTimeField("Құрылған уақыты", auto_now_add=True)
    due_date = models.DateTimeField("Аяқталу мерзімі", null=True, blank=True)
    is_active = models.BooleanField("Белсенді (Оқушыларға көрінеді)", default=False)
    instructions = models.TextField("Нұсқаулық", blank=True, null=True)
    class Meta: verbose_name = "Бағалау (БЖБ/ТЖБ)"; verbose_name_plural = "Бағалаулар (БЖБ/ТЖБ)"; ordering = ['-created_at', 'subject', 'school_class']
    def __str__(self): return f"{self.title} ({self.subject.name} - {self.school_class.name})"
    def recalculate_max_score(self):
        total = self.questions.aggregate(total_points=Sum('points'))['total_points']
        self.max_score = total if total is not None else 0
        self.save(update_fields=['max_score'])

class Question(models.Model):
    QUESTION_TYPE_CHOICES = [('MCQ', 'Бір дұрыс жауапты тест'),('MAQ', 'Бірнеше дұрыс жауапты тест'),('TF', 'Дұрыс/Бұрыс'),('OPEN', 'Ашық жауап (мәтін/файл)'),]
    assessment = models.ForeignKey(Assessment, verbose_name="Бағалау", on_delete=models.CASCADE, related_name='questions')
    text = RichTextUploadingField("Сұрақ мәтіні")
    question_type = models.CharField("Сұрақ түрі", max_length=5, choices=QUESTION_TYPE_CHOICES, default='MCQ')
    order = models.PositiveSmallIntegerField("Реттік нөмірі", default=0)
    points = models.PositiveSmallIntegerField("Балл саны", default=1)
    class Meta: verbose_name = "Сұрақ"; verbose_name_plural = "Сұрақтар"; ordering = ['assessment', 'order']
    def __str__(self): return f"{self.order}. {self.text[:50]}... ({self.assessment.title})"

class Choice(models.Model):
    question = models.ForeignKey(Question, verbose_name="Сұрақ", on_delete=models.CASCADE, related_name='choices')
    text = models.CharField("Нұсқа мәтіні", max_length=500)
    is_correct = models.BooleanField("Дұрыс жауап", default=False)
    class Meta: verbose_name = "Таңдау нұсқасы"; verbose_name_plural = "Таңдау нұсқалары"; ordering = ['question', 'id']
    def __str__(self): return f"{self.text} ({'Дұрыс' if self.is_correct else 'Бұрыс'})"

class Submission(models.Model):
    assessment = models.ForeignKey(Assessment, verbose_name="Бағалау", on_delete=models.CASCADE, related_name='submissions')
    student = models.ForeignKey(settings.AUTH_USER_MODEL, verbose_name="Оқушы", on_delete=models.CASCADE, related_name='assessment_submissions', limit_choices_to={'role': 'student'})
    submitted_at = models.DateTimeField("Тапсырылған уақыты", default=timezone.now)
    score = models.FloatField("Жинаған балл", null=True, blank=True) # IntegerField-тен FloatField-қа өзгертілді (егер ұпайлар бөлшек болса)
    is_graded = models.BooleanField("Бағаланды", default=False)
    graded_at = models.DateTimeField("Бағаланған уақыты", null=True, blank=True)
    class Meta: verbose_name = "Тапсыру (Submission)"; verbose_name_plural = "Тапсырулар"; ordering = ['-submitted_at', 'student']; unique_together = ('assessment', 'student')
    def __str__(self): return f"{self.student.username} - {self.assessment.title} ({self.submitted_at.strftime('%d.%m.%Y %H:%M')})"

    def calculate_score(self):
        calculated_score = 0.0 # Float үшін 0.0
        answers = self.answers.filter(question__question_type__in=['MCQ', 'TF', 'MAQ'])\
                      .select_related('question', 'selected_choice')\
                      .prefetch_related('selected_choices', 'question__choices')
        for answer in answers:
            question = answer.question
            q_points = float(question.points) if question.points is not None else 0.0 # Ұпайды float-қа келтіру
            if question.question_type in ['MCQ', 'TF']:
                if answer.selected_choice and answer.selected_choice.is_correct:
                    calculated_score += q_points
            elif question.question_type == 'MAQ':
                correct_choices_pks = set(question.choices.filter(is_correct=True).values_list('pk', flat=True))
                selected_choices_pks = set(answer.selected_choices.values_list('pk', flat=True))
                if correct_choices_pks == selected_choices_pks and correct_choices_pks:
                    calculated_score += q_points
        return calculated_score # Бұл жерде 0.0 қайтарылады, егер ештеңе есептелмесе


class Answer(models.Model):
    submission = models.ForeignKey(Submission, verbose_name="Тапсыру", on_delete=models.CASCADE, related_name='answers')
    question = models.ForeignKey(Question, verbose_name="Сұрақ", on_delete=models.CASCADE, related_name='answers')
    selected_choice = models.ForeignKey(
        Choice,
        verbose_name="Таңдалған нұсқа (MCQ/TF)",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='single_choice_answers'
    )
    selected_choices = models.ManyToManyField(
        Choice,
        verbose_name="Таңдалған нұсқалар (MAQ)",
        blank=True,
        related_name='multiple_choice_answers'
    )
    text_answer = models.TextField("Мәтіндік жауап (OPEN)", null=True, blank=True)
    attached_file = models.FileField("Тіркелген файл (OPEN)", upload_to=RandomFileName('answers'), null=True, blank=True) # RandomFileName('answers')
    score = models.FloatField("Жеке балл (мұғалім)", null=True, blank=True)
    class Meta:
        verbose_name = "Жауап";
        verbose_name_plural = "Жауаптар";
        unique_together = ('submission', 'question')
    def __str__(self):
        q_text = self.question.text[:20] if self.question else "Сұрақ жоқ"
        if self.selected_choice: return f"{q_text}... -> (MCQ/TF) {self.selected_choice.text[:20]}..."
        elif self.selected_choices.exists(): choices_str = ", ".join([c.text[:15] for c in self.selected_choices.all()]); return f"{q_text}... -> (MAQ) [{choices_str}...]"
        elif self.text_answer: return f"{q_text}... -> (OPEN) {self.text_answer[:20]}..."
        elif self.attached_file: return f"{q_text}... -> (OPEN) Файл: {os.path.basename(self.attached_file.name)}"
        else: return f"{q_text}... (Жауап жоқ)"

class ActivityLog(models.Model):
    ACTIVITY_TYPES = [('LOGIN', 'Жүйеге кіру'),('SUBMIT_ASSESSMENT', 'БЖБ/ТЖБ тапсыру'),]
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='activity_logs', verbose_name="Пайдаланушы")
    activity_type = models.CharField("Әрекет түрі", max_length=30, choices=ACTIVITY_TYPES, db_index=True)
    timestamp = models.DateTimeField("Уақыты", default=timezone.now, db_index=True)
    details = models.JSONField("Қосымша ақпарат", null=True, blank=True)
    class Meta: verbose_name = "Белсенділік журналы"; verbose_name_plural = "Белсенділік журналдары"; ordering = ['-timestamp']
    def __str__(self): return f"{self.user.username} - {self.get_activity_type_display()} - {self.timestamp.strftime('%Y-%m-%d %H:%M')}"