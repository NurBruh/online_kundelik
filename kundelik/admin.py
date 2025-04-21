# kundelik/admin.py
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin # Для кастомизации UserAdmin
from .models import User, School, Schedule, Subject, DailyGrade, ExamGrade, Class, UserProfile

# --- Настройка для UserProfile (можно встроить в UserAdmin) ---
class UserProfileInline(admin.StackedInline): # Или TabularInline
    model = UserProfile
    can_delete = False
    verbose_name_plural = 'Профиль'
    # --- ИЗМЕНЕНО: Заменили 'grade' на 'school_class' ---
    fields = ('patronymic', 'date_of_birth', 'gender', 'school_class', 'avatar')
    # --- ИЗМЕНЕНО: Заменили 'grade' на 'school_class' ---
    raw_id_fields = ('school_class',) # Если классов много

# --- Кастомный UserAdmin ---
# Используем @admin.register(User) вместо перерегистрации в конце
@admin.register(User)
class CustomUserAdmin(BaseUserAdmin): # Наследуемся от BaseUserAdmin
    # Добавляем UserProfile как встроенную форму
    inlines = (UserProfileInline,)

    # Добавляем кастомные поля в отображение списка
    list_display = ('username', 'email', 'first_name', 'last_name', 'role', 'school', 'is_staff')
    # Добавляем фильтры по роли и школе
    list_filter = BaseUserAdmin.list_filter + ('role', 'school')
    # Добавляем поля в поиск
    search_fields = BaseUserAdmin.search_fields + ('role', 'school__name')

    # Копируем стандартные fieldsets и добавляем/изменяем наши поля
    # Важно: убедитесь, что все поля модели User здесь присутствуют
    fieldsets = (
        (None, {'fields': ('username', 'password')}),
        ('Personal info', {'fields': ('first_name', 'last_name', 'email', 'iin')}), # Добавили iin
        ('Permissions', {'fields': ('is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions')}),
        ('Important dates', {'fields': ('last_login', 'date_joined')}),
        ('Role and School', {'fields': ('role', 'school', 'parent_of')}), # Добавили поля
    )
    # Добавляем поля для формы создания пользователя
    add_fieldsets = BaseUserAdmin.add_fieldsets + (
        # Убрал None, т.к. у секции уже есть имя
        ('Role and School', {'fields': ('first_name', 'last_name', 'email', 'role', 'school', 'parent_of')}),
    )
    # Поля ForeignKey с большим количеством записей лучше отображать через raw_id_fields
    raw_id_fields = ('school', 'parent_of', 'groups', 'user_permissions')
    ordering = ('last_name', 'first_name') # Добавил сортировку по умолчанию

# --- Настройка для Schedule (без времени) ---
@admin.register(Schedule)
class ScheduleAdmin(admin.ModelAdmin):
    list_display = ('date', 'lesson_number', 'subject', 'school_class', 'teacher', 'status', 'topic')
    list_filter = ('date', 'status', 'subject__school', 'school_class', 'teacher', 'subject') # Фильтр по школе предмета
    search_fields = ('topic', 'task', 'subject__name', 'teacher__username', 'school_class__name')
    list_editable = ('status', 'topic') # Позволяет редактировать прямо в списке
    date_hierarchy = 'date'
    ordering = ('-date', 'lesson_number')
    # Убедимся, что все поля модели Schedule здесь
    fields = ('date', 'lesson_number', 'school_class', 'subject', 'teacher', 'topic', 'task', 'status')
    raw_id_fields = ('teacher', 'school_class', 'subject') # Удобный выбор связей

# --- Настройка для DailyGrade (с полем term) ---
@admin.register(DailyGrade)
class DailyGradeAdmin(admin.ModelAdmin):
    list_display = ('date', 'student', 'subject', 'term', 'grade', 'teacher', 'comment')
    # --- ИЗМЕНЕНО: Заменили 'student__userprofile__grade' на 'student__userprofile__school_class' ---
    list_filter = ('term', 'subject__school', 'subject', 'teacher', 'student__userprofile__school_class', 'date') # Добавили term и дату
    search_fields = ('student__username', 'student__first_name', 'student__last_name', 'subject__name', 'teacher__username', 'comment')
    raw_id_fields = ('student', 'teacher', 'subject')
    ordering = ('-date', 'student')
    list_per_page = 25
    date_hierarchy = 'date' # Удобно для навигации по датам

# --- Настройка для ExamGrade (с полем term) ---
@admin.register(ExamGrade)
class ExamGradeAdmin(admin.ModelAdmin):
    list_display = ('date', 'student', 'subject', 'term', 'exam_type', 'grade', 'max_grade', 'teacher', 'comment')
    # --- ИЗМЕНЕНО: Заменили 'student__userprofile__grade' на 'student__userprofile__school_class' ---
    list_filter = ('term', 'exam_type', 'subject__school', 'subject', 'teacher', 'student__userprofile__school_class', 'date') # Добавили дату
    search_fields = ('student__username', 'student__first_name', 'student__last_name', 'subject__name', 'teacher__username', 'comment')
    raw_id_fields = ('student', 'teacher', 'subject')
    ordering = ('-date', 'subject', 'student')
    list_per_page = 25
    date_hierarchy = 'date'

# --- Настройка для Class ---
@admin.register(Class)
class ClassAdmin(admin.ModelAdmin):
    list_display = ('name', 'school', 'teacher')
    list_filter = ('school',)
    search_fields = ('name', 'school__name', 'teacher__username')
    raw_id_fields = ('school', 'teacher') # Убрали subjects, т.к. используем filter_horizontal
    filter_horizontal = ('subjects',) # Удобный виджет для ManyToManyField 'subjects'
    ordering = ('school', 'name')

# --- Настройка для Subject ---
@admin.register(Subject)
class SubjectAdmin(admin.ModelAdmin):
    list_display = ('name', 'school')
    list_filter = ('school',)
    search_fields = ('name', 'school__name')
    ordering = ('school', 'name')

# --- Простая регистрация School ---
# UserProfile уже зарегистрирован через UserAdmin Inline
admin.site.register(School)

# Убрал двойную регистрацию User, т.к. используется декоратор @admin.register(User)
# admin.site.register(User, UserAdmin)