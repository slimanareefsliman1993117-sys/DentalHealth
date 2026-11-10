# DentalHealth

Django REST API and Arabic (RTL) administration for patient, student and doctor
accounts, profiles and dental cases. The administration dashboard includes live
statistics, recent cases, activity charts and doctor approval links, with layouts
for desktop and mobile.

Python 3.11 · Django 5.2 · Django REST Framework · SQLite

## Run locally

```sh
python3.11 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
cp .env.example .env
```

Set a persistent, randomly generated `SECRET_KEY` in `.env` before continuing.
For an existing installation, preserve its original key and configuration.

```sh
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

Open `/admin/` and sign in using the administrator's **email address**.
There are no default accounts or passwords. The public `/` page describes the API;
this repository does not contain a separate patient-facing web/mobile frontend.

## Access and uploads

- Patients can create cases and view only their own cases.
- Doctors must be approved by an administrator before accessing clinical cases.
- Students and unapproved doctors cannot access other users' clinical records.
- Profile ownership, calculated age and privileges cannot be changed through the API.
- Images require authentication and authorization. Do not serve `/media/` publicly.
- JPEG, PNG and WebP uploads are limited to 5 MiB and 20 megapixels.
- JWT refresh tokens rotate; logout blacklists the submitted refresh token.

See [API.md](API.md) for endpoints, request fields and authentication details.
Email activation and password-reset email flows are not implemented here.

## Validation

```sh
.venv/bin/python test_api.py
```

The isolated suite has **69 tests** covering API workflows, permissions, uploads,
administration, CSRF, token expiry, file cleanup and invalid input. It uses only
synthetic data and temporary databases.

To build the upload and validate it in a fresh disposable Python environment
(requires [uv](https://docs.astral.sh/uv/)):

```sh
.venv/bin/python validation/release_check.py
```

This also checks production configuration, migrations, WSGI, static files and a
complete registration/case/doctor-approval/token/account-deletion workflow.
See [validation/REPORT.txt](validation/REPORT.txt) for the latest local review.

## Deploy to PythonAnywhere

Follow [SETUP.txt](SETUP.txt). The deployment helper generates a new private `.env`
for a fresh installation and refuses to overwrite existing configuration.

```sh
.venv/bin/python deploy/build_package.py
```

The generated upload contains source only. Credentials, databases, uploaded patient
files, virtual environments and private preview data are excluded from Git and
deployment packages. Production deployments must collect static files, enable
HTTPS and use a persistent signing key. SQLite is the validated deployment backend.
