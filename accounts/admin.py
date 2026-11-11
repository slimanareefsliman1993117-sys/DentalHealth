from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.utils.html import format_html
from .models import User, PatientProfile, StudentProfile, DoctorProfile, Specialty, Case
from .admin_site import STATUS_LABELS
from django.core.exceptions import PermissionDenied
from .demo import is_public_demo, data_alias


FIELD_LABELS = {
    'username': 'اسم المستخدم', 'email': 'البريد الإلكتروني', 'user_type': 'نوع الحساب',
    'first_name': 'الاسم الأول', 'last_name': 'اسم العائلة', 'clinical_access_approved': 'اعتماد الوصول الطبي',
    'user': 'الحساب المرتبط', 'profile_image': 'الصورة الشخصية', 'phone': 'رقم الهاتف',
    'gender': 'الجنس', 'birthdate': 'تاريخ الميلاد', 'age': 'العمر', 'birthplace': 'مكان الولادة',
    'chronic_diseases': 'الأمراض المزمنة', 'additional_info': 'معلومات إضافية',
    'specialty': 'الاختصاص', 'years_of_teaching': 'السنوات الدراسية / التدريس', 'wanted_groups': 'المجموعات المطلوبة',
    'patient': 'المريض', 'title': 'عنوان الحالة', 'description': 'وصف الحالة',
    'pain_type': 'نوع الألم', 'pain_location': 'موضع الألم', 'pain_duration': 'مدة الألم',
    'treated_before': 'علاج سابق', 'physician_notes': 'ملاحظات الطبيب', 'photos': 'صورة الحالة',
    'status': 'حالة المتابعة', 'name': 'اسم الاختصاص',
}
ROLE_LABELS = {'patient': 'مريض', 'doctor': 'طبيب', 'student': 'طالب'}
CHOICE_LABELS = {
    'male': 'ذكر', 'female': 'أنثى', 'other': 'آخر', 'dentistry': 'طب الأسنان',
    'oral_surgery': 'جراحة الفم', 'orthodontics': 'تقويم الأسنان', 'prosthodontics': 'التعويضات السنية',
    'pediatrics': 'طب أسنان الأطفال', 'throbbing': 'نابض', 'sharp': 'حاد', 'continuous': 'مستمر',
    'intermittent': 'متقطع', 'mandible': 'الفك السفلي', 'maxilla': 'الفك العلوي', 'right': 'اليمين',
    'left': 'اليسار', 'less_than_a_day': 'أقل من يوم', '1-3_days': 'من يوم إلى ثلاثة أيام',
    'a_week': 'أسبوع', 'more_than_a_week': 'أكثر من أسبوع', **ROLE_LABELS, **STATUS_LABELS,
}


class DentalAdminMixin:
    list_per_page = 20
    save_on_top = True
    empty_value_display = '—'
    singular = 'سجل'
    plural = 'السجلات'

    def get_queryset(self, request):
        return super().get_queryset(request).using(data_alias(request.user))

    def has_add_permission(self, request):
        return not is_public_demo(request.user) and super().has_add_permission(request)

    def has_change_permission(self, request, obj=None):
        return not is_public_demo(request.user) and super().has_change_permission(request, obj)

    def has_delete_permission(self, request, obj=None):
        return not is_public_demo(request.user) and super().has_delete_permission(request, obj)

    def history_view(self, request, object_id, extra_context=None):
        if is_public_demo(request.user):
            raise PermissionDenied
        return super().history_view(request, object_id, extra_context)

    def formfield_for_dbfield(self, db_field, request, **kwargs):
        field = super().formfield_for_dbfield(db_field, request, **kwargs)
        if field is not None and db_field.name in FIELD_LABELS:
            field.label = FIELD_LABELS[db_field.name]
        return field

    def formfield_for_choice_field(self, db_field, request, **kwargs):
        if 'choices' not in kwargs:
            choices = [(value, CHOICE_LABELS.get(value, label)) for value, label in db_field.flatchoices]
            if db_field.blank or not db_field.has_default():
                choices = [('', '---------')] + choices
            kwargs['choices'] = choices
        return super().formfield_for_choice_field(db_field, request, **kwargs)

    def changelist_view(self, request, extra_context=None):
        return super().changelist_view(request, {**(extra_context or {}), 'title': self.plural, 'dental_description': self.description, 'dental_singular': self.singular, 'dental_plural': self.plural})

    def changeform_view(self, request, object_id=None, form_url='', extra_context=None):
        title = ('إضافة ' if object_id is None else 'تفاصيل ') + self.singular
        return super().changeform_view(request, object_id, form_url, {**(extra_context or {}), 'title': title, 'dental_description': self.description, 'dental_singular': self.singular, 'dental_plural': self.plural})

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        field = super().formfield_for_foreignkey(db_field, request, **kwargs)
        if field is not None and db_field.remote_field.model is User:
            field.label_from_instance = lambda obj: f'{obj.get_full_name() or obj.username} ({obj.email})'
        return field

    @admin.display(description='الاسم')
    def person(self, obj):
        user = obj.user if hasattr(obj, 'user') else obj
        name = user.get_full_name() or user.email
        return format_html('<span class="person-cell"><span class="person-avatar">{}</span><span><strong>{}</strong><small dir="ltr">{}</small></span></span>', name[:1], name, user.email)


class RoleFilter(admin.SimpleListFilter):
    title = 'نوع الحساب'
    parameter_name = 'user_type__exact'
    def lookups(self, request, model_admin):
        return list(ROLE_LABELS.items())
    def queryset(self, request, queryset):
        return queryset.filter(user_type=self.value()) if self.value() in ROLE_LABELS else queryset


class ApprovalFilter(admin.SimpleListFilter):
    title = 'الاعتماد الطبي'
    parameter_name = 'clinical_access_approved__exact'
    def lookups(self, request, model_admin):
        return [('1', 'معتمد'), ('0', 'بانتظار الاعتماد')]
    def queryset(self, request, queryset):
        return queryset.filter(**{self.parameter_name: self.value() == '1'}) if self.value() in {'0', '1'} else queryset


class DoctorApprovalFilter(ApprovalFilter):
    parameter_name = 'user__clinical_access_approved'


class DoctorActiveFilter(ApprovalFilter):
    title = 'حالة الحساب'
    parameter_name = 'user__is_active'
    def lookups(self, request, model_admin):
        return [('1', 'نشط'), ('0', 'غير نشط')]


class StatusFilter(admin.SimpleListFilter):
    title = 'حالة المتابعة'
    parameter_name = 'status__exact'
    def lookups(self, request, model_admin):
        return list(STATUS_LABELS.items())
    def queryset(self, request, queryset):
        return queryset.filter(status=self.value()) if self.value() in STATUS_LABELS else queryset


class SpecialtyFilter(admin.SimpleListFilter):
    title = 'الاختصاص'
    parameter_name = 'specialty__exact'
    def lookups(self, request, model_admin):
        return [(value, CHOICE_LABELS[value]) for value, label in DoctorProfile.SPECIALTY_CHOICES]
    def queryset(self, request, queryset):
        return queryset.filter(specialty=self.value()) if self.value() in dict(DoctorProfile.SPECIALTY_CHOICES) else queryset


class TeachingYearFilter(admin.SimpleListFilter):
    title = 'السنة الدراسية / التدريس'
    parameter_name = 'years_of_teaching__exact'
    def lookups(self, request, model_admin):
        return [(str(i), str(i)) for i in range(1, 9)]
    def queryset(self, request, queryset):
        return queryset.filter(years_of_teaching=int(self.value())) if self.value() in {str(i) for i in range(1, 9)} else queryset


class PriorTreatmentFilter(admin.SimpleListFilter):
    title = 'علاج سابق'
    parameter_name = 'treated_before__exact'
    def lookups(self, request, model_admin):
        return [('1', 'نعم'), ('0', 'لا')]
    def queryset(self, request, queryset):
        return queryset.filter(treated_before=self.value() == '1') if self.value() in {'0', '1'} else queryset


@admin.register(User)
class UserAdmin(DentalAdminMixin, BaseUserAdmin):
    singular, plural = 'مستخدم', 'المستخدمون'
    description = 'إدارة حسابات الفريق والمرضى وصلاحيات الوصول.'
    list_display = ('person', 'role_badge', 'approval_badge', 'is_active', 'date_joined')
    list_filter = (RoleFilter, ApprovalFilter, 'is_active', 'is_staff')
    fieldsets = (
        ('معلومات الحساب', {'fields': ('username', 'email', 'password')}),
        ('البيانات الشخصية', {'fields': (('first_name', 'last_name'), 'user_type')}),
        ('الوصول والصلاحيات', {'fields': ('is_active', 'clinical_access_approved', 'is_staff', 'is_superuser', 'groups', 'user_permissions'),
                                 'description': 'اعتمد الوصول الطبي بعد التحقق من هوية الطبيب ومؤهلاته.'}),
    )
    add_fieldsets = ((None, {'classes': ('wide',), 'fields': ('username', 'email', ('first_name', 'last_name'), 'user_type', 'password1', 'password2')}),)
    search_fields = ('username', 'email', 'first_name', 'last_name')
    ordering = ('-date_joined',)
    filter_horizontal = ('groups', 'user_permissions')

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        profile_model = {'patient': PatientProfile, 'student': StudentProfile, 'doctor': DoctorProfile}[obj.user_type]
        defaults = {} if obj.user_type == 'patient' else {'specialty': 'dentistry'}
        profile_model.objects.get_or_create(user=obj, defaults=defaults)

    @admin.display(description='نوع الحساب', ordering='user_type')
    def role_badge(self, obj):
        return format_html('<span class="status-badge role-{}">{}</span>', obj.user_type, ROLE_LABELS[obj.user_type])

    @admin.display(description='الاعتماد الطبي', ordering='clinical_access_approved')
    def approval_badge(self, obj):
        if obj.user_type != 'doctor':
            return '—'
        return format_html('<span class="status-badge status-{}">{}</span>', 'completed' if obj.clinical_access_approved else 'pending', 'معتمد' if obj.clinical_access_approved else 'بانتظار الاعتماد')


class ProfileAdmin(DentalAdminMixin, admin.ModelAdmin):
    list_display = ('person', 'phone_display', 'age_display')
    list_select_related = ('user',)
    search_fields = ('user__email', 'user__first_name', 'user__last_name', 'phone')
    readonly_fields = ('age_display',)
    ordering = ('-pk',)

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == 'user':
            role = {PatientProfile: 'patient', DoctorProfile: 'doctor', StudentProfile: 'student'}[self.model]
            kwargs['queryset'] = User.objects.filter(user_type=role)
        return super().formfield_for_foreignkey(db_field, request, **kwargs)

    @admin.display(description='العمر')
    def age_display(self, obj):
        return obj.age

    @admin.display(description='رقم الهاتف', ordering='phone')
    def phone_display(self, obj):
        return obj.phone

    @admin.display(description='الاختصاص', ordering='specialty')
    def specialty_display(self, obj):
        return CHOICE_LABELS.get(obj.specialty, obj.specialty)


@admin.register(PatientProfile)
class PatientAdmin(ProfileAdmin):
    singular, plural = 'ملف مريض', 'المرضى'
    description = 'ملفات المرضى وبيانات التواصل والمعلومات الصحية المسجلة.'
    fieldsets = (
        ('البيانات الأساسية', {'fields': ('user', 'profile_image', ('phone', 'gender'), ('birthdate', 'age_display'), 'birthplace')}),
        ('المعلومات الصحية', {'fields': ('chronic_diseases', 'additional_info')}),
    )


@admin.register(DoctorProfile)
class DoctorAdmin(ProfileAdmin):
    singular, plural = 'ملف طبيب', 'الأطباء'
    description = 'بيانات الأطباء والاختصاصات وحالة اعتماد الوصول الطبي.'
    list_display = ('person', 'specialty_display', 'phone_display', 'approved')
    list_filter = (DoctorApprovalFilter, DoctorActiveFilter, SpecialtyFilter)
    fieldsets = (
        ('البيانات الأساسية', {'fields': ('user', 'profile_image', ('phone', 'gender'), ('birthdate', 'age_display'), 'birthplace')}),
        ('الاختصاص والعمل', {'fields': ('specialty', ('years_of_teaching', 'wanted_groups'))}),
    )
    @admin.display(description='معتمد', boolean=True, ordering='user__clinical_access_approved')
    def approved(self, obj):
        return obj.user.clinical_access_approved


@admin.register(StudentProfile)
class StudentAdmin(ProfileAdmin):
    singular, plural = 'ملف طالب', 'الطلاب'
    description = 'ملفات الطلاب واختصاصاتهم ومجموعاتهم الدراسية.'
    list_display = ('person', 'specialty_display', 'teaching_display', 'groups_display')
    list_filter = (SpecialtyFilter, TeachingYearFilter)
    fieldsets = DoctorAdmin.fieldsets

    @admin.display(description='السنة الدراسية / التدريس', ordering='years_of_teaching')
    def teaching_display(self, obj):
        return obj.years_of_teaching

    @admin.display(description='المجموعات المطلوبة', ordering='wanted_groups')
    def groups_display(self, obj):
        return obj.wanted_groups


@admin.register(Case)
class CaseAdmin(DentalAdminMixin, admin.ModelAdmin):
    singular, plural = 'حالة طبية', 'الحالات الطبية'
    description = 'متابعة حالات المرضى من المراجعة الأولى حتى اكتمال العلاج.'
    list_display = ('case_title', 'patient_name', 'status_badge', 'created_display', 'updated_display')
    list_filter = (StatusFilter, PriorTreatmentFilter)
    search_fields = ('title', 'patient__email', 'patient__first_name', 'patient__last_name')
    list_select_related = ('patient',)
    date_hierarchy = 'created_at'
    ordering = ('-created_at', '-pk')
    readonly_fields = ('created_display', 'updated_display')
    fieldsets = (
        ('ملف الحالة', {'fields': (('title', 'status'), 'patient', 'description')}),
        ('الأعراض والتاريخ', {'fields': (('pain_type', 'pain_location'), ('pain_duration', 'treated_before'))}),
        ('المرفقات والملاحظات', {'fields': ('photos', 'physician_notes')}),
        ('سجل المتابعة', {'fields': (('created_display', 'updated_display'),), 'classes': ('collapse',)}),
    )
    @admin.display(description='تاريخ الإضافة', ordering='created_at')
    def created_display(self, obj):
        return obj.created_at

    @admin.display(description='آخر تحديث', ordering='updated_at')
    def updated_display(self, obj):
        return obj.updated_at

    @admin.display(description='الحالة', ordering='title')
    def case_title(self, obj):
        return obj.title or f'حالة رقم {obj.pk}'
    @admin.display(description='المريض', ordering='patient__first_name')
    def patient_name(self, obj):
        return obj.patient.get_full_name() or obj.patient.email
    @admin.display(description='حالة المتابعة', ordering='status')
    def status_badge(self, obj):
        return format_html('<span class="status-badge status-{}"><i></i>{}</span>', obj.status, STATUS_LABELS[obj.status])


@admin.register(Specialty)
class SpecialtyAdmin(DentalAdminMixin, admin.ModelAdmin):
    singular, plural = 'اختصاص', 'الاختصاصات'
    description = 'تنظيم الاختصاصات المسجلة في العيادة.'
    list_display = ('name_display',)
    search_fields = ('name',)

    @admin.display(description='اسم الاختصاص', ordering='name')
    def name_display(self, obj):
        return obj.name
