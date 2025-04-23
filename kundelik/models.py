# kundelik/models.py

from django.contrib.auth.models import AbstractUser
from django.db import models
from django.core.validators import MaxValueValidator, MinValueValidator
from django.core.exceptions import ValidationError
from django.conf import settings # Рекомендуется для ссылки на User модель
from django.utils.translation import gettext_lazy as _

# Модель Школы
class School(models.Model):
    name = models.CharField("Атауы", max_length=255, unique=True)

    class Meta:
        verbose_name = "Мектеп"
        verbose_name_plural = "Мектептер"
        ordering = ['name']

    def __str__(self):
        return self.name

# Модель Пользователя (расширенная)
class User(AbstractUser):
    ROLE_CHOICES = [
        ('admin', 'Администратор'),
        ('director', 'Директор'),
        ('teacher', 'Мұғалім'),
        ('student', 'Оқушы'),
        ('parent', 'Ата-ана'),
    ]

    email = models.EmailField(_('email address'), unique=True, blank=False, null=False)
    role = models.CharField("Рөлі", max_length=20, choices=ROLE_CHOICES, null=False, blank=False)
    school = models.ForeignKey(
        School, verbose_name="Мектеп", on_delete=models.SET_NULL,
        null=True, blank=True, related_name='users'
    )
    parent_of = models.ForeignKey(
        'self', verbose_name="Оқушы (ата-ана үшін)", on_delete=models.SET_NULL,
        null=True, blank=True, related_name='parents', limit_choices_to={'role': 'student'}
    )
    first_name = models.CharField(_('first name'), max_length=150, blank=False, null=False)
    last_name = models.CharField(_('last name'), max_length=150, blank=False, null=False)
    iin = models.CharField("ЖСН", max_length=12, unique=True, blank=True, null=True)

    USERNAME_FIELD = 'username'
    REQUIRED_FIELDS = ['email', 'first_name', 'last_name', 'role']

    class Meta:
        verbose_name = "Пайдаланушы"
        verbose_name_plural = "Пайдаланушылар"
        ordering = ['last_name', 'first_name']

    def __str__(self):
        full_name = self.get_full_name()
        role_display = self.get_role_display() if self.role else "Рөл жоқ"
        return f"{full_name if full_name else self.username} ({role_display})"

# Модель Профиля Пользователя (связана с User)
class UserProfile(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        primary_key=True, verbose_name="Пайдаланушы", related_name="userprofile"
    )
    patronymic = models.CharField("Әкесінің аты", max_length=100, blank=True, null=True)
    date_of_birth = models.DateField("Туған күні", blank=True, null=True)
    GENDER_CHOICES = [('M', 'Ер'), ('F', 'Әйел')]
    gender = models.CharField("Жынысы", max_length=1, choices=GENDER_CHOICES, blank=True, null=True)
    school_class = models.ForeignKey(
         'Class', verbose_name="Сыныбы", on_delete=models.SET_NULL,
         null=True, blank=True, related_name='student_profiles'
    )
    avatar = models.ImageField(
        "Аватар", upload_to='avatars/', default='avatars/default.png',
        blank=True, null=True
    )

    class Meta:
        verbose_name = "Пайдаланушы профилі"
        verbose_name_plural = "Пайдаланушы профильдері"

    def __str__(self):
        return f"Профиль: {self.user.username}"

    @property
    def grade(self):
        return self.school_class


# Модель Предмета
class Subject(models.Model):
    name = models.CharField("Атауы", max_length=100)
    school = models.ForeignKey(
        School, verbose_name="Мектеп", on_delete=models.CASCADE, related_name='subjects', null=False, blank=False
    )

    class Meta:
        verbose_name = "Пән"
        verbose_name_plural = "Пәндер"
        ordering = ['school', 'name']
        unique_together = ('name', 'school')

    def __str__(self):
        return f"{self.name} ({self.school.name})"

# Модель Класса
class Class(models.Model):
    name = models.CharField("Атауы (мысалы, 10А)", max_length=10)
    school = models.ForeignKey(
        School, verbose_name="Мектеп", on_delete=models.CASCADE, related_name='classes', null=False, blank=False
    )
    teacher = models.ForeignKey(
        settings.AUTH_USER_MODEL, verbose_name="Сынып жетекшісі", on_delete=models.SET_NULL,
        null=True, blank=True, related_name='classes_supervised',
        limit_choices_to={'role__in': ['teacher', 'director', 'admin']}
    )
    subjects = models.ManyToManyField(
        Subject, verbose_name="Осы сыныптың пәндері", blank=True, related_name='classes_taught_in'
    )

    class Meta:
        verbose_name = "Сынып"
        verbose_name_plural = "Сыныптар"
        ordering = ['school', 'name']
        unique_together = ('name', 'school')

    def __str__(self):
        return f"{self.name} ({self.school.name})"


# Модель Расписания/Задания (УАҚЫТ ҚОСЫЛҒАН)
class Schedule(models.Model):
    STATUS_CHOICES = [
        ('assigned', 'Берілді'), ('completed', 'Орындалды'),
        ('not_completed', 'Орындалмады'), ('checked', 'Тексерілді'),
    ]
    LESSON_NUMBER_CHOICES = [(i, str(i)) for i in range(1, 11)] # 1-10 сабақтар

    date = models.DateField("Күні", null=False, blank=False)
    lesson_number = models.PositiveSmallIntegerField(
        "Сабақ нөмірі", choices=LESSON_NUMBER_CHOICES, null=False, blank=False
    )
    # --- УАҚЫТ ӨРІСТЕРІ ҚОСЫЛДЫ ---
    time_start = models.TimeField("Басталу уақыты", null=True, blank=True)
    time_end = models.TimeField("Аяқталу уақыты", null=True, blank=True)
    # --- ---
    school_class = models.ForeignKey(
        Class, verbose_name="Сынып", on_delete=models.CASCADE,
        related_name='schedule_entries', null=False, blank=False
    )
    subject = models.ForeignKey(
        Subject, verbose_name="Пән", on_delete=models.PROTECT,
        related_name='schedules', null=False, blank=False
    )
    teacher = models.ForeignKey(
        settings.AUTH_USER_MODEL, verbose_name="Мұғалім", on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='lessons', limit_choices_to={'role__in': ['teacher', 'director', 'admin']}
    )
    room = models.CharField("Кабинет", max_length=50, blank=True, null=True)
    topic = models.CharField("Сабақ тақырыбы", max_length=255, blank=True, null=True)
    task = models.TextField("Үй тапсырмасы", blank=True, null=True)
    status = models.CharField("Статус", max_length=20, choices=STATUS_CHOICES, default='assigned', blank=True, null=True)

    class Meta:
        verbose_name = "Сабақ кестесі/Тапсырма"
        verbose_name_plural = "Сабақ кестелері/Тапсырмалар"
        # --- ordering өрісіне time_start қосылды ---
        ordering = ['date', 'lesson_number', 'time_start']
        unique_together = [
            ('date', 'school_class', 'lesson_number'),
            ('date', 'teacher', 'lesson_number'),
        ]

    def __str__(self):
        class_str = str(self.school_class.name) if self.school_class else "Сынып жоқ"
        subject_str = str(self.subject.name) if self.subject else "Пән жоқ"
        time_str = f"({self.time_start.strftime('%H:%M')})" if self.time_start else ""
        return f"{self.date} - {self.lesson_number}. {time_str} {class_str} - {subject_str}"

    # Модель деңгейінде қосымша валидация
    def clean(self):
        super().clean()
        # --- УАҚЫТ ТЕКСЕРІСІ ҚОСЫЛДЫ ---
        if self.time_start and self.time_end and self.time_start >= self.time_end:
            raise ValidationError(_('Сабақтың аяқталу уақыты басталу уақытынан кейін болуы керек.'))
        # --- ---

        # Мұғалімнің сол уақытта басқа сабағы бар-жоғын тексеру
        if self.teacher and self.date and self.lesson_number:
            conflicting_lessons = Schedule.objects.filter(
                teacher=self.teacher,
                date=self.date,
                lesson_number=self.lesson_number
            ).exclude(pk=self.pk)
            if conflicting_lessons.exists():
                existing = conflicting_lessons.first()
                raise ValidationError(
                    _('Мұғалім "%(teacher)s" бұл уақытта (%(date)s, %(lesson)s-сабақ) "%(class)s" сыныбындағы "%(subject)s" сабағымен бос емес.'),
                    code='teacher_busy',
                    params={
                        'teacher': self.teacher.get_full_name(),
                        'date': self.date,
                        'lesson': self.lesson_number,
                        'class': existing.school_class.name,
                        'subject': existing.subject.name
                    }
                )
        # Сыныптың сол уақытта басқа сабағы бар-жоғын тексеру
        if self.school_class and self.date and self.lesson_number:
             conflicting_lessons = Schedule.objects.filter(
                 school_class=self.school_class,
                 date=self.date,
                 lesson_number=self.lesson_number
             ).exclude(pk=self.pk)
             if conflicting_lessons.exists():
                 existing = conflicting_lessons.first()
                 raise ValidationError(
                     _('Бұл сынып "%(class)s" бұл уақытта (%(date)s, %(lesson)s-сабақ) "%(subject)s" сабағымен бос емес.'),
                     code='class_busy',
                     params={
                         'class': self.school_class.name,
                         'date': self.date,
                         'lesson': self.lesson_number,
                         'subject': existing.subject.name
                     }
                 )

# Модель Дневной Оценки
class DailyGrade(models.Model):
    student = models.ForeignKey(
        settings.AUTH_USER_MODEL, verbose_name="Оқушы", on_delete=models.CASCADE,
        related_name='daily_grades_received', limit_choices_to={'role': 'student'}
    )
    teacher = models.ForeignKey(
        settings.AUTH_USER_MODEL, verbose_name="Мұғалім", on_delete=models.SET_NULL,
        null=True, related_name='daily_grades_given',
        limit_choices_to={'role__in': ['teacher', 'director', 'admin']}
    )
    subject = models.ForeignKey(
        Subject, verbose_name="Пән", on_delete=models.PROTECT, related_name='daily_grades'
    )
    term = models.PositiveSmallIntegerField("Тоқсан", validators=[MinValueValidator(1), MaxValueValidator(4)], null=False, blank=False)
    grade = models.PositiveSmallIntegerField("Баға", validators=[MinValueValidator(1), MaxValueValidator(5)])
    date = models.DateField("Күні", null=False, blank=False)
    comment = models.CharField("Комментарий", max_length=255, blank=True, null=True)

    class Meta:
        verbose_name = "Күнделікті баға"
        verbose_name_plural = "Күнделікті бағалар"
        ordering = ['-date', 'subject', 'student']
        unique_together = ('student', 'subject', 'date')

    def __str__(self):
        student_name = self.student.get_full_name() or self.student.username
        subject_name = self.subject.name if self.subject else "Пән жоқ"
        return f"{subject_name}: {self.grade} ({self.date}) - {student_name}"

# Модель Оценки за Контрольную (СОР/СОЧ)
class ExamGrade(models.Model):
    EXAM_TYPE_CHOICES = [
        ('SOR', 'БЖБ (СОР)'), ('SOCH', 'ТЖБ (СОЧ)'),
        ('EXAM', 'Емтихан'), ('OTHER', 'Басқа'),
    ]
    student = models.ForeignKey(
        settings.AUTH_USER_MODEL, verbose_name="Оқушы", on_delete=models.CASCADE,
        related_name='exam_grades_received', limit_choices_to={'role': 'student'}
    )
    teacher = models.ForeignKey(
        settings.AUTH_USER_MODEL, verbose_name="Мұғалім", on_delete=models.SET_NULL,
        null=True, related_name='exam_grades_given',
        limit_choices_to={'role__in': ['teacher', 'director', 'admin']}
    )
    subject = models.ForeignKey(
        Subject, verbose_name="Пән", on_delete=models.PROTECT, related_name='exam_grades'
    )
    term = models.PositiveSmallIntegerField("Тоқсан", validators=[MinValueValidator(1), MaxValueValidator(4)], null=False, blank=False)
    exam_type = models.CharField("Жұмыс түрі", max_length=10, choices=EXAM_TYPE_CHOICES, default='SOR')
    grade = models.PositiveIntegerField("Алынған балл")
    max_grade = models.PositiveIntegerField("Макс. балл")
    date = models.DateField("Күні")
    comment = models.CharField("Комментарий", max_length=255, blank=True, null=True)

    class Meta:
        verbose_name = "БЖБ/ТЖБ бағасы"
        verbose_name_plural = "БЖБ/ТЖБ бағалары"
        ordering = ['-date', 'subject', 'student']
        unique_together = ('student', 'subject', 'term', 'exam_type')

    def __str__(self):
        student_name = self.student.get_full_name() or self.student.username
        subject_name = self.subject.name if self.subject else "Пән жоқ"
        return f"{subject_name} ({self.get_exam_type_display()}): {self.grade}/{self.max_grade} ({self.date}) - {student_name}"

    def get_percentage(self):
        if self.max_grade and self.max_grade > 0:
            try:
                if isinstance(self.grade, (int, float)):
                    return round((float(self.grade) / float(self.max_grade)) * 100)
            except (TypeError, ValueError):
                return None
        return None