"""Run only inside an extracted release in a temporary directory, via release_check.py."""
import importlib.util
import json
import secrets
from io import BytesIO
from pathlib import Path

from PIL import Image

# Import the exact WSGI entry point that will be copied to PythonAnywhere.
spec = importlib.util.spec_from_file_location('release_wsgi', 'deploy/wsgi.generated.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

from django.conf import settings
from django.contrib.staticfiles.storage import staticfiles_storage
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client
from django.test.utils import setup_test_environment
from django.urls import reverse
from accounts.models import User, Case

setup_test_environment()
assert not settings.DEBUG
assert Path(settings.DATABASES['default']['NAME']).resolve().parent == Path.cwd()
assert not User.objects.exists()
assert Path('.env').stat().st_mode & 0o777 == 0o600
host = 'release-validation.example.test'
client = Client(enforce_csrf_checks=True, HTTP_HOST=host)
checks = []


def checked(name):
    checks.append(name)


def api(method, path, payload=None, token=None, expected=200):
    kwargs = {'secure': True}
    if token:
        kwargs['HTTP_AUTHORIZATION'] = 'Bearer ' + token
    if payload is not None:
        kwargs.update(data=json.dumps(payload), content_type='application/json')
    response = getattr(client, method)(path, **kwargs)
    assert response.status_code == expected, (method, path, response.status_code)
    return response


response = client.get('/')
assert response.status_code == 301 and response['Location'].startswith('https://')
response = client.get('/', secure=True)
assert response.status_code == 200
assert response['X-Frame-Options'] == 'DENY'
assert response['X-Content-Type-Options'] == 'nosniff'
assert 'max-age=31536000' in response['Strict-Transport-Security']
assert client.get('/', secure=True, HTTP_HOST='untrusted.example.test').status_code == 400
response = client.options('/api/profile/', secure=True, HTTP_ORIGIN='https://untrusted.example.test',
                          HTTP_ACCESS_CONTROL_REQUEST_METHOD='GET')
assert 'Access-Control-Allow-Origin' not in response
checked('production_https_host_and_security_headers')

response = client.get('/admin/login/', secure=True)
assert response.status_code == 200 and 'dir="rtl"' in response.content.decode()
assert client.cookies[settings.CSRF_COOKIE_NAME]['secure']
for asset in ['admin.css', 'admin.js', 'icons.svg']:
    url = staticfiles_storage.url('dental_admin/' + asset)
    assert url != '/static/dental_admin/' + asset
    response = client.get(url, secure=True)
    assert response.status_code == 200
    response.close()
checked('arabic_admin_and_collected_hashed_assets')

password = 'Synthetic-Release-' + secrets.token_urlsafe(24)
accounts = {}
for role, name in [('patient', 'patient'), ('patient', 'other'), ('doctor', 'doctor'), ('student', 'student')]:
    payload = {'email': name + '@example.test', 'fullname': 'معاينة ' + name, 'phone': '0000000000',
               'password': password, 'user_type': role}
    response = api('post', '/api/register/', payload, expected=201).json()
    accounts[name] = response
    profile = api('get', '/api/profile/', token=response['access']).json()
    assert profile['user']['id'] == response['user']['id']
    api('patch', '/api/profile/', {'birthdate': '1995-05-15', 'phone': '0000001234'}, response['access'])
api('post', '/api/register/', payload, expected=400)
for path in ['/api/login/', '/api/token/']:
    data = api('post', path, {'email': 'PATIENT@EXAMPLE.TEST', 'password': password}).json()
    assert data['access'] and data['refresh']
checked('all_three_roles_registration_login_and_profiles')

token = accounts['patient']['access']
stream = BytesIO()
Image.new('RGB', (32, 32), '#147d73').save(stream, format='PNG')
image_bytes = stream.getvalue()
response = client.post('/api/cases/create/', {'title': 'حالة تجريبية', 'description': 'Synthetic release validation',
    'status': 'completed', 'physician_notes': 'forged', 'patient': accounts['other']['user']['id'],
    'photos': SimpleUploadedFile('synthetic.png', image_bytes, content_type='image/png')},
    secure=True, HTTP_AUTHORIZATION='Bearer ' + token)
assert response.status_code == 201
data = response.json()
case = Case.objects.get(pk=data['id'])
assert case.patient_id == accounts['patient']['user']['id'] and case.status == 'pending' and not case.physician_notes
media_path = '/media/' + case.photos.name
assert api('get', '/api/cases/', token=token).json()['count'] == 1
assert api('get', '/api/cases/', token=accounts['other']['access']).json()['count'] == 0
api('get', '/api/cases/', token=accounts['doctor']['access'], expected=403)
api('get', '/api/cases/', token=accounts['student']['access'], expected=403)
api('get', media_path, expected=401)
api('get', media_path, token=accounts['other']['access'], expected=404)
response = api('get', media_path, token=token)
assert response['Cache-Control'] == 'private, no-store'
assert b''.join(response.streaming_content) == image_bytes
response.close()
checked('multipart_case_creation_ownership_roles_and_private_media')

admin_password = 'Synthetic-Administrator-' + secrets.token_urlsafe(24)
administrator = User.objects.create_superuser(username='release-admin', email='release-admin@example.test', password=admin_password)
admin = Client(enforce_csrf_checks=True, HTTP_HOST=host, HTTP_ORIGIN='https://' + host)
admin.get('/admin/login/', secure=True)
csrf = admin.cookies[settings.CSRF_COOKIE_NAME].value
assert admin.post('/admin/login/', {'username': administrator.email, 'password': admin_password}, secure=True).status_code == 403
assert admin.post('/admin/login/', {'username': administrator.email, 'password': admin_password,
        'csrfmiddlewaretoken': csrf}, secure=True, HTTP_ORIGIN='https://untrusted.example.test').status_code == 403
response = admin.post('/admin/login/', {'username': administrator.email, 'password': admin_password,
        'csrfmiddlewaretoken': csrf, 'next': '/admin/'}, secure=True)
assert response.status_code == 302
assert admin.cookies[settings.SESSION_COOKIE_NAME]['secure']
assert admin.cookies[settings.SESSION_COOKIE_NAME]['httponly']
assert admin.get('/admin/', secure=True).status_code == 200
doctor = User.objects.get(pk=accounts['doctor']['user']['id'])
csrf = admin.cookies[settings.CSRF_COOKIE_NAME].value
response = admin.post(reverse('admin:accounts_user_change', args=[doctor.pk]), {
    'username': doctor.username, 'email': doctor.email, 'first_name': doctor.first_name, 'last_name': doctor.last_name,
    'user_type': 'doctor', 'is_active': 'on', 'clinical_access_approved': 'on',
    'csrfmiddlewaretoken': csrf, '_save': 'Save'}, secure=True)
assert response.status_code == 302
doctor.refresh_from_db()
assert doctor.clinical_access_approved and not doctor.is_staff
assert api('get', '/api/cases/', token=accounts['doctor']['access']).json()['count'] == 1
api('patch', f'/api/cases/{case.pk}/status/', {'status': 'active'}, accounts['doctor']['access'])
case.refresh_from_db()
assert case.status == 'active'
response = api('get', media_path, token=accounts['doctor']['access'])
response.close()
response = admin.get(media_path, secure=True)
assert response.status_code == 200
response.close()
checked('secure_admin_login_csrf_doctor_approval_and_case_status')

rotated = api('post', '/api/token/refresh/', {'refresh': accounts['patient']['refresh']}).json()
api('post', '/api/token/refresh/', {'refresh': accounts['patient']['refresh']}, expected=401)
api('post', '/api/logout/', {'refresh': rotated['refresh']}, token=rotated['access'], expected=205)
api('post', '/api/token/refresh/', {'refresh': rotated['refresh']}, expected=401)
checked('token_rotation_logout_and_reuse_rejection')

uploaded_path = Path(case.photos.path)
assert uploaded_path.exists()
api('delete', '/api/account/delete/', token=token, expected=204)
assert not uploaded_path.exists() and not Case.objects.filter(pk=case.pk).exists()
api('get', '/api/profile/', token=token, expected=401)
api('get', media_path, token=accounts['doctor']['access'], expected=404)
checked('account_deletion_cascades_removes_upload_and_revokes_access')

print(json.dumps({'production_scenarios': checks, 'result': 'passed', 'default_accounts_in_archive': False}, indent=2))
