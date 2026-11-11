from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenObtainPairView
from .models import PatientProfile, StudentProfile, DoctorProfile, Case
from .serializers import RegisterSerializer, LoginSerializer, LogoutSerializer, PatientProfileSerializer, StudentProfileSerializer, DoctorProfileSerializer, CaseSerializer, CaseStatusUpdateSerializer
from .serializers_jwt import CustomTokenObtainPairSerializer, SafeTokenRefreshSerializer
from rest_framework.pagination import PageNumberPagination
from rest_framework.throttling import ScopedRateThrottle
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.views import TokenRefreshView
from django.db import IntegrityError, transaction
from django.http import FileResponse, Http404
from django.conf import settings
from pathlib import Path
from rest_framework.authentication import SessionAuthentication
from .authentication import ClinicalJWTAuthentication
from .demo import is_public_demo

def format_errors(errors):
    """Helper function to format errors into a list with field-specific messages for missing fields."""
    error_list = []
    if isinstance(errors, dict):
        for field, messages in errors.items():
            if field.lower() == 'non_field_errors':
                # For non_field_errors, return only the message
                if isinstance(messages, list):
                    for message in messages:
                        error_list.append(str(message))
                else:
                    error_list.append(str(messages))
            else:
                # For other fields, include field name
                if isinstance(messages, list):
                    for message in messages:
                        if str(message) == "This field is required.":
                            error_list.append(f"The {field} field is required.")
                        else:
                            error_list.append(f"{field.capitalize()}: {message}")
                else:
                    if str(messages) == "This field is required.":
                        error_list.append(f"The {field} field is required.")
                    else:
                        error_list.append(f"{field.capitalize()}: {messages}")
    elif isinstance(errors, list):
        error_list = [str(error) for error in errors]
    else:
        error_list = [str(errors)]
    return error_list

class CustomTokenObtainPairView(TokenObtainPairView):
    serializer_class = CustomTokenObtainPairSerializer
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "auth"


class LimitedTokenRefreshView(TokenRefreshView):
    serializer_class = SafeTokenRefreshSerializer
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "auth"

class RegisterView(APIView):
    permission_classes = [AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "auth"

    def post(self, request):
        serializer = RegisterSerializer(data=request.data)
        if serializer.is_valid():
            try:
                user = serializer.save()
            except IntegrityError:
                return Response({"errors": ["Email is already in use."]}, status=400)
            refresh = RefreshToken.for_user(user)
            return Response({
                'user': {
                    'id': user.id,
                    'email': user.email,
                    'first_name': user.first_name,
                    'last_name': user.last_name,
                    'user_type': user.user_type
                },
                'refresh': str(refresh),
                'access': str(refresh.access_token)
            }, status=status.HTTP_201_CREATED)
        return Response({"errors": format_errors(serializer.errors)}, status=status.HTTP_400_BAD_REQUEST)

class LoginView(APIView):
    permission_classes = [AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "auth"

    def post(self, request):
        serializer = LoginSerializer(data=request.data, context={"request": request})
        if serializer.is_valid():
            user = serializer.validated_data['user']
            refresh = RefreshToken.for_user(user)
            return Response({
                'user': {
                    'id': user.id,
                    'email': user.email,
                    'first_name': user.first_name,
                    'last_name': user.last_name,
                    'user_type': user.user_type
                },
                'refresh': str(refresh),
                'access': str(refresh.access_token)
            }, status=status.HTTP_200_OK)
        return Response({"errors": format_errors(serializer.errors)}, status=status.HTTP_400_BAD_REQUEST)

class LogoutView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = LogoutSerializer(data=request.data, context={"request": request})
        if serializer.is_valid():
            try:
                refresh_token = serializer.validated_data['refresh']
                token = RefreshToken(refresh_token)
                token.blacklist()
                return Response({"message": "Successfully logged out."}, status=status.HTTP_205_RESET_CONTENT)
            except TokenError:
                return Response({"errors": ["Invalid refresh token."]}, status=status.HTTP_400_BAD_REQUEST)
        return Response({"errors": format_errors(serializer.errors)}, status=status.HTTP_400_BAD_REQUEST)

class DeleteAccountView(APIView):
    permission_classes = [IsAuthenticated]

    def delete(self, request):
        with transaction.atomic():
            request.user.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)

class ProfileView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        if user.user_type == 'patient':
            try:
                profile = PatientProfile.objects.get(user=user)
                serializer = PatientProfileSerializer(profile)
            except PatientProfile.DoesNotExist:
                return Response({"errors": ["Patient profile not found for this user."]}, status=status.HTTP_404_NOT_FOUND)
        elif user.user_type == 'student':
            try:
                profile = StudentProfile.objects.get(user=user)
                serializer = StudentProfileSerializer(profile)
            except StudentProfile.DoesNotExist:
                return Response({"errors": ["Student profile not found for this user."]}, status=status.HTTP_404_NOT_FOUND)
        elif user.user_type == 'doctor':
            try:
                profile = DoctorProfile.objects.get(user=user)
                serializer = DoctorProfileSerializer(profile)
            except DoctorProfile.DoesNotExist:
                return Response({"errors": ["Doctor profile not found for this user."]}, status=status.HTTP_404_NOT_FOUND)
        else:
            return Response({"errors": ["User type is invalid or not supported."]}, status=status.HTTP_400_BAD_REQUEST)
        return Response(serializer.data)

    def put(self, request):
        user = request.user
        if user.user_type == 'patient':
            try:
                profile = PatientProfile.objects.get(user=user)
                serializer = PatientProfileSerializer(profile, data=request.data, partial=True)
            except PatientProfile.DoesNotExist:
                return Response({"errors": ["Patient profile not found for this user."]}, status=status.HTTP_404_NOT_FOUND)
        elif user.user_type == 'student':
            try:
                profile = StudentProfile.objects.get(user=user)
                serializer = StudentProfileSerializer(profile, data=request.data, partial=True)
            except StudentProfile.DoesNotExist:
                return Response({"errors": ["Student profile not found for this user."]}, status=status.HTTP_404_NOT_FOUND)
        elif user.user_type == 'doctor':
            try:
                profile = DoctorProfile.objects.get(user=user)
                serializer = DoctorProfileSerializer(profile, data=request.data, partial=True)
            except DoctorProfile.DoesNotExist:
                return Response({"errors": ["Doctor profile not found for this user."]}, status=status.HTTP_404_NOT_FOUND)
        else:
            return Response({"errors": ["User type is invalid or not supported."]}, status=status.HTTP_400_BAD_REQUEST)

        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response({"errors": format_errors(serializer.errors)}, status=status.HTTP_400_BAD_REQUEST)

    def patch(self, request):
        return self.put(request)

class StandardResultsSetPagination(PageNumberPagination):
    page_size = 10
    page_size_query_param = 'page_size'
    max_page_size = 100

class CaseCreateView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        if request.user.user_type != 'patient':
            return Response({"errors": ["Only patients can create cases."]}, status=status.HTTP_403_FORBIDDEN)

        serializer = CaseSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save(patient=request.user)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response({"errors": format_errors(serializer.errors)}, status=status.HTTP_400_BAD_REQUEST)

class CaseListView(APIView):
    permission_classes = [IsAuthenticated]
    pagination_class = StandardResultsSetPagination

    def get(self, request):
        if request.user.user_type == 'patient':
            cases = Case.objects.filter(patient=request.user)
        elif request.user.user_type == 'doctor' and request.user.clinical_access_approved:
            cases = Case.objects.all()
        else:
            return Response({"errors": ["Clinical access requires administrator approval."]}, status=403)

        cases = cases.order_by('-created_at', '-pk')
        status_filter = request.query_params.get('status', None)
        if status_filter and status_filter not in dict(Case.STATUS_CHOICES):
            return Response({"errors": ["Invalid case status filter."]}, status=400)
        if status_filter in ['pending', 'active', 'completed', 'rejected']:
            cases = cases.filter(status=status_filter)

        paginator = self.pagination_class()
        result_page = paginator.paginate_queryset(cases, request)
        serializer = CaseSerializer(result_page, many=True)
        return paginator.get_paginated_response(serializer.data)

class CaseStatusUpdateView(APIView):
    permission_classes = [IsAuthenticated]

    def patch(self, request, case_id):
        if request.user.user_type != 'doctor' or not request.user.clinical_access_approved:
            return Response({"errors": ["Only approved doctors can update case status."]}, status=status.HTTP_403_FORBIDDEN)

        try:
            case = Case.objects.get(id=case_id)
        except Case.DoesNotExist:
            return Response({"errors": ["Case not found."]}, status=status.HTTP_404_NOT_FOUND)

        serializer = CaseStatusUpdateSerializer(case, data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response({"errors": format_errors(serializer.errors)}, status=status.HTTP_400_BAD_REQUEST)


class PrivateMediaView(APIView):
    """Medical uploads are never served by a public static/media mapping."""
    permission_classes = [IsAuthenticated]
    authentication_classes = [ClinicalJWTAuthentication, SessionAuthentication]

    def get(self, request, path):
        if is_public_demo(request.user):
            raise Http404
        root = Path(settings.MEDIA_ROOT).resolve()
        file_path = (root / path).resolve()
        if not file_path.is_relative_to(root) or not file_path.is_file():
            raise Http404
        clinical = request.user.is_superuser or (request.user.user_type == 'doctor' and request.user.clinical_access_approved)
        cases = Case.objects.filter(photos=path)
        allowed = cases.exists() if clinical else cases.filter(patient=request.user).exists()
        if not allowed:
            allowed = any(model.objects.filter(profile_image=path).filter(**({} if request.user.is_superuser else {'user': request.user})).exists()
                          for model in (PatientProfile, StudentProfile, DoctorProfile))
        if not allowed:
            raise Http404
        response = FileResponse(file_path.open('rb'))
        response['Cache-Control'] = 'private, no-store'
        response['X-Content-Type-Options'] = 'nosniff'
        return response
