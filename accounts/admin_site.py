from datetime import timedelta
from urllib.parse import urlencode
from django.contrib.admin import AdminSite
from django.contrib.admin.forms import AdminAuthenticationForm
from django.db.models import Count
from django.db.models.functions import TruncDate
from django.urls import reverse
from django.utils import timezone
from .models import User, PatientProfile, DoctorProfile, Case


MODEL_LABELS = {
    'user': ('المستخدمون', 'users'), 'patientprofile': ('المرضى', 'patient'),
    'doctorprofile': ('الأطباء', 'doctor'), 'studentprofile': ('الطلاب', 'student'),
    'case': ('الحالات الطبية', 'case'), 'specialty': ('الاختصاصات', 'grid'),
    'group': ('مجموعات الصلاحيات', 'shield'),
    'outstandingtoken': ('جلسات الدخول', 'key'), 'blacklistedtoken': ('الجلسات الملغاة', 'key'),
}
STATUS_LABELS = {'pending': 'بانتظار المراجعة', 'active': 'قيد العلاج', 'completed': 'مكتملة', 'rejected': 'مرفوضة'}


class DentalLoginForm(AdminAuthenticationForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['username'].label = 'البريد الإلكتروني'
        self.fields['username'].widget.attrs.update({'type': 'email', 'dir': 'ltr', 'placeholder': 'name@example.com', 'autocomplete': 'username'})
        self.fields['password'].label = 'كلمة المرور'
        self.fields['password'].widget.attrs.update({'placeholder': 'أدخل كلمة المرور', 'autocomplete': 'current-password'})


class DentalAdminSite(AdminSite):
    site_header = 'DentalHealth'
    site_title = 'إدارة العيادة'
    index_title = 'نظرة عامة'
    index_template = 'admin/dental_index.html'
    app_index_template = 'admin/dental_app_index.html'
    login_template = 'admin/dental_login.html'
    login_form = DentalLoginForm

    def get_app_list(self, request, app_label=None):
        apps = super().get_app_list(request, app_label)
        rank = {'case': 0, 'patientprofile': 1, 'doctorprofile': 2, 'studentprofile': 3, 'user': 4, 'specialty': 5}
        for app in apps:
            if app['app_label'] == 'accounts':
                app['name'] = 'إدارة العيادة'
            elif app['app_label'] == 'auth':
                app['name'] = 'الصلاحيات'
            elif app['app_label'] == 'token_blacklist':
                app['name'] = 'أمان الحسابات'
            for model in app['models']:
                key = model['object_name'].lower()
                model['name'], model['icon'] = MODEL_LABELS.get(key, (model['name'], 'grid'))
            app['models'].sort(key=lambda model: rank.get(model['object_name'].lower(), 20))
        return sorted(apps, key=lambda app: 0 if app['app_label'] == 'accounts' else 1)

    def each_context(self, request):
        context = super().each_context(request)
        context['dental_today'] = timezone.localdate()
        return context

    def may_view(self, request, model):
        admin = self._registry.get(model)
        return bool(admin and admin.has_view_or_change_permission(request))

    def index(self, request, extra_context=None):
        context = dict(extra_context or {})
        stats = []
        if self.may_view(request, PatientProfile):
            stats.append({'label': 'إجمالي المرضى', 'value': PatientProfile.objects.count(), 'icon': 'patient', 'tone': 'teal', 'url': reverse('admin:accounts_patientprofile_changelist'), 'hint': 'ملفات المرضى المسجلين'})
        if self.may_view(request, DoctorProfile):
            stats.append({'label': 'الأطباء المعتمدون', 'value': DoctorProfile.objects.filter(user__clinical_access_approved=True, user__is_active=True).count(), 'icon': 'doctor', 'tone': 'blue', 'url': reverse('admin:accounts_doctorprofile_changelist') + '?user__clinical_access_approved=1&user__is_active=1', 'hint': 'فريق الرعاية المعتمد'})
        if self.may_view(request, Case):
            counts = {row['status']: row['total'] for row in Case.objects.values('status').annotate(total=Count('pk'))}
            for status, label, icon, tone, hint in [('active', 'الحالات النشطة', 'case', 'violet', 'حالات قيد العلاج'), ('pending', 'بانتظار المراجعة', 'clock', 'amber', 'حالات تحتاج إلى متابعة')]:
                stats.append({'label': label, 'value': counts.get(status, 0), 'icon': icon, 'tone': tone, 'url': reverse('admin:accounts_case_changelist') + '?status__exact=' + status, 'hint': hint})
            today = timezone.localdate()
            first_day = today - timedelta(days=6)
            activity = {row['day']: row['total'] for row in Case.objects.filter(created_at__date__gte=first_day, created_at__date__lte=today).annotate(day=TruncDate('created_at')).values('day').annotate(total=Count('pk'))}
            maximum = max(activity.values(), default=0)
            week = [{'day': first_day + timedelta(days=i), 'count': activity.get(first_day + timedelta(days=i), 0)} for i in range(7)]
            for day in week:
                day['height'] = round(day['count'] / maximum * 100) if maximum else 0
            recent = list(Case.objects.select_related('patient').order_by('-created_at', '-pk')[:6])
            for case in recent:
                case.dashboard_status = STATUS_LABELS[case.status]
            context.update(can_view_cases=True, recent_cases=recent, weekly_cases=week, weekly_total=sum(d['count'] for d in week),
                           status_summary=[{'label': STATUS_LABELS[key], 'value': counts.get(key, 0), 'key': key} for key in STATUS_LABELS],
                           case_list_url=reverse('admin:accounts_case_changelist'))
        if self.may_view(request, User):
            doctors = User.objects.filter(user_type='doctor', clinical_access_approved=False, is_active=True).order_by('-date_joined')
            context.update(can_view_users=True, pending_doctors=list(doctors[:4]), pending_doctor_count=doctors.count(),
                           doctor_review_url=reverse('admin:accounts_user_changelist') + '?' + urlencode({'user_type__exact': 'doctor', 'clinical_access_approved__exact': '0', 'is_active__exact': '1'}))
        context['dashboard_stats'] = stats
        context['title'] = 'نظرة عامة'
        return super().index(request, extra_context=context)
