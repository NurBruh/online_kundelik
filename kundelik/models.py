# kundelik/models.py

from django.contrib.auth.models import AbstractUser
from django.db import models
from django.core.validators import MaxValueValidator, MinValueValidator
from django.conf import settings # Рекомендуется для ссылки на User модель

# Модель Школы
class School(models.Model):
    name = models.CharField("Атауы", max_length=255)

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

    email = models.EmailField("Электрондық пошта", unique=True, blank=False, null=False)
    role = models.CharField("Рөлі", max_length=20, choices=ROLE_CHOICES, null=False, blank=False)
    school = models.ForeignKey(
        School, verbose_name="Мектеп", on_delete=models.SET_NULL,
        null=True, blank=True, related_name='users'
    )
    parent_of = models.ForeignKey(
        'self', verbose_name="Оқушы (ата-ана үшін)", on_delete=models.SET_NULL,
        null=True, blank=True, related_name='parents', limit_choices_to={'role': 'student'}
    )
    first_name = models.CharField("Аты", max_length=150, blank=False, null=False)
    last_name = models.CharField("Тегі", max_length=150, blank=False, null=False)
    iin = models.CharField("ЖСН", max_length=12, unique=True, blank=True, null=True)

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
        primary_key=True, verbose_name="Пайдаланушы"
    )
    patronymic = models.CharField("Әкесінің аты", max_length=100, blank=True, null=True)
    date_of_birth = models.DateField("Туған күні", blank=True, null=True)
    GENDER_CHOICES = [('M', 'Ер'), ('F', 'Әйел')]
    gender = models.CharField("Жынысы", max_length=1, choices=GENDER_CHOICES, blank=True, null=True)
    school_class = models.ForeignKey(
        'Class', verbose_name="Сыныбы", on_delete=models.SET_NULL,
        null=True, blank=True, related_name='students_profiles'
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

# Модель Расписания/Задания
class Schedule(models.Model):
    STATUS_CHOICES = [
        ('assigned', 'Берілді'), ('completed', 'Орындалды'),
        ('not_completed', 'Орындалмады'), ('checked', 'Тексерілді'),
    ]
    teacher = models.ForeignKey(
        settings.AUTH_USER_MODEL, verbose_name="Мұғалім", on_delete=models.SET_NULL,
        null=True, related_name='schedules_as_teacher',
        limit_choices_to={'role__in': ['teacher', 'director', 'admin']}
    )
    school_class = models.ForeignKey(
        Class, verbose_name="Сынып", on_delete=models.CASCADE,
        related_name='schedules', null=True, blank=True
    )
    subject = models.ForeignKey(
        Subject, verbose_name="Пән", on_delete=models.PROTECT, related_name='schedules', null=False, blank=False
    )
    date = models.DateField("Күні", null=False, blank=False)
    lesson_number = models.PositiveSmallIntegerField("Сабақ нөмірі", null=True, blank=True)
    topic = models.CharField("Сабақ тақырыбы", max_length=255, blank=True)
    task = models.TextField("Үй тапсырмасы", blank=True)
    status = models.CharField("Статус", max_length=20, choices=STATUS_CHOICES, default='assigned')

    class Meta:
        verbose_name = "Сабақ кестесі/Тапсырма"
        verbose_name_plural = "Сабақ кестелері/Тапсырмалар"
        ordering = ['date', 'lesson_number']
        # unique_together = ('school_class', 'subject', 'date', 'lesson_number')

    def __str__(self):
        class_str = str(self.school_class) if self.school_class else "Жалпы"
        subject_str = str(self.subject) if self.subject else "Пән жоқ"
        return f"{subject_str} - {class_str} - {self.date}"

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
    comment = models.CharField("Комментарий", max_length=255, blank=True)

    class Meta:
        verbose_name = "Күнделікті баға"
        verbose_name_plural = "Күнделікті бағалар"
        ordering = ['-date', 'subject', 'student']
        # Ограничение уникальности для дневных оценок закомментировано
        # unique_together = ('student', 'subject', 'date')

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
    comment = models.CharField("Комментарий", max_length=255, blank=True)

    class Meta:
        verbose_name = "БЖБ/ТЖБ бағасы"
        verbose_name_plural = "БЖБ/ТЖБ бағалары"
        ordering = ['-date', 'subject', 'student']
        # --- ИЗМЕНЕНО: Закомментировали ограничение уникальности ---
        # unique_together = ('student', 'subject', 'term', 'exam_type')

    def __str__(self):
        student_name = self.student.get_full_name() or self.student.username
        subject_name = self.subject.name if self.subject else "Пән жоқ"
        return f"{subject_name} ({self.get_exam_type_display()}): {self.grade}/{self.max_grade} ({self.date}) - {student_name}"

    def get_percentage(self):
        if self.max_grade and self.max_grade > 0:
            try:
                if isinstance(self.grade, (int, float)):
                    return round((self.grade / self.max_grade) * 100)
            except (TypeError, ValueError):
                return None
        return None