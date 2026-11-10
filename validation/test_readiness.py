"""Release regressions: boundary inputs, permissions, uploads and administration."""
from datetime import date, timedelta
from io import BytesIO
from pathlib import Path
from tempfile import TemporaryDirectory

from PIL import Image
from django.contrib import admin
from django.contrib.auth.models import Permission
from django.core.cache import cache
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import IntegrityError, transaction
from django.test import TestCase, RequestFactory, override_settings
from django.urls import reverse
from rest_framework.test import APITestCase, APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from accounts import tests as api_helpers
from accounts.models import User, PatientProfile, StudentProfile, DoctorProfile, Case, Specialty


def image_upload(fmt='PNG', size=(16, 16), padding=0):
    stream = BytesIO()
    Image.new('RGB', size, 'white').save(stream, format=fmt)
    extension = {'JPEG': 'jpg', 'PNG': 'png', 'GIF': 'gif', 'WEBP': 'webp'}[fmt]
    return SimpleUploadedFile('synthetic.' + extension, stream.getvalue() + b'\0' * padding,
                              content_type='image/' + extension)


class ReleaseAPITests(APITestCase):
    password = api_helpers.APITests.password
    create_user = api_helpers.APITests.__dict__['create_user']
    auth = api_helpers.APITests.auth
    registration = api_helpers.APITests.registration

    @classmethod
    def setUpTestData(cls):
        api_helpers.APITests.setUpTestData.__func__(cls)

    def setUp(self):
        api_helpers.APITests.setUp(self)

    def test_registration_invalid_inputs_create_no_accounts(self):
        invalid = [dict(email='invalid'), dict(fullname='   '), dict(fullname='x' * 151),
                   dict(phone='1' * 16), dict(user_type='admin'), dict(password=''),
                   dict(email='x' * 151 + '@example.test')]
        before = User.objects.count()
        for values in invalid:
            cache.clear()
            response = self.registration(**values)
            self.assertEqual(response.status_code, 400, values)
            self.assertIsInstance(response.data['errors'], list)
        self.assertEqual(User.objects.count(), before)

    def test_arabic_single_name_registration_and_profile(self):
        response = self.registration(fullname='ليان')
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data['user']['first_name'], 'ليان')
        self.assertEqual(response.data['user']['last_name'], '')
        self.client.credentials(HTTP_AUTHORIZATION='Bearer ' + response.data['access'])
        self.assertEqual(self.client.get('/api/profile/').status_code, 200)

    def test_database_prevents_case_insensitive_duplicate_email(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            User.objects.create_user(username='duplicate', email=self.patient.email.upper())

    def test_error_responses_preserve_authentication_and_retry_headers(self):
        response = self.client.get('/api/profile/')
        self.assertEqual(response.status_code, 401)
        self.assertIn('Bearer', response.get('WWW-Authenticate', ''))
        for _ in range(10):
            self.client.post('/api/login/', {'email': 'missing@example.test', 'password': 'wrong'}, format='json')
        response = self.client.post('/api/login/', {'email': 'missing@example.test', 'password': 'wrong'}, format='json')
        self.assertEqual(response.status_code, 429)
        self.assertGreater(int(response.get('Retry-After', '0')), 0)

    def test_malformed_payload_and_wrong_method_are_client_errors(self):
        self.assertEqual(self.client.post('/api/register/', data='{', content_type='application/json').status_code, 400)
        self.assertEqual(self.client.get('/api/register/').status_code, 405)
        self.assertEqual(self.client.post('/api/login/', data='text', content_type='text/plain').status_code, 415)
        self.auth(self.patient)
        self.assertEqual(self.client.post('/api/cases/create/', {}, format='json').status_code, 400)

    def test_tampered_and_expired_tokens_rejected(self):
        token = RefreshToken.for_user(self.patient)
        expired = token.access_token
        expired.set_exp(lifetime=timedelta(seconds=-1))
        for value in ['bad-token', str(expired), str(token.access_token) + 'tamper']:
            self.client.credentials(HTTP_AUTHORIZATION='Bearer ' + value)
            self.assertEqual(self.client.get('/api/profile/').status_code, 401)
        self.client.credentials()
        token.set_exp(lifetime=timedelta(seconds=-1))
        self.assertEqual(self.client.post('/api/token/refresh/', {'refresh': str(token)}, format='json').status_code, 401)

    def test_disabled_account_loses_access_and_refresh_immediately(self):
        token = self.auth(self.patient)
        self.patient.is_active = False
        self.patient.save()
        self.assertEqual(self.client.get('/api/profile/').status_code, 401)
        self.client.credentials()
        self.assertEqual(self.client.post('/api/token/refresh/', {'refresh': str(token)}, format='json').status_code, 401)

    def test_revoking_doctor_approval_blocks_existing_access_token(self):
        self.auth(self.approved)
        self.approved.clinical_access_approved = False
        self.approved.save()
        self.assertEqual(self.client.get('/api/cases/').status_code, 403)
        self.assertEqual(self.client.patch(f'/api/cases/{self.case.pk}/status/', {'status': 'active'}, format='json').status_code, 403)

    def test_profile_nested_user_cannot_change_role_or_privileges(self):
        self.auth(self.patient)
        response = self.client.patch('/api/profile/', {'user': {'user_type': 'doctor', 'is_superuser': True,
                                                  'clinical_access_approved': True}}, format='json')
        self.assertEqual(response.status_code, 200)
        self.patient.refresh_from_db()
        self.assertEqual(self.patient.user_type, 'patient')
        self.assertFalse(self.patient.is_superuser or self.patient.clinical_access_approved)

    def test_profile_field_boundaries_for_each_role(self):
        for user in [self.patient, self.student, self.doctor]:
            self.auth(user)
            for data in [{'gender': 'invalid'}, {'phone': '0' * 16}, {'birthdate': 'not-a-date'},
                         {'birthdate': str(date.today() + timedelta(days=1))}]:
                self.assertEqual(self.client.patch('/api/profile/', data, format='json').status_code, 400, data)
            if user.user_type != 'patient':
                for data in [{'specialty': 'invalid'}, {'years_of_teaching': 9}, {'wanted_groups': -1}]:
                    self.assertEqual(self.client.patch('/api/profile/', data, format='json').status_code, 400)

    def test_case_field_boundaries_and_status_update_preserve_patient(self):
        self.auth(self.patient)
        for field, value in [('pain_type', 'invalid'), ('pain_location', 'invalid'),
                             ('pain_duration', 'invalid'), ('title', 'x' * 101)]:
            response = self.client.post('/api/cases/create/', {'description': 'Synthetic', field: value}, format='json')
            self.assertEqual(response.status_code, 400)
        self.auth(self.approved)
        response = self.client.patch(f'/api/cases/{self.case.pk}/status/',
                                    {'status': 'active', 'patient': self.other.pk, 'physician_notes': 'injected'}, format='json')
        self.assertEqual(response.status_code, 200)
        self.case.refresh_from_db()
        self.assertEqual(self.case.patient_id, self.patient.pk)
        self.assertFalse(self.case.physician_notes)

    def test_case_pagination_limits_and_owner_isolation(self):
        Case.objects.bulk_create([Case(patient=self.patient, description='Synthetic', title=f'Case {i}') for i in range(105)])
        self.auth(self.patient)
        first = self.client.get('/api/cases/?page_size=1000')
        self.assertEqual(first.data['count'], 106)
        self.assertEqual(len(first.data['results']), 100)
        second = self.client.get('/api/cases/?page_size=100&page=2')
        self.assertEqual(len(second.data['results']), 6)
        self.assertTrue(all(case['patient'] == self.patient.pk for case in first.data['results'] + second.data['results']))
        self.assertEqual(self.client.get('/api/cases/?page=999').status_code, 404)

    def test_api_image_limits_and_formats(self):
        self.auth(self.patient)
        for upload in [image_upload('GIF'), image_upload(padding=5 * 1024 * 1024),
                       image_upload(size=(5001, 4000))]:
            response = self.client.patch('/api/profile/', {'profile_image': upload}, format='multipart')
            self.assertEqual(response.status_code, 400, response.data)
        for fmt in ['PNG', 'JPEG', 'WEBP']:
            response = self.client.patch('/api/profile/', {'profile_image': image_upload(fmt)}, format='multipart')
            self.assertEqual(response.status_code, 200, response.data)

    def test_replacing_and_clearing_image_remove_only_previous_file(self):
        self.auth(self.patient)
        self.client.patch('/api/profile/', {'profile_image': image_upload()}, format='multipart')
        self.patient.patient_profile.refresh_from_db()
        old_path = Path(self.patient.patient_profile.profile_image.path)
        with self.captureOnCommitCallbacks(execute=True):
            self.client.patch('/api/profile/', {'profile_image': image_upload()}, format='multipart')
        self.patient.patient_profile.refresh_from_db()
        current_path = Path(self.patient.patient_profile.profile_image.path)
        self.assertFalse(old_path.exists())
        self.assertTrue(current_path.exists())
        with self.captureOnCommitCallbacks(execute=True):
            response = self.client.patch('/api/profile/', {'profile_image': None}, format='json')
        self.assertEqual(response.status_code, 200)
        self.assertFalse(current_path.exists())

    def test_rollback_preserves_existing_image(self):
        self.auth(self.patient)
        self.client.patch('/api/profile/', {'profile_image': image_upload()}, format='multipart')
        profile = PatientProfile.objects.get(user=self.patient)
        original = Path(profile.profile_image.path)
        with self.captureOnCommitCallbacks(execute=True):
            try:
                with transaction.atomic():
                    profile.profile_image = None
                    profile.save()
                    raise RuntimeError('Synthetic transaction rollback')
            except RuntimeError:
                pass
        self.assertTrue(original.exists())
        profile.refresh_from_db()
        self.assertTrue(profile.profile_image)

    def test_private_media_blocks_path_traversal_and_unassociated_files(self):
        self.auth(self.approved)
        unrelated = Path(self.upload_dir.name) / 'unassociated.png'
        unrelated.write_bytes(b'synthetic')
        for path in ['unassociated.png', '../manage.py', '%2e%2e/manage.py', '/etc/passwd']:
            self.assertEqual(self.client.get('/media/' + path).status_code, 404)


class ReleaseAdminTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.admin = User.objects.create_superuser(username='release-admin', email='release-admin@example.test', password='Release-Admin-Password-991!')
        cls.patient = User.objects.create_user(username='release-patient', email='release-patient@example.test')
        cls.profile = PatientProfile.objects.create(user=cls.patient)
        cls.case = Case.objects.create(patient=cls.patient, description='Synthetic', title='Synthetic case')
        cls.specialty = Specialty.objects.create(name='Synthetic specialty')

    def setUp(self):
        cache.clear()
        self.media = TemporaryDirectory()
        self.addCleanup(self.media.cleanup)
        self.settings_override = override_settings(MEDIA_ROOT=self.media.name)
        self.settings_override.enable()
        self.addCleanup(self.settings_override.disable)
        self.client.force_login(self.admin)

    def test_all_admin_add_change_history_and_delete_pages_render(self):
        objects = {'user': self.patient, 'patientprofile': self.profile, 'case': self.case, 'specialty': self.specialty}
        for model in ['user', 'patientprofile', 'doctorprofile', 'studentprofile', 'case', 'specialty']:
            self.assertEqual(self.client.get(reverse('admin:accounts_' + model + '_add')).status_code, 200, model)
        for model, obj in objects.items():
            for action in ['change', 'history', 'delete']:
                self.assertEqual(self.client.get(reverse('admin:accounts_' + model + '_' + action, args=[obj.pk])).status_code, 200)

    def test_admin_rejects_future_birthdate_before_database_save(self):
        response = self.client.post(reverse('admin:accounts_patientprofile_change', args=[self.profile.pk]), {
            'user': self.patient.pk, 'birthdate': str(date.today() + timedelta(days=400)),
            'chronic_diseases': 'Synthetic', '_save': 'Save'})
        self.assertEqual(response.status_code, 200)
        self.assertIn('birthdate', response.context['adminform'].form.errors)
        self.profile.refresh_from_db()
        self.assertIsNone(self.profile.birthdate)

    def test_admin_enforces_upload_policy(self):
        for upload in [image_upload('GIF'), image_upload(padding=5 * 1024 * 1024), image_upload(size=(5001, 4000))]:
            request = RequestFactory().get('/admin/')
            request.user = self.admin
            form_class = admin.site._registry[Case].get_form(request, self.case)
            form = form_class(data={'patient': self.patient.pk, 'description': 'Synthetic', 'status': 'pending'},
                              files={'photos': upload}, instance=Case.objects.get(pk=self.case.pk))
            self.assertFalse(form.is_valid())
            self.assertIn('photos', form.errors)

    def test_admin_create_user_login_and_case_save_work(self):
        response = self.client.post(reverse('admin:accounts_user_add'), {
            'username': 'created-by-admin', 'email': 'created-by-admin@example.test', 'first_name': 'معاينة',
            'last_name': 'اختبار', 'user_type': 'doctor', 'password1': 'Created-Admin-User-Password-927!',
            'password2': 'Created-Admin-User-Password-927!', 'usable_password': 'true', '_save': 'Save'})
        self.assertEqual(response.status_code, 302, getattr(response, 'context', None) and response.context['adminform'].form.errors)
        user = User.objects.get(email='created-by-admin@example.test')
        self.assertTrue(user.check_password('Created-Admin-User-Password-927!'))
        self.assertFalse(user.clinical_access_approved)
        self.assertTrue(DoctorProfile.objects.filter(user=user).exists())
        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION='Bearer ' + str(RefreshToken.for_user(user).access_token))
        self.assertEqual(client.get('/api/profile/').status_code, 200)
        response = self.client.post(reverse('admin:accounts_case_change', args=[self.case.pk]), {
            'patient': self.patient.pk, 'title': 'تحديث تجريبي', 'description': 'Synthetic',
            'status': 'completed', 'physician_notes': 'Synthetic doctor notes', '_save': 'Save'})
        self.assertEqual(response.status_code, 302)
        self.case.refresh_from_db()
        self.assertEqual(self.case.title, 'تحديث تجريبي')
        self.assertEqual(self.case.status, 'completed')

    def test_profile_admin_only_offers_accounts_with_matching_role(self):
        doctor = User.objects.create_user(username='role-doctor', email='role-doctor@example.test', user_type='doctor')
        student = User.objects.create_user(username='role-student', email='role-student@example.test', user_type='student')
        request = RequestFactory().get('/admin/')
        request.user = self.admin
        for model, expected_role in [(PatientProfile, 'patient'), (DoctorProfile, 'doctor'), (StudentProfile, 'student')]:
            form = admin.site._registry[model].get_form(request)()
            self.assertTrue(all(user.user_type == expected_role for user in form.fields['user'].queryset))

    def test_admin_session_csrf_and_logout_are_enforced(self):
        client = APIClient(enforce_csrf_checks=True)
        response = client.get('/admin/login/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(client.post('/admin/login/', {'username': self.admin.email, 'password': 'Release-Admin-Password-991!'}).status_code, 403)
        csrf = client.cookies['dentalhealth_csrftoken'].value
        response = client.post('/admin/login/', {'username': self.admin.email.upper(), 'password': 'Release-Admin-Password-991!',
                                               'csrfmiddlewaretoken': csrf, 'next': '/admin/'})
        self.assertEqual(response.status_code, 302)
        self.assertEqual(client.get('/admin/').status_code, 200)
        self.assertEqual(client.get('/admin/logout/').status_code, 405)
        self.assertEqual(client.post('/admin/logout/', {}).status_code, 403)
        csrf = client.cookies['dentalhealth_csrftoken'].value
        self.assertEqual(client.post('/admin/logout/', {'csrfmiddlewaretoken': csrf}).status_code, 200)
        self.assertEqual(client.get('/admin/').status_code, 302)

    def test_read_only_staff_has_no_save_delete_or_bulk_actions(self):
        staff = User.objects.create_user(username='view-only', email='view-only@example.test', is_staff=True)
        staff.user_permissions.add(Permission.objects.get(codename='view_case'))
        self.client.force_login(staff)
        response = self.client.get(reverse('admin:accounts_case_change', args=[self.case.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, 'name="_save"')
        self.assertNotContains(response, 'class="deletelink"')
        response = self.client.get(reverse('admin:accounts_case_changelist'))
        self.assertNotContains(response, 'name="action"')

    def test_untrusted_titles_and_names_are_escaped(self):
        payload = '<script>alert("synthetic")</script>'
        self.case.title = payload
        self.case.save()
        self.patient.first_name = payload
        self.patient.save()
        for url in ['/admin/', '/admin/accounts/case/', '/admin/accounts/user/']:
            response = self.client.get(url)
            self.assertNotContains(response, payload)
            self.assertContains(response, '&lt;script&gt;')
