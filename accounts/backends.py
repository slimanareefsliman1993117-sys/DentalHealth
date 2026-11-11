from django.contrib.auth import get_user_model
from django.contrib.auth.backends import ModelBackend
from django.conf import settings
from .demo import is_public_demo


class EmailBackend(ModelBackend):
    """Use the same case-insensitive email authentication for both login URLs."""
    def authenticate(self, request, username=None, password=None, **kwargs):
        User = get_user_model()
        email = kwargs.get('email', username)
        if email is None or password is None:
            return None
        try:
            user = User.objects.get(email__iexact=email.strip())
        except User.DoesNotExist:
            User().set_password(password)
            return None
        if user.check_password(password) and self.user_can_authenticate(user):
            if is_public_demo(user) and (not settings.PUBLIC_DEMO_ENABLED or user.is_superuser or
                    request is None or request.path_info != '/admin/login/'):
                return None
            return user
