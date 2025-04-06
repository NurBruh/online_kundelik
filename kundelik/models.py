from django.contrib.auth.models import AbstractUser
from django.db import models
from django.core.validators import MaxValueValidator, MinValueValidator


class School(models.Model):
    name = models.CharField(max_length=255)

    def __str__(self):
        return self.name


class User(AbstractUser):
    ROLE_CHOICES = [
        ('admin', 'Администратор'),
        ('director', 'Директор'),
        ('teacher', 'Учитель'),
        ('student', 'Ученик'),
        ('parent', 'Родитель'),
    ]

    role = models.CharField(max_length=20, choices=ROLE_CHOICES)
    school = models.ForeignKey(School, on_delete=models.SET_NULL, null=True, blank=True)
    parent_of = models.ForeignKey('self', on_delete=models.SET_NULL, null=True, blank=True, related_name='children')

    first_name = models.CharField(max_length=150, blank=True)
    last_name = models.CharField(max_length=150, blank=True)
    surname = models.CharField(max_length=150, blank=True)

    iin = models.CharField(max_length=12, unique=True, blank=True, null=True, verbose_name="ИИН")  # Добавлен ИИН
    birth_date = models.DateField(null=True, blank=True, verbose_name="Дата рождения")  # Добавлена дата рождения

    def __str__(self):
        return f"{self.first_name} {self.last_name} {self.surname} ({self.get_role_display()})"


class Subject(models.Model):
    name = models.CharField(max_length=100)
    school = models.ForeignKey(School, on_delete=models.CASCADE, related_name='subjects')

    def __str__(self):
        return self.name


class Class(models.Model):
    name = models.CharField(max_length=10)  # Например, "1A", "5Б", "10"
    school = models.ForeignKey(School, on_delete=models.CASCADE, related_name='classes')
    teacher = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True,
                                related_name='classes_taught')  # Куратор

    def __str__(self):
        return self.name


class Schedule(models.Model):
    STATUS_CHOICES = [
        ('assigned', 'Задано'),
        ('completed', 'Выполнено'),
        ('not_completed', 'Не выполнено'),
    ]
    student = models.ForeignKey(User, on_delete=models.CASCADE, related_name='schedules_as_student')
    teacher = models.ForeignKey(User, on_delete=models.CASCADE, related_name='schedules_as_teacher')
    subject = models.ForeignKey(Subject, on_delete=models.CASCADE, related_name='schedules')
    date = models.DateField()
    time = models.TimeField()
    task = models.TextField(blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='assigned')
    lesson_number = models.IntegerField(null=True, blank=True)
    school_class = models.ForeignKey(Class, on_delete=models.CASCADE, related_name='schedules',
                                     null=True)  # Добавил связь с классом

    def __str__(self):
        return f"{self.subject} для {self.student} ({self.school_class}) с {self.teacher} ({self.date} {self.time})"


class DailyGrade(models.Model):
    student = models.ForeignKey(User, on_delete=models.CASCADE, related_name='daily_grades_received')
    teacher = models.ForeignKey(User, on_delete=models.CASCADE, related_name='daily_grades_given')
    subject = models.ForeignKey(Subject, on_delete=models.CASCADE, related_name='daily_grades')
    grade = models.IntegerField(validators=[MinValueValidator(0), MaxValueValidator(10)])
    date = models.DateField()

    def __str__(self):
        return f"{self.subject}: {self.grade}/10 для {self.student} от {self.teacher} ({self.date})"

    def get_traditional_grade(self):
        percentage = (self.grade / 10) * 100
        if percentage >= 85:
            return 5
        elif percentage >= 70:
            return 4
        elif percentage >= 50:
            return 3
        else:
            return 2


class ExamGrade(models.Model):
    student = models.ForeignKey(User, on_delete=models.CASCADE, related_name='exam_grades_received')
    teacher = models.ForeignKey(User, on_delete=models.CASCADE, related_name='exam_grades_given')
    subject = models.ForeignKey(Subject, on_delete=models.CASCADE, related_name='exam_grades')
    grade = models.IntegerField()  # Балл за контрольную (без ограничения)
    max_grade = models.IntegerField()  # Максимальный балл за эту контрольную
    date = models.DateField()

    def __str__(self):
        return f"{self.subject}: {self.grade}/{self.max_grade} для {self.student} от {self.teacher} ({self.date})"

class UserProfile(models.Model):
    # Связь с основной моделью пользователя
    # related_name='userprofile' позволяет обращаться user.userprofile
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='userprofile')
    # Ваши дополнительные поля
    patronymic = models.CharField("Әкесінің аты", max_length=100, blank=True, null=True)
    date_of_birth = models.DateField("Туған күні", blank=True, null=True)
    # Пример поля с выбором
    GENDER_CHOICES = [('M', 'Ер'), ('F', 'Әйел')]
    gender = models.CharField("Жынысы", max_length=1, choices=GENDER_CHOICES, blank=True, null=True)
    grade = models.CharField("Сыныбы", max_length=10, blank=True, null=True) # Или ForeignKey на Class
    avatar = models.ImageField("Аватар", upload_to='avatars/', default='avatars/default.png', blank=True, null=True)
    # ... другие поля ...

    def __str__(self):
        return f"Профиль: {self.user.username}"