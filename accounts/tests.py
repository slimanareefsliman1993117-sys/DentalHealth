"""API and permission regression tests using only Django's isolated test database."""
from datetime import date, timedelta
from io import BytesIO
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from PIL import Image
from django.core.cache import cache
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
from rest_framework.test import APITestCase
from rest_framework_simplejwt.tokens import RefreshToken
from .models import User, PatientProfile, StudentProfile, DoctorProfile, Case


class APITests(APITestCase):
    password = 'Dental-Validation-Password-934!'

    @classmethod
    def setUpTestData(cls):
        cls.patient = cls.create_user('patient')
        cls.other = cls.create_user('patient', 'other')
        cls.student = cls.create_user('student')
        cls.doctor = cls.create_user('doctor')
        cls.approved = cls.create_user('doctor', 'approved', approved=True)
        cls.case = Case.objects.create(patient=cls.patient, description='Synthetic case', title='Case one')
        cls.other_case = Case.objects.create(patient=cls.other, description='Other synthetic case', title='Case two')

    @classmethod
    def create_user(cls, role, name=None, approved=False):
        name = name or role
        user = User.objects.create_user(username=name, email=name+'@example.test', password=cls.password,
                                        user_type=role, clinical_access_approved=approved)
        model = {'patient': PatientProfile, 'student': StudentProfile, 'doctor': DoctorProfile}[role]
        kwargs = {} if role == 'patient' else {'specialty': 'dentistry'}
        model.objects.create(user=user, **kwargs)
        return user

    def setUp(self):
        cache.clear()
        self.upload_dir = TemporaryDirectory()
        self.addCleanup(self.upload_dir.cleanup)
        self.media_override = override_settings(MEDIA_ROOT=self.upload_dir.name)
        self.media_override.enable()
        self.addCleanup(self.media_override.disable)

    def auth(self, user):
        token = RefreshToken.for_user(user)
        self.client.credentials(HTTP_AUTHORIZATION='Bearer '+str(token.access_token))
        return token

    def registration(self, role='patient', **overrides):
        data = {'email': role+'-new@example.test', 'fullname': 'New Person', 'phone': '12345678',
                'password': self.password, 'user_type': role}
        data.update(overrides)
        return self.client.post('/api/register/', data, format='json')

    def image(self, name='image.png'):
        stream = BytesIO()
        Image.new('RGB', (16, 16), 'white').save(stream, format='PNG')
        return SimpleUploadedFile(name, stream.getvalue(), content_type='image/png')

    def test_home_and_admin_render(self):
        self.assertContains(self.client.get('/'), 'DentalHealth API')
        self.assertEqual(self.client.get('/admin/login/').status_code, 200)

    def test_anonymous_private_endpoints_denied(self):
        for url in ['/api/profile/', '/api/cases/', '/media/cases/photos/unknown.png']:
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).status_code, 401)

    def test_register_each_role_and_correct_profile(self):
        for role, model in [('patient',PatientProfile),('student',StudentProfile),('doctor',DoctorProfile)]:
            with self.subTest(role=role):
                response = self.registration(role)
                self.assertEqual(response.status_code,201,response.data)
                user = User.objects.get(email=role+'-new@example.test')
                self.assertTrue(model.objects.filter(user=user).exists())
                self.assertFalse(user.clinical_access_approved)
                self.assertNotIn('password',response.data['user'])
                self.assertIn('access',response.data)

    def test_registration_rejects_duplicate_case_insensitive_email(self):
        response=self.registration(email='PATIENT@EXAMPLE.TEST')
        self.assertEqual(response.status_code,400)
        self.assertIn('already in use',str(response.data))

    def test_registration_rejects_weak_password(self):
        self.assertEqual(self.registration(password='123').status_code,400)

    def test_registration_cannot_set_privileges(self):
        self.assertEqual(self.registration('doctor',clinical_access_approved=True,is_staff=True,is_superuser=True).status_code,201)
        user=User.objects.get(email='doctor-new@example.test')
        self.assertFalse(user.is_staff or user.is_superuser or user.clinical_access_approved)

    def test_profile_creation_failure_rolls_back_user(self):
        with patch('accounts.serializers.PatientProfile.objects.create',side_effect=RuntimeError('synthetic failure')):
            with self.assertRaises(RuntimeError):
                self.registration()
        self.assertFalse(User.objects.filter(email='patient-new@example.test').exists())

    def test_both_login_urls_use_email_case_insensitively(self):
        for url in ['/api/login/','/api/token/']:
            response=self.client.post(url,{'email':'PATIENT@EXAMPLE.TEST','password':self.password},format='json')
            self.assertEqual(response.status_code,200,response.data)
            self.assertIn('access',response.data)

    def test_password_whitespace_is_preserved(self):
        password='  Dental-Whitespace-Password-993!  '
        self.assertEqual(self.registration(password=password).status_code,201)
        for url in ['/api/login/','/api/token/']:
            response=self.client.post(url,{'email':'patient-new@example.test','password':password},format='json')
            self.assertEqual(response.status_code,200,response.data)

    def test_inactive_user_cannot_login(self):
        self.patient.is_active=False;self.patient.save()
        for url in ['/api/login/','/api/token/']:
            self.assertIn(self.client.post(url,{'email':self.patient.email,'password':self.password},format='json').status_code,[400,401])

    def test_refresh_rotates_and_blacklists_old_token(self):
        token=str(RefreshToken.for_user(self.patient))
        response=self.client.post('/api/token/refresh/',{'refresh':token},format='json')
        self.assertEqual(response.status_code,200,response.data)
        self.assertIn('refresh',response.data)
        self.assertEqual(self.client.post('/api/token/refresh/',{'refresh':token},format='json').status_code,401)

    def test_logout_rejects_another_users_token(self):
        other=str(RefreshToken.for_user(self.other))
        self.auth(self.patient)
        self.assertEqual(self.client.post('/api/logout/',{'refresh':other},format='json').status_code,400)
        self.client.credentials()
        self.assertEqual(self.client.post('/api/token/refresh/',{'refresh':other},format='json').status_code,200)

    def test_logout_blacklists_own_token(self):
        token=self.auth(self.patient)
        self.assertEqual(self.client.post('/api/logout/',{'refresh':str(token)},format='json').status_code,205)
        self.assertEqual(self.client.post('/api/token/refresh/',{'refresh':str(token)},format='json').status_code,401)

    def test_invalid_logout_token_is_generic(self):
        self.auth(self.patient)
        response=self.client.post('/api/logout/',{'refresh':'bad-token'},format='json')
        self.assertEqual(response.status_code,400)
        self.assertNotIn('Not enough segments',str(response.data))

    def test_password_change_revokes_access(self):
        self.auth(self.patient)
        self.patient.set_password('Another-Password-119!');self.patient.save()
        self.assertEqual(self.client.get('/api/profile/').status_code,401)

    def test_all_profile_types_update_correct_model(self):
        for user in [self.patient,self.student,self.doctor]:
            self.auth(user)
            data={'phone':'998877'}
            if user.user_type!='patient':data['specialty']='orthodontics'
            response=self.client.put('/api/profile/',data,format='json')
            self.assertEqual(response.status_code,200,response.data)
            self.assertEqual(response.data['phone'],'998877')
            if user.user_type!='patient':self.assertEqual(response.data['specialty'],'orthodontics')

    def test_profile_patch_supported(self):
        self.auth(self.patient)
        self.assertEqual(self.client.patch('/api/profile/',{'phone':'87654'},format='json').status_code,200)

    def test_profile_owner_and_computed_age_cannot_be_overwritten(self):
        self.auth(self.patient)
        response=self.client.put('/api/profile/',{'user':self.other.pk,'age':999,'birthdate':'2000-01-01'},format='json')
        self.assertEqual(response.status_code,200,response.data)
        self.assertEqual(response.data['user']['id'],self.patient.pk)
        self.assertNotEqual(response.data['age'],999)

    def test_future_birthdate_rejected(self):
        self.auth(self.patient)
        self.assertEqual(self.client.patch('/api/profile/',{'birthdate':str(date.today()+timedelta(days=1))},format='json').status_code,400)

    def test_clearing_birthdate_clears_age(self):
        self.auth(self.patient)
        self.client.patch('/api/profile/',{'birthdate':'2000-01-01'},format='json')
        response=self.client.patch('/api/profile/',{'birthdate':None},format='json')
        self.assertIsNone(response.data['age'])

    def test_missing_profile_returns_404(self):
        self.patient.patient_profile.delete();self.auth(self.patient)
        self.assertEqual(self.client.get('/api/profile/').status_code,404)

    def test_patient_case_creation_protects_clinical_fields(self):
        self.auth(self.patient)
        response=self.client.post('/api/cases/create/',{'description':'Synthetic symptoms','patient':self.other.pk,'status':'completed','physician_notes':'forged'},format='json')
        self.assertEqual(response.status_code,201,response.data)
        self.assertEqual(response.data['patient'],self.patient.pk)
        self.assertEqual(response.data['status'],'pending')
        self.assertFalse(response.data['physician_notes'])

    def test_only_patients_create_cases(self):
        for user in [self.student,self.doctor,self.approved]:
            self.auth(user)
            self.assertEqual(self.client.post('/api/cases/create/',{'description':'test'},format='json').status_code,403)

    def test_patient_sees_only_own_cases(self):
        self.auth(self.patient)
        response=self.client.get('/api/cases/')
        self.assertEqual([c['id'] for c in response.data['results']],[self.case.pk])

    def test_unapproved_clinicians_cannot_read_cases(self):
        for user in [self.student,self.doctor]:
            self.auth(user)
            self.assertEqual(self.client.get('/api/cases/').status_code,403)

    def test_approved_doctor_can_list_cases(self):
        self.auth(self.approved)
        self.assertEqual(self.client.get('/api/cases/').data['count'],2)

    def test_only_approved_doctor_can_update_status(self):
        url=f'/api/cases/{self.case.pk}/status/'
        for user in [self.patient,self.student,self.doctor]:
            self.auth(user)
            self.assertEqual(self.client.patch(url,{'status':'active'},format='json').status_code,403)
        self.auth(self.approved)
        self.assertEqual(self.client.patch(url,{'status':'active'},format='json').status_code,200)
        self.case.refresh_from_db();self.assertEqual(self.case.status,'active')

    def test_status_validation_and_missing_case(self):
        self.auth(self.approved)
        url=f'/api/cases/{self.case.pk}/status/'
        self.assertEqual(self.client.patch(url,{'status':'invented'},format='json').status_code,400)
        self.assertEqual(self.client.patch(url,{},format='json').status_code,400)
        self.assertEqual(self.client.patch('/api/cases/999999/status/',{'status':'active'},format='json').status_code,404)

    def test_case_status_filter(self):
        self.auth(self.patient)
        self.assertEqual(self.client.get('/api/cases/?status=completed').data['count'],0)
        self.assertEqual(self.client.get('/api/cases/?status=unknown').status_code,400)

    def test_medical_image_requires_owner_or_approved_doctor(self):
        self.auth(self.patient)
        response=self.client.post('/api/cases/create/',{'description':'Synthetic case','photos':self.image()},format='multipart')
        self.assertEqual(response.status_code,201,response.data)
        url='/media/'+Case.objects.get(pk=response.data['id']).photos.name
        self.client.credentials();self.assertEqual(self.client.get(url).status_code,401)
        for user,code in [(self.patient,200),(self.other,404),(self.student,404),(self.doctor,404),(self.approved,200)]:
            self.auth(user)
            result=self.client.get(url);self.assertEqual(result.status_code,code)
            if code==200:
                self.assertEqual(result['Cache-Control'],'private, no-store');result.close()

    def test_profile_image_is_private(self):
        self.auth(self.patient)
        response=self.client.patch('/api/profile/',{'profile_image':self.image()},format='multipart')
        self.assertEqual(response.status_code,200,response.data)
        self.patient.patient_profile.refresh_from_db()
        url='/media/'+self.patient.patient_profile.profile_image.name
        self.auth(self.other);self.assertEqual(self.client.get(url).status_code,404)
        self.auth(self.patient);response=self.client.get(url);self.assertEqual(response.status_code,200);response.close()

    def test_non_image_upload_rejected(self):
        self.auth(self.patient)
        bad=SimpleUploadedFile('bad.png',b'<script>bad</script>',content_type='image/png')
        self.assertEqual(self.client.patch('/api/profile/',{'profile_image':bad},format='multipart').status_code,400)

    def test_delete_account_cascades(self):
        token=self.auth(self.patient)
        response=self.client.delete('/api/account/delete/')
        self.assertEqual(response.status_code,204)
        self.assertFalse(User.objects.filter(pk=self.patient.pk).exists())
        self.assertFalse(Case.objects.filter(pk=self.case.pk).exists())
        self.client.credentials()
        self.assertEqual(self.client.post('/api/token/refresh/',{'refresh':str(token)},format='json').status_code,401)

    def test_auth_rate_limit(self):
        for _ in range(10):
            self.client.post('/api/login/',{'email':'absent@example.test','password':'invalid'},format='json')
        self.assertEqual(self.client.post('/api/login/',{'email':'absent@example.test','password':'invalid'},format='json').status_code,429)

    def test_password_change_revokes_refresh(self):
        refresh=str(RefreshToken.for_user(self.patient))
        self.patient.set_password('Changed-Dental-Password-994!');self.patient.save()
        response=self.client.post('/api/token/refresh/',{'refresh':refresh},format='json')
        self.assertEqual(response.status_code,401)

    def test_deleted_medical_files_removed_after_commit(self):
        self.auth(self.patient)
        response=self.client.post('/api/cases/create/',{'description':'Synthetic','photos':self.image()},format='multipart')
        case=Case.objects.get(pk=response.data['id']);file_path=Path(case.photos.path)
        self.assertTrue(file_path.exists())
        with self.captureOnCommitCallbacks(execute=True):
            self.client.delete('/api/account/delete/')
        self.assertFalse(file_path.exists())

    def test_superuser_session_can_view_medical_upload(self):
        self.auth(self.patient)
        response=self.client.post('/api/cases/create/',{'description':'Synthetic','photos':self.image()},format='multipart')
        case=Case.objects.get(pk=response.data['id'])
        admin=User.objects.create_superuser(username='admin',email='admin@example.test',password=self.password)
        self.client.credentials();self.client.force_login(admin)
        response=self.client.get('/media/'+case.photos.name)
        self.assertEqual(response.status_code,200);response.close()
