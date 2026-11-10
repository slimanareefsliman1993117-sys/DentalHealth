from django.contrib.auth.models import Permission
from django.test import TestCase
from django.urls import reverse
from django.utils import translation
from accounts.models import User, PatientProfile, DoctorProfile, Case


class AdminInterfaceTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.admin=User.objects.create_superuser(username='admin',email='admin@example.test',password='Synthetic-Admin-Password-934!')
        cls.patient=User.objects.create_user(username='patient',email='patient@example.test',password=None,user_type='patient')
        PatientProfile.objects.create(user=cls.patient)
        cls.doctor=User.objects.create_user(username='doctor',email='doctor@example.test',password=None,user_type='doctor')
        DoctorProfile.objects.create(user=cls.doctor,specialty='dentistry')
        cls.case=Case.objects.create(patient=cls.patient,title='Synthetic case',description='Synthetic test data',status='pending')
        cls.staff=User.objects.create_user(username='limited',email='limited@example.test',password=None,is_staff=True)

    def test_login_is_arabic_and_uses_email(self):
        response=self.client.get(reverse('admin:login'))
        self.assertEqual(response.status_code,200)
        self.assertContains(response,'dir="rtl"')
        self.assertContains(response,'البريد الإلكتروني')
        self.assertContains(response,'type="email"')
        self.assertContains(response,'csrfmiddlewaretoken')
        self.assertContains(response,'data-password-toggle')

    def test_dashboard_uses_database_counts(self):
        self.client.force_login(self.admin)
        response=self.client.get(reverse('admin:index'))
        self.assertEqual(response.status_code,200)
        self.assertEqual(response.context['pending_doctor_count'],1)
        self.assertEqual(response.context['weekly_total'],1)
        self.assertEqual(len(response.context['recent_cases']),1)
        stats={s['label']:s['value'] for s in response.context['dashboard_stats']}
        self.assertEqual(stats['إجمالي المرضى'],1)
        self.assertEqual(stats['الأطباء المعتمدون'],0)
        self.assertEqual(stats['بانتظار المراجعة'],1)

    def test_staff_without_model_permissions_sees_no_patient_information(self):
        self.client.force_login(self.staff)
        response=self.client.get(reverse('admin:index'))
        self.assertEqual(response.status_code,200)
        self.assertFalse(response.context['dashboard_stats'])
        self.assertNotIn('recent_cases',response.context)
        self.assertNotIn('pending_doctors',response.context)
        self.assertNotContains(response,'Synthetic case')
        self.assertNotContains(response,'patient@example.test')

    def test_case_view_permission_does_not_reveal_user_admin_data(self):
        self.staff.user_permissions.add(Permission.objects.get(codename='view_case'))
        self.client.force_login(self.staff)
        response=self.client.get(reverse('admin:index'))
        self.assertTrue(response.context['can_view_cases'])
        self.assertNotIn('pending_doctors',response.context)
        self.assertNotContains(response,reverse('admin:accounts_user_changelist'))
        self.assertContains(response,'Synthetic case')

    def test_list_and_edit_pages_render_with_original_admin_controls(self):
        self.client.force_login(self.admin)
        for name in ['user','patientprofile','doctorprofile','studentprofile','case','specialty']:
            response=self.client.get(reverse('admin:accounts_'+name+'_changelist'))
            self.assertEqual(response.status_code,200)
            self.assertContains(response,'dental_admin/admin.css')
        response=self.client.get(reverse('admin:accounts_case_change',args=[self.case.pk]))
        self.assertContains(response,'name="status"')
        self.assertContains(response,'csrfmiddlewaretoken')
        self.assertContains(response,'name="_save"')
        response=self.client.get(reverse('admin:accounts_user_change',args=[self.doctor.pk]))
        self.assertContains(response,'name="clinical_access_approved"')

    def test_dashboard_filters_link_to_matching_results(self):
        self.client.force_login(self.admin)
        response=self.client.get(reverse('admin:accounts_case_changelist')+'?status__exact=pending')
        self.assertEqual(response.status_code,200)
        self.assertEqual(response.context['cl'].result_count,1)
        response=self.client.get(reverse('admin:accounts_doctorprofile_changelist')+'?user__clinical_access_approved=1&user__is_active=1')
        self.assertEqual(response.status_code,200)
        self.assertEqual(response.context['cl'].result_count,0)

    def test_read_only_staff_cannot_approve_doctors(self):
        self.staff.user_permissions.add(Permission.objects.get(codename='view_user'))
        self.client.force_login(self.staff)
        response=self.client.post(reverse('admin:accounts_user_change',args=[self.doctor.pk]),{'clinical_access_approved':'on'})
        self.assertEqual(response.status_code,403)
        self.doctor.refresh_from_db()
        self.assertFalse(self.doctor.clinical_access_approved)

    def test_api_language_does_not_inherit_admin_language(self):
        self.client.get(reverse('admin:login'))
        response=self.client.get('/api/profile/')
        self.assertIn('credentials',str(response.data).lower())
        self.assertEqual(translation.get_language(),'en-us')
