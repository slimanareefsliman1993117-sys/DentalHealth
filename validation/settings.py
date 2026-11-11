import os
os.environ['SECRET_KEY'] = 'synthetic-validation-secret-' + 'x' * 64
os.environ['DEBUG'] = 'True'
os.environ['DB_ENGINE'] = 'sqlite'
from dentalhealth.settings import *
DATABASES = {'default': {'ENGINE': 'django.db.backends.sqlite3', 'NAME': ':memory:'}}
DATABASES['demo'] = {'ENGINE': 'django.db.backends.sqlite3', 'NAME': ':memory:'}
ALLOWED_HOSTS = ['testserver', 'localhost', '127.0.0.1']
SECURE_SSL_REDIRECT = False
STORAGES = {'default': {'BACKEND': 'django.core.files.storage.FileSystemStorage'}, 'staticfiles': {'BACKEND': 'django.contrib.staticfiles.storage.StaticFilesStorage'}}
