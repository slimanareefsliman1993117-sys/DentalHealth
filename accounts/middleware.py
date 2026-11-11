from zoneinfo import ZoneInfo
from django.conf import settings
from django.utils import timezone, translation
from django.http import HttpResponseForbidden
from .demo import is_public_demo, DEMO_MODELS


class AdminLanguageMiddleware:
    """Localize administration without changing the public API's language."""
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if is_public_demo(request.user):
            if not settings.PUBLIC_DEMO_ENABLED and request.path_info != '/admin/logout/':
                return HttpResponseForbidden('المعاينة العامة غير مفعّلة.')
            if request.method not in {'GET', 'HEAD', 'OPTIONS'} and request.path_info not in {'/admin/login/', '/admin/logout/'}:
                return HttpResponseForbidden('حساب العرض للمشاهدة فقط؛ لا يمكن تعديل البيانات.')
            if request.path_info.startswith('/admin/'):
                allowed = request.path_info in {'/admin/', '/admin/login/', '/admin/logout/', '/admin/jsi18n/', '/admin/accounts/'}
                allowed = allowed or any(request.path_info.startswith('/admin/accounts/' + model + '/') for model in DEMO_MODELS)
                if not allowed:
                    return HttpResponseForbidden('هذه الصفحة غير متاحة في حساب العرض.')
        if request.path_info.startswith('/admin/'):
            with translation.override('ar'), timezone.override(ZoneInfo(settings.ADMIN_TIME_ZONE)):
                request.LANGUAGE_CODE = 'ar'
                response = self.get_response(request)
                response.headers.setdefault('Content-Language', 'ar')
                return response
        return self.get_response(request)
