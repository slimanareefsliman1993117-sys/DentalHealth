"""Public preview isolation, immutable access and login presentation regressions."""
from io import StringIO
from django.contrib import admin
from django.contrib.auth.models import Permission
from django.core.cache import cache
from django.core.management import call_command, CommandError
from django.test import TestCase, RequestFactory, override_settings
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken
from accounts.models import User, PatientProfile, DoctorProfile, StudentProfile, Case


@override_settings(PUBLIC_DEMO_ENABLED=True, PUBLIC_DEMO_EMAIL='demo@dentalhealth.example', PUBLIC_DEMO_PASSWORD='Preview-Password-294!')
class PublicDemoTests(TestCase):
    databases = {'default', 'demo'}

    @classmethod
    def setUpTestData(cls):
        cls.owner = User.objects.create_superuser(username='private-owner', email='private-owner@example.test', password='Private-Owner-Password-932!')
        cls.real = User.objects.create_user(username='real-person', email='private-patient@example.test')
        PatientProfile.objects.create(user=cls.real)
        cls.real_case = Case.objects.create(patient=cls.real, title='PRIVATE MEDICAL RECORD', description='Private clinical details')
        cls.demo = User.objects.create_user(username='public-demo', email='demo@dentalhealth.example',
            password='Preview-Password-294!', is_staff=True, user_type='student')
        cls.demo.user_permissions.set(Permission.objects.filter(codename__in=[
            'view_case', 'view_patientprofile', 'view_doctorprofile', 'view_studentprofile', 'view_specialty']))
        patient = User.objects.using('demo').create(username='synthetic-patient', email='synthetic@example.test', password='!', first_name='ليان', last_name='للمعاينة')
        PatientProfile.objects.using('demo').create(user=patient)
        cls.preview_case = Case.objects.using('demo').create(pk=cls.real_case.pk, patient=patient,
            title='SYNTHETIC PREVIEW RECORD', description='Synthetic isolated preview')

    def setUp(self):
        cache.clear()

    def test_public_panel_displays_only_demo_credentials_and_is_not_cached(self):
        response = self.client.get('/admin/login/')
        self.assertContains(response, 'demo@dentalhealth.example')
        self.assertContains(response, 'Preview-Password-294!')
        self.assertNotContains(response, self.owner.email)
        self.assertNotContains(response, 'Private-Owner-Password-932!')
        self.assertIn('no-store', response['Cache-Control'])

    def test_disabled_preview_hides_credentials_and_rejects_login(self):
        with override_settings(PUBLIC_DEMO_ENABLED=False):
            response = self.client.get('/admin/login/')
            self.assertNotContains(response, 'Preview-Password-294!')
            response = self.client.post('/admin/login/', {'username': self.demo.email, 'password': 'Preview-Password-294!'})
            self.assertEqual(response.status_code, 200)
            self.assertNotIn('_auth_user_id', self.client.session)

    def test_demo_can_sign_in_to_admin_and_sign_out(self):
        response = self.client.post('/admin/login/', {'username': self.demo.email, 'password': 'Preview-Password-294!', 'next': '/admin/'})
        self.assertEqual(response.status_code, 302)
        self.assertEqual(self.client.get('/admin/').status_code, 200)
        self.assertEqual(self.client.post('/admin/logout/').status_code, 200)

    def test_dashboard_reads_only_the_separate_database(self):
        self.client.force_login(self.demo)
        response = self.client.get('/admin/')
        self.assertContains(response, 'SYNTHETIC PREVIEW RECORD')
        self.assertNotContains(response, 'PRIVATE MEDICAL RECORD')
        self.assertNotContains(response, self.real.email)
        self.assertContains(response, 'بيانات تجريبية منفصلة')
        self.assertNotContains(response, '/admin/accounts/user/')
        self.assertEqual(response.context['weekly_total'], 1)

    def test_list_and_detail_are_isolated_even_when_real_and_demo_ids_collide(self):
        self.client.force_login(self.demo)
        for path in ['/admin/accounts/case/', f'/admin/accounts/case/{self.real_case.pk}/change/']:
            response = self.client.get(path)
            self.assertEqual(response.status_code, 200)
            self.assertContains(response, 'SYNTHETIC PREVIEW RECORD')
            self.assertNotContains(response, 'PRIVATE MEDICAL RECORD')
            self.assertNotContains(response, 'name="_save"')
            self.assertNotContains(response, 'class="deletelink"')
        response = self.client.get('/admin/accounts/patientprofile/')
        self.assertContains(response, 'synthetic@example.test')
        self.assertNotContains(response, self.real.email)

    def test_real_administrator_still_sees_only_real_clinical_records(self):
        self.client.force_login(self.owner)
        for path in ['/admin/', '/admin/accounts/case/']:
            response = self.client.get(path)
            self.assertContains(response, 'PRIVATE MEDICAL RECORD')
            self.assertNotContains(response, 'SYNTHETIC PREVIEW RECORD')

    def test_mutation_posts_and_sensitive_admin_routes_are_blocked(self):
        self.client.force_login(self.demo)
        for path in ['/admin/password_change/', '/admin/accounts/user/', '/admin/auth/group/',
                     '/admin/token_blacklist/outstandingtoken/', f'/admin/accounts/case/{self.real_case.pk}/history/']:
            self.assertEqual(self.client.get(path).status_code, 403, path)
        for path in [f'/admin/accounts/case/{self.real_case.pk}/change/', '/admin/accounts/case/',
                     '/admin/password_change/', '/api/account/delete/', '/api/cases/create/']:
            self.assertEqual(self.client.post(path, {'action': 'delete_selected', 'status': 'completed'}).status_code, 403, path)
        self.real_case.refresh_from_db()
        self.assertEqual(self.real_case.status, 'pending')
        self.assertEqual(Case.objects.using('demo').get(pk=self.preview_case.pk).status, 'pending')
        self.assertTrue(User.objects.filter(pk=self.demo.pk).exists())

    def test_add_change_and_delete_are_denied_even_if_permissions_are_misassigned(self):
        self.demo.user_permissions.add(*Permission.objects.filter(content_type__app_label='accounts'))
        self.client.force_login(self.demo)
        request = RequestFactory().get('/admin/')
        request.user = User.objects.get(pk=self.demo.pk)
        model_admin = admin.site._registry[Case]
        self.assertFalse(model_admin.has_add_permission(request))
        self.assertFalse(model_admin.has_change_permission(request, self.preview_case))
        self.assertFalse(model_admin.has_delete_permission(request, self.preview_case))
        self.assertEqual(self.client.get('/admin/accounts/user/').status_code, 403)

    def test_demo_cannot_obtain_or_use_api_tokens(self):
        client = APIClient()
        for path in ['/api/login/', '/api/token/']:
            self.assertIn(client.post(path, {'email': self.demo.email, 'password': 'Preview-Password-294!'}, format='json').status_code, {400, 401})
        token = RefreshToken.for_user(self.demo)
        client.credentials(HTTP_AUTHORIZATION='Bearer ' + str(token.access_token))
        self.assertEqual(client.get('/api/profile/').status_code, 401)
        self.assertEqual(client.delete('/api/account/delete/').status_code, 401)
        client.credentials()
        self.assertEqual(client.post('/api/token/refresh/', {'refresh': str(token)}, format='json').status_code, 401)

    def test_demo_session_cannot_read_real_media(self):
        self.client.force_login(self.demo)
        self.assertEqual(self.client.get('/media/profiles/patients/anything.png').status_code, 404)

    def test_reserved_email_cannot_be_registered(self):
        response = self.client.post('/api/register/', {'email': 'DEMO@DENTALHEALTH.EXAMPLE', 'fullname': 'Reserved',
            'phone': '123', 'password': 'Other-Registration-Password-942!', 'user_type': 'patient'}, content_type='application/json')
        self.assertEqual(response.status_code, 400)

    def test_setup_creates_only_synthetic_clinical_data_in_demo_database(self):
        Case.objects.using('demo').all().delete()
        User.objects.using('demo').all().delete()
        initial = (User.objects.count(), PatientProfile.objects.count(), Case.objects.count())
        call_command('setup_public_demo', stdout=StringIO())
        self.assertEqual((User.objects.count(), PatientProfile.objects.count(), Case.objects.count()), initial)
        self.assertEqual(Case.objects.using('demo').count(), 18)
        self.assertEqual(PatientProfile.objects.using('demo').count(), 8)
        self.assertEqual(DoctorProfile.objects.using('demo').count(), 3)
        self.assertEqual(StudentProfile.objects.using('demo').count(), 4)
        self.demo.refresh_from_db()
        self.assertFalse(self.demo.is_superuser)
        self.assertFalse(self.demo.user_permissions.exclude(codename__startswith='view_').exists())
        call_command('setup_public_demo', stdout=StringIO())
        self.assertEqual(Case.objects.using('demo').count(), 18)

    def test_setup_refuses_to_repurpose_a_real_administrator(self):
        with override_settings(PUBLIC_DEMO_EMAIL=self.owner.email), self.assertRaises(CommandError):
            call_command('setup_public_demo', stdout=StringIO())
        self.owner.refresh_from_db()
        self.assertTrue(self.owner.is_superuser)
