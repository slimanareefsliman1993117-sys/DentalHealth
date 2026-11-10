from zoneinfo import ZoneInfo
from django.conf import settings
from django.utils import timezone, translation


class AdminLanguageMiddleware:
    """Localize administration without changing the public API's language."""
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.path_info.startswith('/admin/'):
            with translation.override('ar'), timezone.override(ZoneInfo(settings.ADMIN_TIME_ZONE)):
                request.LANGUAGE_CODE = 'ar'
                response = self.get_response(request)
                response.headers.setdefault('Content-Language', 'ar')
                return response
        return self.get_response(request)
