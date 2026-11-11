from rest_framework.exceptions import AuthenticationFailed
from rest_framework_simplejwt.authentication import JWTAuthentication
from .demo import is_public_demo


class ClinicalJWTAuthentication(JWTAuthentication):
    def get_user(self, validated_token):
        user = super().get_user(validated_token)
        if is_public_demo(user):
            raise AuthenticationFailed('The public demo is available only in the read-only administration preview.')
        return user
