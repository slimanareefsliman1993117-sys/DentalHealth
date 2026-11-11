"""Public preview identity and its isolated, synthetic database."""
from django.conf import settings

DEMO_MODELS = {'case', 'patientprofile', 'doctorprofile', 'studentprofile', 'specialty'}


def is_public_demo(user):
    return bool(user.is_authenticated and user.email.casefold() == settings.PUBLIC_DEMO_EMAIL.casefold())


def data_alias(user):
    return 'demo' if is_public_demo(user) else 'default'
