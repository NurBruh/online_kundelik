from django.contrib import admin
from .models import User, School, Schedule, Subject, DailyGrade, ExamGrade, Class

admin.site.register(User)
admin.site.register(School)
admin.site.register(Schedule)
admin.site.register(DailyGrade)
admin.site.register(ExamGrade)
admin.site.register(Subject)
admin.site.register(Class)
