from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from django.contrib.auth import get_user_model
from rest_framework_simplejwt.serializers import TokenRefreshSerializer
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.exceptions import InvalidToken
from rest_framework_simplejwt.settings import api_settings
from rest_framework_simplejwt.utils import get_md5_hash_password

User = get_user_model()

class CustomTokenObtainPairSerializer(TokenObtainPairSerializer):
    # Override default fields to use 'email' instead of 'username'
    email = serializers.EmailField(required=True)
    password = serializers.CharField(required=True, write_only=True)

    # Remove the default 'username' field
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields.pop('username', None)  # Remove default username field
        self.fields['password'].trim_whitespace = False

    def validate(self, attrs):
        # Map 'email' to 'username' for authentication
        attrs['username'] = attrs.pop('email')
        return super().validate(attrs)


class SafeTokenRefreshSerializer(TokenRefreshSerializer):
    def validate(self, attrs):
        token = RefreshToken(attrs['refresh'])
        user = User.objects.filter(pk=token['user_id'], is_active=True).first()
        if user is None or token.get(api_settings.REVOKE_TOKEN_CLAIM) != get_md5_hash_password(user.password):
            raise InvalidToken('This refresh token is no longer valid.')
        return super().validate(attrs)
