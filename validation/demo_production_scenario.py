"""Acceptance for opt-in public preview in a disposable production release."""
import json
import runpy
from django.test import Client
runpy.run_path('deploy/wsgi.generated.py')
from django.conf import settings
from accounts.models import User, Case

host = 'release-validation.example.test'
private = User.objects.create_user(username='private-validation', email='private-validation@example.test')
case = Case.objects.create(patient=private, title='PRIVATE PRODUCTION RECORD', description='Synthetic private control record')
client = Client(enforce_csrf_checks=True, HTTP_HOST=host, HTTP_ORIGIN='https://' + host)
response = client.get('/admin/login/', secure=True)
assert response.status_code == 200
assert settings.PUBLIC_DEMO_EMAIL.encode() in response.content
assert settings.PUBLIC_DEMO_PASSWORD.encode() in response.content
assert 'no-store' in response['Cache-Control']
csrf = client.cookies[settings.CSRF_COOKIE_NAME].value
response = client.post('/admin/login/', {'username': settings.PUBLIC_DEMO_EMAIL, 'password': settings.PUBLIC_DEMO_PASSWORD,
    'csrfmiddlewaretoken': csrf, 'next': '/admin/'}, secure=True)
assert response.status_code == 302
response = client.get('/admin/', secure=True)
assert response.status_code == 200
assert b'PRIVATE PRODUCTION RECORD' not in response.content
for model in ['case', 'patientprofile', 'doctorprofile', 'studentprofile', 'specialty']:
    assert client.get('/admin/accounts/' + model + '/', secure=True).status_code == 200
response = client.get('/admin/accounts/case/1/change/', secure=True)
assert response.status_code == 200 and b'name="_save"' not in response.content
csrf = client.cookies[settings.CSRF_COOKIE_NAME].value
for path in ['/admin/accounts/case/1/change/', '/admin/password_change/', '/api/cases/create/']:
    assert client.post(path, {'status': 'completed', 'csrfmiddlewaretoken': csrf}, secure=True).status_code == 403
assert client.get('/admin/accounts/user/', secure=True).status_code == 403
assert client.get('/admin/accounts/case/1/history/', secure=True).status_code == 403
case.refresh_from_db()
assert case.status == 'pending'
owner = Client(HTTP_HOST=host)
owner.force_login(User.objects.get(is_superuser=True))
response = owner.get('/admin/', secure=True)
assert b'PRIVATE PRODUCTION RECORD' in response.content
assert Case.objects.using('demo').count() == 18
assert Case.objects.count() == 1
print(json.dumps({'public_demo_production': 'passed', 'separate_demo_database': 'passed',
    'anonymous_credentials_panel': 'passed', 'secure_demo_login': 'passed', 'immutable_preview': 'passed',
    'real_and_demo_data_isolation': 'passed'}))
