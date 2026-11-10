"""Create synthetic data only in a separate private, local preview database."""
import json,os,secrets,sys
from pathlib import Path
from datetime import timedelta, date
root=Path(__file__).resolve().parent.parent
sys.path.insert(0,str(root))
folder=root/'.local'
folder.mkdir(mode=0o700,exist_ok=True)
folder.chmod(0o700)
database=folder/'admin-preview.sqlite3'
if database.exists():
    raise SystemExit('Preview database already exists; not overwritten.')
os.environ.update(DJANGO_SETTINGS_MODULE='dentalhealth.settings',DEBUG='True',DB_ENGINE='sqlite',SQLITE_PATH=str(database),SECRET_KEY='preview-only-'+secrets.token_urlsafe(48))
import django
django.setup()
from django.core.management import call_command
from django.utils import timezone
from accounts.models import User,PatientProfile,DoctorProfile,StudentProfile,Case,Specialty
call_command('migrate',verbosity=0,interactive=False)
password=secrets.token_urlsafe(24)
admin=User.objects.create_superuser(username='preview-admin',email='preview-admin@example.test',password=password,first_name='المسؤول',last_name='للمعاينة')
first=['ليان','عمر','نور','ليلى','أحمد','ريم','سامر','رنا','يوسف','هبة','مازن','سارة']
last=['أحمد','خليل','حسن','علي','مراد','صالح','يوسف','عمر','سليم','نور']
patients=[]
for i in range(42):
    user=User.objects.create(username=f'preview-patient-{i}',email=f'patient-{i}@example.test',password='!',user_type='patient',first_name=first[i%len(first)],last_name=last[i%len(last)])
    PatientProfile.objects.create(user=user,phone=f'000000{i:04}',birthdate=date(1995,5,15),gender='female' if i%2 else 'male',chronic_diseases='بيانات تجريبية للمعاينة فقط')
    patients.append(user)
for i in range(7):
    user=User.objects.create(username=f'preview-doctor-{i}',email=f'doctor-{i}@example.test',password='!',user_type='doctor',first_name=['د. يارا','د. لؤي','د. ندى','د. كريم','د. سارة','د. رامي','د. لينا'][i],last_name='للمعاينة',clinical_access_approved=i<4)
    DoctorProfile.objects.create(user=user,specialty='dentistry' if i%2 else 'orthodontics',phone='0000000000')
for i in range(8):
    user=User.objects.create(username=f'preview-student-{i}',email=f'student-{i}@example.test',password='!',user_type='student',first_name=first[i],last_name='للمعاينة')
    StudentProfile.objects.create(user=user,specialty='dentistry',years_of_teaching=(i%5)+1)
for name in ['طب الأسنان العام','تقويم الأسنان','جراحة الفم','طب أسنان الأطفال']:
    Specialty.objects.create(name=name)
now=timezone.now()
titles=['مراجعة ألم الأسنان','فحص دوري للأسنان','متابعة حساسية الأسنان','مراجعة اللثة','تقييم ألم الفك','متابعة العلاج']
statuses=['pending','active','completed','pending','active','completed','pending','rejected']
for i in range(26):
    case=Case.objects.create(patient=patients[i%len(patients)],title=titles[i%len(titles)],description='حالة تجريبية مخصصة لمعاينة تصميم لوحة التحكم؛ لا تمثل بيانات مريض حقيقي.',status=statuses[i%len(statuses)],pain_type='intermittent',pain_location='right',pain_duration='1-3_days')
    Case.objects.filter(pk=case.pk).update(created_at=now-timedelta(days=i%7,hours=i%3),updated_at=now-timedelta(hours=i%12))
credentials=folder/'admin-preview.json'
credentials.write_text(json.dumps({'email':admin.email,'password':password,'url':'http://127.0.0.1:8021/admin/','note':'Synthetic local preview only; not deployed.'},indent=2)+'\n')
credentials.chmod(0o600)
database.chmod(0o600)
print('Synthetic preview database and private credentials created. No real database was changed. No credentials printed.')
