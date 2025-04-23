# kundelik/admin.py
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
# Добавим get_user_model для более надежного получения модели User
from django.contrib.auth import get_user_model
# Импортируем reverse для создания ссылок в админке
from django.urls import reverse
from django.utils.html import format_html

from .models import School, Schedule, Subject, DailyGrade, ExamGrade, Class, UserProfile

# Получаем актуальную модель пользователя
User = get_user_model()

# --- Настройка для UserProfile (встроена в UserAdmin) ---
class UserProfileInline(admin.StackedInline):
    model = UserProfile
    can_delete = False
    verbose_name_plural = 'Профиль'
    fields = ('patronymic', 'date_of_birth', 'gender', 'school_class', 'avatar')
    raw_id_fields = ('school_class',) # Используем raw_id для ForeignKey

# --- Кастомный UserAdmin ---
@admin.register(User)
class CustomUserAdmin(BaseUserAdmin):
    inlines = (UserProfileInline,)
    list_display = ('username', 'email', 'first_name', 'last_name', 'role', 'school', 'is_staff')
    list_filter = BaseUserAdmin.list_filter + ('role', 'school')
    search_fields = BaseUserAdmin.search_fields + ('role', 'school__name')
    fieldsets = (
        (None, {'fields': ('username', 'password')}),
        ('Personal info', {'fields': ('first_name', 'last_name', 'email', 'iin')}),
        ('Permissions', {'fields': ('is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions')}),
        ('Important dates', {'fields': ('last_login', 'date_joined')}),
        ('Role and School', {'fields': ('role', 'school', 'parent_of')}),
    )
    add_fieldsets = BaseUserAdmin.add_fieldsets + (
        ('Role and School', {'fields': ('first_name', 'last_name', 'email', 'role', 'school', 'parent_of')}),
    )
    raw_id_fields = ('school', 'parent_of', 'groups', 'user_permissions')
    ordering = ('last_name', 'first_name')

# --- НОВЫЙ Inline для отображения студентов в ClassAdmin ---
class StudentProfileInlineForClass(admin.TabularInline): # TabularInline компактнее
    model = UserProfile
    # Указываем ForeignKey от UserProfile к Class
    fk_name = 'school_class'
    # Поля для отображения в строке
    fields = ('get_user_link', 'patronymic', 'date_of_birth')
    readonly_fields = ('get_user_link', 'patronymic', 'date_of_birth') # Делаем все поля только для чтения
    # Добавляем метод для отображения ссылки на пользователя
    list_display = ('get_user_link',) # Не обязательно, но можно

    # Названия
    verbose_name = "Оқушы"
    verbose_name_plural = "Осы сыныптың оқушылары"

    # Убираем возможность добавлять/удалять профили отсюда
    extra = 0
    can_delete = False
    max_num = 0 # Запрещаем добавление новых

    def get_queryset(self, request):
        # Фильтруем queryset, чтобы показывать только студентов
        qs = super().get_queryset(request)
        return qs.filter(user__role='student').select_related('user')

    # Функция для создания ссылки на страницу пользователя в админке
    def get_user_link(self, obj):
        if obj.user:
            user_admin_url = reverse('admin:%s_%s_change' % (obj.user._meta.app_label, obj.user._meta.model_name), args=[obj.user.pk])
            return format_html('<a href="{}">{}</a>', user_admin_url, obj.user.get_full_name() or obj.user.username)
        return "-"
    get_user_link.short_description = 'Оқушы (ФИО)' # Название колонки

# --- Настройка для Class (С ДОБАВЛЕННЫМ INLINE) ---
@admin.register(Class)
class ClassAdmin(admin.ModelAdmin):
    list_display = ('name', 'school', 'teacher')
    list_filter = ('school',)
    search_fields = ('name', 'school__name', 'teacher__username')
    raw_id_fields = ('school', 'teacher')
    filter_horizontal = ('subjects',)
    ordering = ('school', 'name')
    # Добавляем инлайн для отображения студентов
    inlines = [StudentProfileInlineForClass] # <--- ДОБАВЛЕНО

# --- Остальные настройки админки (без изменений) ---
@admin.register(Schedule)
class ScheduleAdmin(admin.ModelAdmin):
    list_display = ('date', 'lesson_number', 'subject', 'school_class', 'teacher', 'status', 'topic')
    list_filter = ('date', 'status', 'subject__school', 'school_class', 'teacher', 'subject')
    search_fields = ('topic', 'task', 'subject__name', 'teacher__username', 'school_class__name')
    list_editable = ('status', 'topic')
    date_hierarchy = 'date'
    ordering = ('-date', 'lesson_number')
    fields = ('date', 'lesson_number', 'school_class', 'subject', 'teacher', 'topic', 'task', 'status')
    raw_id_fields = ('teacher', 'school_class', 'subject')

@admin.register(DailyGrade)
class DailyGradeAdmin(admin.ModelAdmin):
    list_display = ('date', 'student', 'subject', 'term', 'grade', 'teacher', 'comment')
    list_filter = ('term', 'subject__school', 'subject', 'teacher', 'student__userprofile__school_class', 'date')
    search_fields = ('student__username', 'student__first_name', 'student__last_name', 'subject__name', 'teacher__username', 'comment')
    raw_id_fields = ('student', 'teacher', 'subject')
    ordering = ('-date', 'student')
    list_per_page = 25
    date_hierarchy = 'date'

@admin.register(ExamGrade)
class ExamGradeAdmin(admin.ModelAdmin):
    list_display = ('date', 'student', 'subject', 'term', 'exam_type', 'grade', 'max_grade', 'teacher', 'comment')
    list_filter = ('term', 'exam_type', 'subject__school', 'subject', 'teacher', 'student__userprofile__school_class', 'date')
    search_fields = ('student__username', 'student__first_name', 'student__last_name', 'subject__name', 'teacher__username', 'comment')
    raw_id_fields = ('student', 'teacher', 'subject')
    ordering = ('-date', 'subject', 'student')
    list_per_page = 25
    date_hierarchy = 'date'

@admin.register(Subject)
class SubjectAdmin(admin.ModelAdmin):
    list_display = ('name', 'school')
    list_filter = ('school',)
    search_fields = ('name', 'school__name')
    ordering = ('school', 'name')

admin.site.register(School)