from django.contrib.auth import authenticate
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import transaction
from rest_framework import serializers
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.tokens import RefreshToken
from .models import User, PatientProfile, StudentProfile, DoctorProfile, Case


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ('id', 'username', 'email', 'user_type', 'first_name', 'last_name', 'clinical_access_approved')


class ProfileSerializer(serializers.ModelSerializer):
    user = UserSerializer(read_only=True)

    class Meta:
        fields = '__all__'
        read_only_fields = ('id', 'user', 'age')


class PatientProfileSerializer(ProfileSerializer):
    class Meta(ProfileSerializer.Meta):
        model = PatientProfile


class StudentProfileSerializer(ProfileSerializer):
    class Meta(ProfileSerializer.Meta):
        model = StudentProfile


class DoctorProfileSerializer(ProfileSerializer):
    class Meta(ProfileSerializer.Meta):
        model = DoctorProfile


class RegisterSerializer(serializers.Serializer):
    email = serializers.EmailField(max_length=150)
    fullname = serializers.CharField(max_length=255)
    phone = serializers.CharField(max_length=15)
    password = serializers.CharField(write_only=True, trim_whitespace=False)
    user_type = serializers.ChoiceField(choices=User.USER_TYPE_CHOICES, write_only=True)

    def validate_email(self, value):
        value = value.strip().lower()
        if User.objects.filter(email__iexact=value).exists():
            raise serializers.ValidationError('Email is already in use.')
        return value

    def validate_fullname(self, value):
        if any(len(part) > 150 for part in value.split(maxsplit=1)):
            raise serializers.ValidationError('Each name must be at most 150 characters.')
        return value

    def validate(self, attrs):
        names = attrs['fullname'].split(maxsplit=1)
        candidate = User(email=attrs['email'], username=attrs['email'], first_name=names[0], last_name=names[1] if len(names) > 1 else '')
        try:
            validate_password(attrs['password'], candidate)
        except DjangoValidationError as error:
            raise serializers.ValidationError({'password': error.messages})
        return attrs

    @transaction.atomic
    def create(self, validated_data):
        names = validated_data['fullname'].split(maxsplit=1)
        user = User.objects.create_user(
            username=validated_data['email'], email=validated_data['email'],
            first_name=names[0], last_name=names[1] if len(names) > 1 else '',
            user_type=validated_data['user_type'], password=validated_data['password'],
        )
        profile_class = {'patient': PatientProfile, 'student': StudentProfile, 'doctor': DoctorProfile}[user.user_type]
        options = {} if user.user_type == 'patient' else {'specialty': 'dentistry'}
        profile_class.objects.create(user=user, phone=validated_data['phone'], **options)
        return user


class LoginSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True, trim_whitespace=False)

    def validate(self, data):
        user = authenticate(self.context.get('request'), username=data['email'], password=data['password'])
        if user is None:
            raise serializers.ValidationError('Invalid email or password.')
        data['user'] = user
        return data


class LogoutSerializer(serializers.Serializer):
    refresh = serializers.CharField()

    def validate_refresh(self, value):
        try:
            token = RefreshToken(value)
        except TokenError:
            raise serializers.ValidationError('Invalid refresh token.')
        if str(token['user_id']) != str(self.context['request'].user.pk):
            raise serializers.ValidationError('Refresh token does not belong to this account.')
        return value


class CaseSerializer(serializers.ModelSerializer):
    patient = serializers.PrimaryKeyRelatedField(read_only=True)

    class Meta:
        model = Case
        fields = '__all__'
        read_only_fields = ('patient', 'status', 'physician_notes', 'created_at', 'updated_at')


class CaseStatusUpdateSerializer(serializers.ModelSerializer):
    status = serializers.ChoiceField(choices=Case.STATUS_CHOICES, required=True)
    class Meta:
        model = Case
        fields = ('status',)
