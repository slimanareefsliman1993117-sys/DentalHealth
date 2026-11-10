from django.urls import path
from .views import RegisterView, LoginView, LogoutView, DeleteAccountView, ProfileView, CaseCreateView, CaseListView, CaseStatusUpdateView

urlpatterns = [
    path('register/', RegisterView.as_view(), name='register'),
    path('login/', LoginView.as_view(), name='login'),
    path('logout/', LogoutView.as_view(), name='logout'),
    path('account/delete/', DeleteAccountView.as_view(), name='delete_account'),
    path('profile/', ProfileView.as_view(), name='profile'),
    path('cases/create/', CaseCreateView.as_view(), name='case_create'),
    path('cases/', CaseListView.as_view(), name='case_list'),
    path('cases/<int:case_id>/status/', CaseStatusUpdateView.as_view(), name='case_status_update'),
]
