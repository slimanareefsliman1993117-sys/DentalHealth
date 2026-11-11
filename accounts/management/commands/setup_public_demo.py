"""Prepare a public view-only account and seed only the separate preview database."""
from datetime import timedelta
from django.conf import settings
from django.contrib.auth.models import Permission
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone
from accounts.demo import DEMO_MODELS
from accounts.models import User, PatientProfile, DoctorProfile, StudentProfile, Specialty, Case


class Command(BaseCommand):
    help = __doc__

    def handle(self, *args, **options):
        if not settings.PUBLIC_DEMO_PASSWORD:
            raise CommandError('Set PUBLIC_DEMO_PASSWORD privately before preparing the public preview.')
        account = User.objects.filter(email__iexact=settings.PUBLIC_DEMO_EMAIL).first()
        if account and (account.is_superuser or account.username != 'public-demo'):
            raise CommandError('An existing non-demo account uses this address; it was not changed.')
        if User.objects.exclude(pk=account.pk if account else None).filter(username='public-demo').exists():
            raise CommandError('The preview username is already used; no account was changed.')
        if not User.objects.using('demo').exists():
            with transaction.atomic(using='demo'):
                patients = []
                names = ['ليان', 'عمر', 'نور', 'ليلى', 'أحمد', 'ريم', 'سامر', 'رنا']
                for i, name in enumerate(names):
                    user = User.objects.using('demo').create(username=f'preview-patient-{i}', email=f'preview-patient-{i}@example.test',
                        password='!', first_name=name, last_name='للمعاينة', user_type='patient')
                    PatientProfile.objects.using('demo').create(user=user, phone=f'00000000{i}',
                        chronic_diseases='بيانات تجريبية فقط؛ لا تمثل شخصاً حقيقياً.')
                    patients.append(user)
                for i, name in enumerate(['د. يارا', 'د. لؤي', 'د. ندى']):
                    user = User.objects.using('demo').create(username=f'preview-doctor-{i}', email=f'preview-doctor-{i}@example.test',
                        password='!', first_name=name, last_name='للمعاينة', user_type='doctor', clinical_access_approved=True)
                    DoctorProfile.objects.using('demo').create(user=user, specialty='orthodontics' if i else 'dentistry')
                for i, name in enumerate(['هبة', 'يوسف', 'سارة', 'مازن']):
                    user = User.objects.using('demo').create(username=f'preview-student-{i}', email=f'preview-student-{i}@example.test',
                        password='!', first_name=name, last_name='للمعاينة', user_type='student')
                    StudentProfile.objects.using('demo').create(user=user, specialty='dentistry', years_of_teaching=i + 1)
                for name in ['طب الأسنان العام', 'تقويم الأسنان', 'جراحة الفم']:
                    Specialty.objects.using('demo').create(name=name)
                titles = ['فحص دوري للأسنان', 'مراجعة ألم الأسنان', 'متابعة حساسية الأسنان', 'تقييم اللثة']
                now = timezone.now()
                for i in range(18):
                    case = Case.objects.using('demo').create(patient=patients[i % len(patients)], title=titles[i % len(titles)],
                        description='حالة تجريبية للعرض فقط؛ لا تمثل بيانات مريض حقيقي.',
                        status=['pending', 'active', 'completed', 'pending', 'active', 'rejected'][i % 6],
                        pain_type='intermittent', pain_location='right', pain_duration='1-3_days')
                    Case.objects.using('demo').filter(pk=case.pk).update(created_at=now - timedelta(days=i % 7))
        with transaction.atomic():
            if account is None:
                account = User(username='public-demo', email=settings.PUBLIC_DEMO_EMAIL)
            account.first_name, account.last_name = 'زائر', 'المعاينة'
            account.is_active, account.is_staff, account.is_superuser = True, True, False
            account.user_type, account.clinical_access_approved = 'student', False
            account.set_password(settings.PUBLIC_DEMO_PASSWORD)
            account.save()
            account.groups.clear()
            account.user_permissions.set(Permission.objects.filter(content_type__app_label='accounts',
                codename__in=['view_' + model for model in DEMO_MODELS]))
        self.stdout.write(self.style.SUCCESS('Public preview prepared: separate synthetic database and view-only permissions. No password printed.'))
