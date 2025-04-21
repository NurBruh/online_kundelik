from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin # Для кастомизации UserAdmin
from .models import User, School, Schedule, Subject, DailyGrade, ExamGrade, Class, UserProfile

# --- Настройка для UserProfile (можно встроить в UserAdmin) ---
class UserProfileInline(admin.StackedInline): # Или TabularInline
    model = UserProfile
    can_delete = False
    verbose_name_plural = 'Профиль'
    fields = ('patronymic', 'date_of_birth', 'gender', 'grade', 'avatar')
    raw_id_fields = ('grade',) # Если классов много

# --- Кастомный UserAdmin ---
@admin.register(User)
class UserAdmin(BaseUserAdmin):
    # Добавляем UserProfile как встроенную форму
    inlines = (UserProfileInline,)

    # Добавляем кастомные поля в отображение списка
    list_display = ('username', 'email', 'first_name', 'last_name', 'role', 'school', 'is_staff')
    # Добавляем фильтры по роли и школе
    list_filter = BaseUserAdmin.list_filter + ('role', 'school')
    # Добавляем поля в поиск
    search_fields = BaseUserAdmin.search_fields + ('role', 'school__name')

    # Копируем стандартные fieldsets и добавляем/изменяем наши поля
    fieldsets = (
        (None, {'fields': ('username', 'password')}),
        # Добавляем role и school в личную информацию
        ('Personal info', {'fields': ('first_name', 'last_name', 'email')}),
        # Добавляем кастомную секцию для роли и школы
        ('Role and School', {'fields': ('role', 'school', 'parent_of')}),
        ('Permissions', {'fields': ('is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions')}),
        ('Important dates', {'fields': ('last_login', 'date_joined')}),
    )
    # Добавляем поля для формы создания пользователя
    add_fieldsets = BaseUserAdmin.add_fieldsets + (
        (None, {'fields': ('first_name', 'last_name', 'email', 'role', 'school', 'parent_of')}),
    )
    # Поля ForeignKey с большим количеством записей лучше отображать через raw_id_fields
    raw_id_fields = ('school', 'parent_of', 'groups', 'user_permissions')

# --- Настройка для Schedule (без времени) ---
@admin.register(Schedule)
class ScheduleAdmin(admin.ModelAdmin):
    list_display = ('date', 'lesson_number', 'subject', 'school_class', 'teacher', 'status', 'topic')
    list_filter = ('date', 'status', 'school_class__school', 'school_class', 'teacher', 'subject')
    search_fields = ('topic', 'task', 'subject__name', 'teacher__username', 'school_class__name')
    list_editable = ('status', 'topic')
    date_hierarchy = 'date'
    ordering = ('-date', 'lesson_number')
    # Убрали time_start, time_end. Добавили topic.
    fields = ('date', 'lesson_number', 'school_class', 'subject', 'teacher', 'topic', 'task', 'status')
    raw_id_fields = ('teacher', 'school_class', 'subject')

# --- Настройка для DailyGrade (с полем term) ---
@admin.register(DailyGrade)
class DailyGradeAdmin(admin.ModelAdmin):
    list_display = ('date', 'student', 'subject', 'term', 'grade', 'teacher', 'comment')
    # ВРЕМЕННО УБИРАЕМ 'term' ИЗ ФИЛЬТРА
    list_filter = ('date', 'subject', 'teacher', 'student__school', 'student__userprofile__grade')
    search_fields = ('student__username', 'subject__name', 'teacher__username', 'comment')
    raw_id_fields = ('student', 'teacher', 'subject')
    ordering = ('-date', 'student')
    list_per_page = 25

# --- Настройка для ExamGrade (с полем term) ---
@admin.register(ExamGrade)
class ExamGradeAdmin(admin.ModelAdmin):
    list_display = ('date', 'student', 'subject', 'term', 'exam_type', 'grade', 'max_grade', 'teacher', 'comment') # Добавили term, comment
    list_filter = ('date', 'term', 'exam_type', 'subject', 'teacher', 'student__school', 'student__userprofile__grade')
    search_fields = ('student__username', 'subject__name', 'teacher__username', 'comment')
    raw_id_fields = ('student', 'teacher', 'subject')
    ordering = ('-date', 'subject', 'student')
    list_per_page = 25

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

# --- Простая регистрация School и UserProfile (если не встроен в UserAdmin) ---
admin.site.register(School)
# admin.site.register(UserProfile) # Зарегистрирован через UserAdmin Inline