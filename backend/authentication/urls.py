from django.urls import path
from . import views

urlpatterns = [
    # Аутентификация
    path('register/', views.RegisterView.as_view(), name='register'),
    path('login/', views.LoginView.as_view(), name='login'),
    path('logout/', views.LogoutView.as_view(), name='logout'),
    path('google-auth/', views.GoogleAuthView.as_view(), name='google-auth'),
    
    # Профиль
    path('profile/', views.UserProfileView.as_view(), name='profile'),
    path('check-auth/', views.check_auth, name='check-auth'),
    path('csrf/', views.get_csrf_token, name='csrf'),
    path('users/', views.list_users, name='list-users'),
    path('profile/', views.user_profile, name='user-profile'),
    path('regions/', views.get_regions, name='regions'),
    path('cities/', views.get_cities, name='cities'),
    path('districts/', views.get_districts, name='districts'),
    path('detect-location/', views.detect_location, name='detect-location'),
    
    # Сброс пароля
    path('password-reset/', views.PasswordResetView.as_view(), name='password-reset'),
] 