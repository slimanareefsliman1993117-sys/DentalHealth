from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from accounts.views import CustomTokenObtainPairView
from accounts.views import LimitedTokenRefreshView, PrivateMediaView
from django.views.generic import TemplateView

urlpatterns = [
    path("", TemplateView.as_view(template_name="home.html"), name="home"),
    path("media/<path:path>", PrivateMediaView.as_view(), name="private_media"),
    path('admin/', admin.site.urls),
    path('api/', include('accounts.urls')),
    path('api/token/', CustomTokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('api/token/refresh/', LimitedTokenRefreshView.as_view(), name='token_refresh'),
]
