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

    def __str__(self):
        return f"{self.first_name} {self.last_name} ({self.get_role_display()})"


class Subject(models.Model):
    name = models.CharField(max_length=100)
    school = models.ForeignKey(School, on_delete=models.CASCADE, related_name='subjects')

    def __str__(self):
        return self.name


class Class(models.Model):
    name = models.CharField(max_length=10)  # Например, "1A", "5Б", "10"
    school = models.ForeignKey(School, on_delete=models.CASCADE, related_name='classes')
    teacher = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True,
                                related_name='classes_taught')  # куратор

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