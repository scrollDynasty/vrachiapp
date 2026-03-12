import os
from rest_framework import status, generics
import uuid
from django.views.decorators.csrf import csrf_exempt
from rest_framework.decorators import api_view, permission_classes
from django.views.decorators.csrf import ensure_csrf_cookie
from django.utils.decorators import method_decorator
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from django.contrib.auth import login, logout
from django.utils import timezone
from django.conf import settings
from django.core.files.storage import default_storage
import requests
import json
from django.db import models
from django.urls import reverse
from django.shortcuts import render
from django.http import FileResponse, Http404
import asyncio
from .ai_service import ai_service
import html
from django.core.cache import cache
from .models import LabOrder, LabTest, LabReport


from .models import (
    User, UserProfile, Region, MedCity, MedDistrict,
    DoctorApplication, Consultation, Message,
    MedCity, MedDistrict, MedicalFacility, FacilityReview,
)
from .serializers import (
    ConsultationSerializer, ConsultationCreateSerializer, ConsultationUpdateSerializer, MessageSerializer, UserSerializer, RegisterSerializer, LoginSerializer,
    GoogleAuthSerializer, PasswordResetSerializer,
    UserProfileSerializer, UserProfileReadSerializer,
    RegionSerializer, MedCitySerializer, MedDistrictSerializer,
    MedCitySerializer, MedDistrictSerializer,
    FacilityListSerializer, FacilityDetailSerializer, FacilityReviewSerializer,
    DoctorApplicationSerializer, DoctorApplicationCreateSerializer,
)
from .utils import create_user_with_verification, send_verification_email, verify_email_token, create_google_user

from rest_framework.pagination import PageNumberPagination

def paginate(request, queryset, serializer_class):
    paginator = PageNumberPagination()
    paginator.page_size = int(request.query_params.get('page_size', 20))
    paginator.page_size = min(paginator.page_size, 100)  # max 100
    page = paginator.paginate_queryset(queryset, request)
    if page is not None:
        serializer = serializer_class(page, many=True)
        return paginator.get_paginated_response(serializer.data)
    serializer = serializer_class(queryset, many=True)
    return Response(serializer.data)


class RegisterView(generics.CreateAPIView):
    """Регистрация пользователя с email верификацией"""
    queryset = User.objects.all()
    permission_classes = (AllowAny,)
    serializer_class = RegisterSerializer

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
                
        if not serializer.is_valid():
            # Не логируем чувствительные ошибки со входными данными
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        # Получаем данные из сериализатора
        email = serializer.validated_data['email']
        password = serializer.validated_data['password']
        first_name = serializer.validated_data.get('first_name', '')
        last_name = serializer.validated_data.get('last_name', '')
        username = serializer.validated_data.get('username', '')
        role = serializer.validated_data.get('role', 'patient')
        if role not in ['patient', 'doctor']:
            role = 'patient'
        
        # Если username не указан, используем email
        if not username:
            username = email.split('@')[0]
        
        # Создаем пользователя с верификацией
        user = create_user_with_verification(
            email=email,
            password=password,
            first_name=first_name,
            last_name=last_name,
            role=role
        )
        
        # Если был указан username, обновляем его
        if username and username != user.username:
            # Проверяем уникальность
            if not User.objects.filter(username=username).exists():
                user.username = username
                user.save()
        
        # Создаем профиль пользователя
        UserProfile.objects.create(user=user)
        
        # Отправляем email для верификации
        verification_url = request.build_absolute_uri(
            reverse('verify_email', kwargs={'token': user.email_verification_token})
        )
        
        email_sent = send_verification_email(user, verification_url)
        
        if email_sent:
            return Response({
                'message': 'Регистрация успешна! Проверьте ваш email для подтверждения аккаунта.',
                'email': email,
                'user_id': user.id
            }, status=status.HTTP_201_CREATED)
        else:
            # Если email не отправлен, удаляем пользователя
            user.delete()
            return Response({'error': 'Ошибка отправки email для подтверждения. Попробуйте позже.'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class LoginView(generics.GenericAPIView):
    """Вход пользователя"""
    permission_classes = (AllowAny,)
    serializer_class = LoginSerializer

    def post(self, request):
        serializer = self.get_serializer(data=request.data)
        
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        user = serializer.validated_data['user']
        login(request, user)
        
        # Получаем данные пользователя
        user_data = UserSerializer(user).data
        
        return Response({
            'message': 'Вход выполнен успешно',
            'user': user_data
        })


class LogoutView(generics.GenericAPIView):
    """Выход пользователя"""
    permission_classes = (IsAuthenticated,)

    def post(self, request):
        logout(request)
        return Response({'message': 'Выход выполнен успешно'})


class UserProfileView(generics.RetrieveUpdateAPIView):
    """Профиль пользователя"""
    permission_classes = (IsAuthenticated,)
    serializer_class = UserSerializer

    def get_object(self):
        return self.request.user


@method_decorator(csrf_exempt, name='dispatch')
class GoogleAuthView(generics.GenericAPIView):
    """Google OAuth аутентификация"""
    permission_classes = (AllowAny,)
    authentication_classes = ()  # отключаем SessionAuthentication/CSRF для этого эндпоинта
    serializer_class = GoogleAuthSerializer

    def post(self, request):
        serializer = self.get_serializer(data=request.data)
        
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        access_token = serializer.validated_data['access_token']
        
        try:
            # Получаем информацию о пользователе от Google
            google_user_info = self.get_google_user_info(access_token)
            
            if not google_user_info:
                return Response({
                    'error': 'Не удалось получить информацию о пользователе от Google'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # Создаем или получаем пользователя
            user = self.get_or_create_google_user(google_user_info)
            
            if not user.is_active:
                return Response({
                    'error': 'Аккаунт не активирован'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # Входим в систему
            login(request, user)
            
            # Получаем данные пользователя
            user_data = UserSerializer(user).data
            
            return Response({
                'message': 'Вход через Google выполнен успешно',
                'user': user_data
            })
            
        except Exception:
            return Response({
                'error': 'Ошибка аутентификации через Google'
            }, status=status.HTTP_400_BAD_REQUEST)

    def get_google_user_info(self, access_token):
        """Получает информацию о пользователе от Google"""
        try:
            response = requests.get(
                'https://www.googleapis.com/oauth2/v2/userinfo',
                headers={'Authorization': f'Bearer {access_token}'},
                timeout=5
            )
            
            if response.status_code == 200:
                return response.json()
            else:
                return None
        except Exception:
            return None

    def get_or_create_google_user(self, google_user_info):
        """Создает или получает пользователя на основе Google данных"""
        email = google_user_info.get('email')
        google_id = google_user_info.get('id')
        
        if not email:
            raise ValueError("Email не найден в данных Google")
        
        # Пытаемся найти пользователя по email или google_id
        user = None
        
        if google_id:
            try:
                user = User.objects.get(google_id=google_id)
            except User.DoesNotExist:
                pass
        
        if not user:
            try:
                user = User.objects.get(email=email)
                # Если пользователь найден по email, но у него нет google_id, добавляем его
                if not user.google_id and google_id:
                    user.google_id = google_id
                    user.save()
            except User.DoesNotExist:
                # Создаем нового пользователя
                user = create_google_user(google_user_info)
        
        return user


class PasswordResetView(generics.GenericAPIView):
    """Сброс пароля"""
    permission_classes = (AllowAny,)
    serializer_class = PasswordResetSerializer

    def post(self, request):
        serializer = self.get_serializer(data=request.data)
        
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        email = serializer.validated_data['email']
        
        try:
            user = User.objects.get(email=email)
            # Здесь должна быть логика отправки email для сброса пароля
            return Response({
                'message': 'Инструкции по сбросу пароля отправлены на ваш email'
            })
        except User.DoesNotExist:
            return Response({
                'message': 'Если пользователь с таким email существует, инструкции по сбросу пароля отправлены'
            })


@api_view(['GET'])
@permission_classes([AllowAny])
def check_auth(request):
    """Проверка аутентификации"""
    if request.user.is_authenticated:
        user_data = UserSerializer(request.user).data
        return Response({
            'authenticated': True,
            'user': user_data
        })
    else:
        return Response({
            'authenticated': False,
            'user': None
        })


@api_view(['GET'])
@permission_classes([AllowAny])
@ensure_csrf_cookie
def get_csrf_token(request):
    """Выдаёт CSRF токен и гарантированно устанавливает csrftoken cookie"""
    from django.middleware.csrf import get_token
    token = get_token(request)
    resp = Response({'csrfToken': token})
    # Явно выставляем cookie, чтобы избежать проблем на некоторых клиентах/браузерах
    resp.set_cookie(
        key='csrftoken',
        value=token,
        secure=True,
        httponly=False,
        samesite='Lax'
    )
    return resp


@api_view(['GET'])
@permission_classes([AllowAny])
def list_users(request):
    """Список пользователей (только для отладки)"""
    users = User.objects.all()
    serializer = UserSerializer(users, many=True)
    return Response(serializer.data)


@api_view(['GET'])
@permission_classes([AllowAny])
def get_regions(request):
    """Получение списка регионов"""
    regions = Region.objects.all()
    serializer = RegionSerializer(regions, many=True)
    return Response(serializer.data)


def get_cities(request):
    """Получение списка городов"""
    region_id = request.GET.get('region_id')
    if region_id:
        cities = MedCity.objects.filter(region_id=region_id)
    else:
        cities = MedCity.objects.all()
    serializer = MedCitySerializer(cities, many=True)
    return Response(serializer.data)


@api_view(['GET'])
@permission_classes([AllowAny])
def get_districts(request):
    """Получение списка районов"""
    region_id = request.GET.get('region_id')
    city_id = request.GET.get('city_id')

    districts = MedDistrict.objects.all()

    if region_id:
        districts = districts.filter(region_id=region_id)

    if city_id:
        districts = districts.filter(city_id=city_id)

    serializer = MedDistrictSerializer(districts, many=True)
    return Response(serializer.data)


@api_view(['POST'])
@permission_classes([AllowAny])
def detect_location(request):
    """Определение местоположения по IP"""
    
    # Локальные хелперы (объявлены до использования)
    def extract_nominatim_address(data):
        try:
            country = data.get('country', '')
            region = data.get('regionName', '')
            city = data.get('city', '')
            # Ищем регион в базе данных
            region_obj = None
            if region:
                try:
                    region_obj = Region.objects.filter(name__icontains=region).first()
                except Exception:
                    pass
            # Ищем город в базе данных
            city_obj = None
            if city and region_obj:
                try:
                    city_obj = MedCity.objects.filter(
                        name__icontains=city,
                        region=region_obj
                    ).first()
                except Exception:
                    pass
            return {
                'country': country,
                'region': region,
                'city': city,
                'region_id': region_obj.id if region_obj else None,
                'city_id': city_obj.id if city_obj else None,
                'ip': data.get('query', '')
            }
        except Exception:
            return None

    def extract_bigdatacloud_address(data):
        try:
            location = data.get('location', {})
            country = location.get('country', {}).get('name', '')
            region = location.get('region', {}).get('name', '')
            city = location.get('city', {}).get('name', '')
            # Ищем регион в базе данных
            region_obj = None
            if region:
                try:
                    region_obj = Region.objects.filter(name__icontains=region).first()
                except Exception:
                    pass
            # Ищем город в базе данных
            city_obj = None
            if city and region_obj:
                try:
                    city_obj = MedCity.objects.filter(
                        name__icontains=city,
                        region=region_obj
                    ).first()
                except Exception:
                    pass
            return {
                'country': country,
                'region': region,
                'city': city,
                'region_id': region_obj.id if region_obj else None,
                'city_id': city_obj.id if city_obj else None,
                'ip': data.get('ip', '')
            }
        except Exception:
            return None

    def extract_locationiq_address(data):
        try:
            country = data.get('country', '')
            region = data.get('region', '')
            city = data.get('city', '')
            # Ищем регион в базе данных
            region_obj = None
            if region:
                try:
                    region_obj = Region.objects.filter(name__icontains=region).first()
                except Exception:
                    pass
            # Ищем город в базе данных
            city_obj = None
            if city and region_obj:
                try:
                    city_obj = MedCity.objects.filter(
                        name__icontains=city,
                        region=region_obj
                    ).first()
                except Exception:
                    pass
            return {
                'country': country,
                'region': region,
                'city': city,
                'region_id': region_obj.id if region_obj else None,
                'city_id': city_obj.id if city_obj else None,
                'ip': data.get('ip', '')
            }
        except Exception:
            return None
    try:
        # Получаем IP адрес
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0]
        else:
            ip = request.META.get('REMOTE_ADDR')
        
        # Используем несколько сервисов для определения местоположения
        location_data = None
        
        # Попытка 1: Nominatim (OpenStreetMap)
        try:
            response = requests.get(f'http://ip-api.com/json/{ip}', timeout=3)
            if response.status_code == 200:
                data = response.json()
                if data.get('status') == 'success':
                    location_data = extract_nominatim_address(data)
        except Exception:
            pass
        
        # Попытка 2: BigDataCloud
        if not location_data:
            try:
                response = requests.get(f'https://api.bigdatacloud.net/data/ip-geolocation?ip={ip}&key=free', timeout=3)
                if response.status_code == 200:
                    data = response.json()
                    location_data = extract_bigdatacloud_address(data)
            except Exception:
                pass
        
        # Попытка 3: LocationIQ (если есть API ключ)
        if not location_data:
            try:
                # Здесь можно добавить LocationIQ API ключ
                # response = requests.get(f'https://us1.locationiq.com/v1/ip.php?key=YOUR_API_KEY&ip={ip}', timeout=5)
                # if response.status_code == 200:
                #     data = response.json()
                #     location_data = self.extract_locationiq_address(data)
                pass
            except Exception:
                pass
        
        if location_data:
            return Response(location_data)
        else:
            return Response({'error': 'Не удалось определить местоположение'}, status=status.HTTP_400_BAD_REQUEST)

    except Exception:
        return Response({'error': 'Ошибка определения местоположения'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    # (локальные хелперы перенесены наверх функции)


@api_view(['GET', 'PUT'])
@permission_classes([IsAuthenticated])
def user_profile(request):
    """Профиль пользователя"""
    if request.method == 'GET':
        if request.user.is_authenticated:
            try:
                profile = UserProfile.objects.get(user=request.user)
                serializer = UserProfileReadSerializer(profile)
                return Response(serializer.data)
            except UserProfile.DoesNotExist:
                return Response({
                    'error': 'Профиль не найден'
                }, status=status.HTTP_404_NOT_FOUND)
        else:
            return Response({'error': 'Пользователь не авторизован'}, status=status.HTTP_401_UNAUTHORIZED)
    
    elif request.method == 'PUT':
        if request.user.is_authenticated:
            try:
                profile = UserProfile.objects.get(user=request.user)
                serializer = UserProfileSerializer(profile, data=request.data, partial=True, context={'request': request})
                
                if serializer.is_valid():
                    serializer.save()
                    return Response(serializer.data)
                else:
                    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
            except UserProfile.DoesNotExist:
                return Response({
                    'error': 'Профиль не найден'
                }, status=status.HTTP_404_NOT_FOUND)
        else:
            return Response({
                'error': 'Пользователь не авторизован'
            }, status=status.HTTP_401_UNAUTHORIZED)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def submit_doctor_application(request):
    """Подача заявки на роль врача"""
    
    serializer = DoctorApplicationCreateSerializer(data=request.data)
    # сериализатор создан
    
    if serializer.is_valid():
        # сериализатор валиден
        # Привязываем заявку к текущему пользователю
        application = serializer.save(user=request.user)
        # заявка создана
        
        # Возвращаем полную информацию о заявке
        full_serializer = DoctorApplicationSerializer(application)
        return Response({
            'message': 'Заявка успешно отправлена! Мы рассмотрим её в течение 1-3 рабочих дней.',
            'application': full_serializer.data
        }, status=status.HTTP_201_CREATED)
    else:
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_doctor_applications(request):
    """Получение списка заявок (только для админов)"""
    # Проверяем, что пользователь является администратором
    if not (request.user.is_staff or request.user.is_superuser or request.user.role == 'admin'):
        return Response({'error': 'Доступ запрещен. Требуются права администратора.'}, status=status.HTTP_403_FORBIDDEN)
    
    applications = DoctorApplication.objects.all()
    serializer = DoctorApplicationSerializer(applications, many=True)
    return Response(serializer.data)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_doctor_application_detail(request, application_id):
    """Получение детальной информации о заявке"""
    try:
        application = DoctorApplication.objects.get(id=application_id)
        serializer = DoctorApplicationSerializer(application)
        return Response(serializer.data)
    except DoctorApplication.DoesNotExist:
        return Response({'error': 'Заявка не найдена'}, status=status.HTTP_404_NOT_FOUND)


@api_view(['PUT'])
@permission_classes([IsAuthenticated])
def update_doctor_application(request, application_id):
    """Обновление заявки (только для админов)"""
    # Проверяем, что пользователь является администратором
    if not (request.user.is_staff or request.user.is_superuser or request.user.role == 'admin'):
        return Response({'error': 'Доступ запрещен. Требуются права администратора.'}, status=status.HTTP_403_FORBIDDEN)
    
    try:
        application = DoctorApplication.objects.get(id=application_id)
    except DoctorApplication.DoesNotExist:
        return Response({'error': 'Заявка не найдена'}, status=status.HTTP_404_NOT_FOUND)
    
    serializer = DoctorApplicationUpdateSerializer(application, data=request.data, partial=True)
    if serializer.is_valid():
        # Если заявка одобрена, обновляем профиль пользователя
        if serializer.validated_data.get('status') == 'approved':
            user = application.user
            user.role = 'doctor'
            
            # Обновляем имя пользователя из заявки
            if application.first_name:
                user.first_name = application.first_name
            
            if application.last_name:
                user.last_name = application.last_name
            
            user.save()
            
            # Проверяем, что сохранилось
            user.refresh_from_db()
            
            # Обновляем или создаем профиль пользователя
            profile, created = UserProfile.objects.get_or_create(user=user)
            
            # убраны избыточные логи с персональными данными
            
            # Копируем все поля из заявки в профиль
            profile.specialization = application.specialization
            profile.experience = application.experience
            profile.education = application.education
            profile.license_number = application.license_number
            profile.languages = application.languages
            profile.additional_info = application.additional_info
            
            # Копируем поля профиля
            if application.date_of_birth:
                profile.date_of_birth = application.date_of_birth
            if application.gender:
                profile.gender = application.gender
            if application.phone:
                profile.phone = application.phone
            if application.address:
                profile.address = application.address
            if application.medical_info:
                profile.medical_info = application.medical_info
            if application.emergency_contact:
                profile.emergency_contact = application.emergency_contact
            
            # Копируем адресные данные
            if application.region:
                profile.region = application.region
            if application.city:
                profile.city = application.city
            if application.district:
                profile.district = application.district
            
            profile.save()
        
        # Обновляем заявку
        serializer.save(reviewed_by=request.user, reviewed_at=timezone.now())
        
        # Возвращаем обновленную заявку
        full_serializer = DoctorApplicationSerializer(application)
        return Response({
            'message': 'Заявка успешно обновлена',
            'application': full_serializer.data
        })
    else:
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_user_applications(request):
    """Получение заявок текущего пользователя"""
    applications = DoctorApplication.objects.filter(user=request.user)
    serializer = DoctorApplicationSerializer(applications, many=True)
    return Response(serializer.data)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_current_user_data(request):
    """Получение данных текущего пользователя"""
    user_data = UserSerializer(request.user).data
    
    # Добавляем информацию о профиле
    try:
        profile = UserProfile.objects.get(user=request.user)
        profile_data = UserProfileReadSerializer(profile).data
        user_data['profile'] = profile_data
    except UserProfile.DoesNotExist:
        user_data['profile'] = None
    
    # Добавляем информацию о заявках (если есть)
    if request.user.role == 'patient':
        applications = DoctorApplication.objects.filter(user=request.user)
        applications_data = DoctorApplicationSerializer(applications, many=True).data
        user_data['applications'] = applications_data
    else:
        user_data['applications'] = []
    
    return Response(user_data)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_doctors(request):
    """Получение списка врачей"""
    # Получаем всех пользователей с ролью врача
    doctors = User.objects.filter(role='doctor', is_active=True)
    
    # Фильтры
    specialization = request.GET.get('specialization')
    region_id = request.GET.get('region_id')
    city_id = request.GET.get('city_id')
    search = request.GET.get('search')
    
    if specialization:
        doctors = doctors.filter(profile__specialization__icontains=specialization)
    
    if region_id:
        doctors = doctors.filter(profile__region_id=region_id)
    
    if city_id:
        doctors = doctors.filter(profile__city_id=city_id)
    
    if search:
        doctors = doctors.filter(
            models.Q(first_name__icontains=search) |
            models.Q(last_name__icontains=search) |
            models.Q(profile__specialization__icontains=search)
        )
    
    # Получаем данные профилей
    doctors_data = []
    for doctor in doctors:
        try:
            profile = UserProfile.objects.get(user=doctor)
            doctor_data = {
                'id': doctor.id,
                'email': doctor.email,
                'first_name': doctor.first_name,
                'last_name': doctor.last_name,
                'full_name': doctor.full_name,
                'initials': doctor.initials,
                'avatar': doctor.avatar,
                'specialization': profile.specialization,
                'experience': profile.experience,
                'education': profile.education,
                'license_number': profile.license_number,
                'languages': profile.languages,
                'additional_info': profile.additional_info,
                'region': profile.region.name if profile.region else None,
                'city': profile.city.name if profile.city else None,
                'district': profile.district.name if profile.district else None,
                'phone': profile.phone,
                'address': profile.address,
            }
            doctors_data.append(doctor_data)
        except UserProfile.DoesNotExist:
            continue
    
    return Response(doctors_data)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_doctor_profile(request, doctor_id):
    """Получение профиля врача"""
    try:
        doctor = User.objects.get(id=doctor_id, role='doctor', is_active=True)
        profile = UserProfile.objects.get(user=doctor)
        
        doctor_data = {
            'id': doctor.id,
            'email': doctor.email,
            'first_name': doctor.first_name,
            'last_name': doctor.last_name,
            'full_name': doctor.full_name,
            'initials': doctor.initials,
            'avatar': doctor.avatar,
            'specialization': profile.specialization,
            'experience': profile.experience,
            'education': profile.education,
            'license_number': profile.license_number,
            'languages': profile.languages,
            'additional_info': profile.additional_info,
            'region': profile.region.name if profile.region else None,
            'city': profile.city.name if profile.city else None,
            'district': profile.district.name if profile.district else None,
            'phone': profile.phone,
            'address': profile.address,
        }
        
        return Response(doctor_data)
    except (User.DoesNotExist, UserProfile.DoesNotExist):
        return Response({'error': 'Врач не найден'}, status=status.HTTP_404_NOT_FOUND)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_all_users(request):
    """Получение всех пользователей (только для админов)"""
    if not (request.user.is_staff or request.user.is_superuser or request.user.role == 'admin'):
        return Response({'error': 'Доступ запрещен'}, status=status.HTTP_403_FORBIDDEN)
    
    users = User.objects.all()
    serializer = UserSerializer(users, many=True)
    return Response(serializer.data)


@api_view(['GET', 'PUT'])
@permission_classes([IsAuthenticated])
def manage_user_profile(request, user_id):
    """Управление профилем пользователя (только для админов)"""
    if not (request.user.is_staff or request.user.is_superuser or request.user.role == 'admin'):
        return Response({'error': 'Доступ запрещен'}, status=status.HTTP_403_FORBIDDEN)
    
    try:
        user = User.objects.get(id=user_id)
    except User.DoesNotExist:
        return Response({'error': 'Пользователь не найден'}, status=status.HTTP_404_NOT_FOUND)
    
    if request.method == 'GET':
        try:
            profile = UserProfile.objects.get(user=user)
            serializer = UserProfileSerializer(profile)
            return Response(serializer.data)
        except UserProfile.DoesNotExist:
            return Response({'error': 'Профиль не найден'}, status=status.HTTP_404_NOT_FOUND)
    
    elif request.method == 'PUT':
        try:
            profile = UserProfile.objects.get(user=user)
            serializer = UserProfileSerializer(profile, data=request.data, partial=True, context={'request': request})
            
            if serializer.is_valid():
                serializer.save()
                return Response(serializer.data)
            else:
                return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        except UserProfile.DoesNotExist:
            return Response({'error': 'Профиль не найден'}, status=status.HTTP_404_NOT_FOUND)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def update_doctor_name_from_application(request, application_id):
    # Проверяем, что пользователь является администратором
    if not (request.user.is_staff or request.user.is_superuser or request.user.role == 'admin'):
        return Response({'error': 'Доступ запрещен. Требуются права администратора.'}, status=status.HTTP_403_FORBIDDEN)
    
    try:
        application = DoctorApplication.objects.get(id=application_id)
    except DoctorApplication.DoesNotExist:
        return Response({'error': 'Заявка не найдена'}, status=status.HTTP_404_NOT_FOUND)
    
    user = application.user
    
    # Обновляем имя пользователя из заявки
    if application.first_name:
        user.first_name = application.first_name
    
    if application.last_name:
        user.last_name = application.last_name
    
    user.save()
    
    # Проверяем, что сохранилось
    user.refresh_from_db()
    
    return Response({
        'message': 'Имя пользователя обновлено',
        'user': UserSerializer(user).data
    })


@api_view(['DELETE'])
@permission_classes([IsAuthenticated])
def delete_user(request, user_id):
    # Проверяем, что пользователь является администратором
    if not (request.user.is_staff or request.user.is_superuser or request.user.role == 'admin'):
        return Response({'error': 'Доступ запрещен. Требуются права администратора.'}, status=status.HTTP_403_FORBIDDEN)
    
    try:
        user = User.objects.get(id=user_id)
    except User.DoesNotExist:
        return Response({'error': 'Пользователь не найден'}, status=status.HTTP_404_NOT_FOUND)
    
    # Не позволяем удалять самого себя
    if user == request.user:
        return Response({'error': 'Нельзя удалить самого себя'}, status=status.HTTP_400_BAD_REQUEST)
    
    # Удаляем пользователя
    user.delete()
    
    return Response({'message': 'Пользователь успешно удален'})


@api_view(['GET'])
@permission_classes([AllowAny])
def verify_email_view(request, token):
    """Верификация email по токену"""
    try:
        user = verify_email_token(token)
        if user:
            return Response({
                'message': 'Email успешно подтвержден! Теперь вы можете войти в систему.',
                'user_id': user.id
            })
        else:
            return Response({
                'error': 'Недействительный или истекший токен верификации'
            }, status=status.HTTP_400_BAD_REQUEST)
    except Exception as e:
        return Response({
            'error': 'Ошибка верификации email'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


def verify_email_html_view(request, token):
    """HTML страница для верификации email"""
    try:
        user = verify_email_token(token)
        if user:
            # Успех: передаем флаг success в шаблон успеха
            return render(request, 'authentication/email_verification_success.html', {
                'success': True,
                'user': user,
            })
        else:
            # Неуспех: показываем страницу успеха, но с блоком ошибки
            return render(request, 'authentication/email_verification_success.html', {
                'success': False,
                'error_message': 'Недействительный или истекший токен верификации'
            })
    except Exception:
        return render(request, 'authentication/email_verification_success.html', {
            'success': False,
            'error_message': 'Ошибка верификации email'
        })


@api_view(['POST'])
@permission_classes([AllowAny])
def resend_verification_email(request):
    """Повторная отправка email для верификации"""
    email = request.data.get('email')
    if not email:
        return Response({'error': 'Email обязателен'}, status=status.HTTP_400_BAD_REQUEST)
    
    try:
        user = User.objects.get(email=email)
        if user.is_verified:
            return Response({'error': 'Email уже подтвержден'}, status=status.HTTP_400_BAD_REQUEST)
        
        # Rate limit: max 1 email per 2 minutes
        if user.email_verification_sent_at:
            from django.utils import timezone
            elapsed = (timezone.now() - user.email_verification_sent_at).total_seconds()
            if elapsed < 120:
                remaining = int(120 - elapsed)
                return Response({
                    'error': f'Подождите {remaining} секунд перед повторной отправкой.'
                    }, status=status.HTTP_429_TOO_MANY_REQUESTS)
        
        # Создаем новый токен верификации
        user.email_verification_token = uuid.uuid4()
        user.email_verification_sent_at = timezone.now()
        user.save()
        
        # Отправляем email
        verification_url = request.build_absolute_uri(
            reverse('verify_email', kwargs={'token': user.email_verification_token})
        )
        
        email_sent = send_verification_email(user, verification_url)
        
        if email_sent:
            return Response({
                'message': 'Email для подтверждения отправлен повторно. Проверьте вашу почту.'
            })
        else:
            return Response({
                'error': 'Ошибка отправки email'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
            
    except User.DoesNotExist:
        return Response({
            'error': 'Пользователь с таким email не найден'
        }, status=status.HTTP_404_NOT_FOUND)


# Views для консультаций и чатов
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_consultations(request):
    """Получение списка консультаций пользователя"""
    user = request.user
    
    if user.role == 'patient':
        consultations = Consultation.objects.filter(patient=user)
    elif user.role == 'doctor':
        consultations = Consultation.objects.filter(doctor=user)
    else:
        return Response({'error': 'Доступ запрещен'}, status=status.HTTP_403_FORBIDDEN)
    return paginate(request, consultations, ConsultationSerializer)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def create_consultation(request):
    """Создание новой консультации"""
    serializer = ConsultationCreateSerializer(data=request.data, context={'request': request})
    
    if serializer.is_valid():
        consultation = serializer.save()
        full_serializer = ConsultationSerializer(consultation)
        return Response({
            'message': 'Консультация успешно создана',
            'consultation': full_serializer.data
        }, status=status.HTTP_201_CREATED)
    else:
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_consultation_detail(request, consultation_id):
    """Получение детальной информации о консультации"""
    try:
        consultation = Consultation.objects.get(id=consultation_id)
        
        # Проверяем доступ
        if request.user not in [consultation.patient, consultation.doctor]:
            return Response({'error': 'Доступ запрещен'}, status=status.HTTP_403_FORBIDDEN)
        
        serializer = ConsultationSerializer(consultation)
        return Response(serializer.data)
    except Consultation.DoesNotExist:
        return Response({'error': 'Консультация не найдена'}, status=status.HTTP_404_NOT_FOUND)


@api_view(['PUT'])
@permission_classes([IsAuthenticated])
def update_consultation(request, consultation_id):
    """Обновление консультации"""
    try:
        consultation = Consultation.objects.get(id=consultation_id)
        
        # Проверяем доступ
        if request.user not in [consultation.patient, consultation.doctor]:
            return Response({'error': 'Доступ запрещен'}, status=status.HTTP_403_FORBIDDEN)
        
        serializer = ConsultationUpdateSerializer(consultation, data=request.data, partial=True, context={'request': request})
        
        if serializer.is_valid():
            serializer.save()
            full_serializer = ConsultationSerializer(consultation)
            return Response({
                'message': 'Консультация успешно обновлена',
                'consultation': full_serializer.data
            })
        else:
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    except Consultation.DoesNotExist:
        return Response({'error': 'Консультация не найдена'}, status=status.HTTP_404_NOT_FOUND)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_messages(request, consultation_id):
    """Получение сообщений консультации"""
    try:
        consultation = Consultation.objects.get(id=consultation_id)
        
        # Проверяем доступ
        if request.user not in [consultation.patient, consultation.doctor]:
            return Response({'error': 'Доступ запрещен'}, status=status.HTTP_403_FORBIDDEN)
        
        messages = consultation.messages.all()
        return paginate(request, messages, MessageSerializer)
    except Consultation.DoesNotExist:
        return Response({'error': 'Консультация не найдена'}, status=status.HTTP_404_NOT_FOUND)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def send_message(request, consultation_id):
    """Отправка сообщения в консультацию"""
    try:
        consultation = Consultation.objects.get(id=consultation_id)
        
        # Проверяем доступ
        if request.user not in [consultation.patient, consultation.doctor]:
            return Response({'error': 'Доступ запрещен'}, status=status.HTTP_403_FORBIDDEN)
        
        # Проверяем, может ли пользователь писать
        if request.user == consultation.patient and not consultation.can_patient_write:
            return Response({'error': 'Нельзя писать в завершенной консультации'}, status=status.HTTP_400_BAD_REQUEST)
        elif request.user == consultation.doctor and not consultation.can_doctor_write:
            return Response({'error': 'Нельзя писать в завершенной консультации'}, status=status.HTTP_400_BAD_REQUEST)
        
        content = request.data.get('content')
        if not content:
            return Response({'error': 'Содержание сообщения обязательно'}, status=status.HTTP_400_BAD_REQUEST)
        
        message = Message.objects.create(
            consultation=consultation,
            sender=request.user,
            content=content
        )
        
        # Push notification to the other person
        recipient = consultation.doctor if request.user == consultation.patient else consultation.patient
        send_push_notification(
            user=recipient,
            title=f'New message from {request.user.full_name}',
            body=content[:100],
            data={'consultation_id': str(consultation_id), 'url': f'/consultations/{consultation_id}/'},
            notification_type='new_message',
        )

        serializer = MessageSerializer(message)
        return Response({
            'message': 'РЎРѕРѕР±С‰РµРЅРёРµ РѕС‚РїСЂР°РІР»РµРЅРѕ',
            'message_data': serializer.data
        }, status=status.HTTP_201_CREATED)
    except Consultation.DoesNotExist:
        return Response({'error': 'Консультация не найдена'}, status=status.HTTP_404_NOT_FOUND)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def accept_consultation(request, consultation_id):
    """Принятие консультации врачом"""
    try:
        consultation = Consultation.objects.get(id=consultation_id)
        
        # Проверяем, что пользователь является врачом этой консультации
        if request.user != consultation.doctor:
            return Response({'error': 'Доступ запрещен'}, status=status.HTTP_403_FORBIDDEN)
        
        # Проверяем, что консультация в статусе ожидания
        if consultation.status != 'pending':
            return Response({'error': 'Консультация уже не в статусе ожидания'}, status=status.HTTP_400_BAD_REQUEST)
        
        # Принимаем консультацию
        consultation.status = 'active'
        consultation.started_at = timezone.now()
        consultation.save()
        
        # Push notification to patient
        send_push_notification(
            user=consultation.patient,
            title='Consultation Accepted',
            body=f'Dr. {request.user.full_name} has accepted your consultation request.',
            data={'consultation_id': str(consultation_id), 'url': f'/consultations/{consultation_id}/'},
            notification_type='consultation',
        )

        serializer = ConsultationSerializer(consultation)
        return Response({
            'message': 'РљРѕРЅСЃСѓР»СЊС‚Р°С†РёСЏ СѓСЃРїРµС€РЅРѕ РїСЂРёРЅСЏС‚Р°',
            'consultation': serializer.data
        })
    except Consultation.DoesNotExist:
        return Response({'error': 'Консультация не найдена'}, status=status.HTTP_404_NOT_FOUND)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def complete_consultation(request, consultation_id):
    """Завершение консультации врачом"""
    try:
        consultation = Consultation.objects.get(id=consultation_id)
        
        # Проверяем, что пользователь является врачом этой консультации
        if request.user != consultation.doctor:
            return Response({'error': 'Доступ запрещен'}, status=status.HTTP_403_FORBIDDEN)
        
        # Проверяем, что консультация активна
        if consultation.status != 'active':
            return Response({'error': 'Консультация не активна'}, status=status.HTTP_400_BAD_REQUEST)
        
        # Завершаем консультацию
        consultation.status = 'completed'
        consultation.completed_at = timezone.now()
        consultation.save()

        # Auto-generate AI summary in background
        from .tasks import generate_consultation_summary
        generate_consultation_summary.delay(consultation.id)
        
        serializer = ConsultationSerializer(consultation)
        return Response({
            'message': 'Консультация успешно завершена',
            'consultation': serializer.data
        })
    except Consultation.DoesNotExist:
        return Response({'error': 'Консультация не найдена'}, status=status.HTTP_404_NOT_FOUND)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def ai_diagnosis(request):
    """API для работы с AI диагностикой с поддержкой голосового общения"""
    try:
        user = request.user
        
        # Проверяем тип запроса
        if 'file' in request.FILES:
            # Обработка файла (изображение, видео, аудио)
            file = request.FILES['file']
            file_type = request.data.get('type', 'image')
            # Базовая валидация контента
            max_size = getattr(settings, 'FILE_UPLOAD_MAX_SIZE', 10 * 1024 * 1024)
            if file.size > max_size:
                return Response({'error': 'Файл слишком большой'}, status=status.HTTP_400_BAD_REQUEST)
            allowed = []
            if file_type == 'image':
                allowed = getattr(settings, 'ALLOWED_IMAGE_MIME_TYPES', ['image/jpeg', 'image/png', 'image/gif'])
            elif file_type == 'audio':
                allowed = getattr(settings, 'ALLOWED_AUDIO_MIME_TYPES', ['audio/webm', 'audio/wav', 'audio/mp3', 'audio/ogg'])
            elif file_type == 'pdf':
                allowed = ['application/pdf']
            elif file_type == 'video':
                allowed = getattr(settings, 'ALLOWED_VIDEO_MIME_TYPES', ['video/mp4', 'video/webm'])
            
            if allowed and getattr(file, 'content_type', '') not in allowed:
                return Response({'error': 'Неподдерживаемый тип файла'}, status=status.HTTP_400_BAD_REQUEST)
            
            # Используем обновленный сервис
            if allowed and getattr(file, 'content_type', '') not in allowed:
                return Response({'error': 'Неподдерживаемый тип файла'}, status=status.HTTP_400_BAD_REQUEST)
            
            # Обработка по типу файла
            if file_type == 'image':
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                try:
                    result = loop.run_until_complete(ai_service.process_image_message(user, file))
                finally:
                    loop.close()

            elif file_type == 'audio':
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                try:
                    result = loop.run_until_complete(ai_service.process_audio_message(user, file))
                finally:
                    loop.close()

            elif file_type == 'pdf':
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                try:
                    result = loop.run_until_complete(ai_service.process_pdf_message(user, file))
                finally:
                    loop.close()

            elif file_type == 'video':
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                try:
                    result = loop.run_until_complete(ai_service.process_image_message(user, file))
                finally:
                    loop.close()
            else:
                return Response({'error': 'Неподдерживаемый тип файла'}, status=status.HTTP_400_BAD_REQUEST)
                
            if result['success']:
                # Сохраняем пользовательское сообщение
                user_message = ai_service.save_dialogue_message(
                    user=user,
                    content=result.get('transcription', f"Файл загружен: {file.name}"),
                    sender_type='user',
                    message_type=file_type,
                    audio_file=file.read() if file_type == 'audio' else None
                )
                
                # Сохраняем ответ AI с аудиофайлом если есть
                ai_message = ai_service.save_dialogue_message(
                    user=user,
                    content=result['response'],
                    sender_type='ai',
                    message_type='voice_response' if result.get('has_voice') else 'text',
                    audio_file=result.get('audio_content')
                )
                
                # Формируем ответ
                response_data = {
                    'response': result['response'],
                    'type': result['type'],
                    'has_voice': result.get('has_voice', False)
                }
                
                # Добавляем URL аудиофайла если есть
                if result.get('has_voice') and ai_message.audio_file:
                    response_data['audio_url'] = request.build_absolute_uri(ai_message.audio_file.url)
                
                # Добавляем расшифровку для аудио
                if result.get('transcription'):
                    response_data['transcription'] = result['transcription']
                
                return Response(response_data)
            else:
                return Response({
                    'error': result.get('error', 'Ошибка обработки файла')
                }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
                
        elif 'message' in request.data:
            # Обработка текстового сообщения
            message = request.data['message']
            
            if not message or not message.strip():
                return Response({
                    'error': 'Сообщение не может быть пустым'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # Асинхронная обработка текста с возможностью голосового ответа
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                result = loop.run_until_complete(ai_service.process_text_message(user, message))
            finally:
                loop.close()
                
            if result['success']:
                # Сохраняем пользовательское сообщение
                ai_service.save_dialogue_message(
                    user=user,
                    content=message,
                    sender_type='user',
                    message_type='text'
                )
                
                # Сохраняем ответ AI с аудиофайлом если есть
                ai_message = ai_service.save_dialogue_message(
                    user=user,
                    content=result['response'],
                    sender_type='ai',
                    message_type='voice_response' if result.get('has_voice') else 'text',
                    audio_file=result.get('audio_content')
                )
                
                # Формируем ответ
                response_data = {
                    'response': result['response'],
                    'type': result['type'],
                    'has_voice': result.get('has_voice', False)
                }
                
                # Добавляем URL аудиофайла если есть
                if result.get('has_voice') and ai_message.audio_file:
                    response_data['audio_url'] = request.build_absolute_uri(ai_message.audio_file.url)
                
                return Response(response_data)
            else:
                return Response({
                    'error': result.get('error', 'Ошибка обработки сообщения')
                }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        else:
            return Response({
                'error': 'Не указано сообщение или файл'
            }, status=status.HTTP_400_BAD_REQUEST)
            
    except Exception as e:
        print(f"Error in ai_diagnosis: {e}")
        return Response({
            'error': 'Произошла внутренняя ошибка сервера'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def ai_dialogue_history(request):
    """Получение истории диалогов с AI"""
    try:
        user = request.user
        
        # Получаем активный диалог пользователя
        from .models import AIDialogue
        
        try:
            dialogue = AIDialogue.objects.get(user=user, is_active=True)
            messages = dialogue.messages.all()
            
            messages_data = []
            for msg in messages:
                messages_data.append({
                    'id': msg.id,
                    'sender_type': msg.sender_type,
                    'message_type': msg.message_type,
                    'content': msg.content,
                    'timestamp': msg.timestamp.isoformat(),
                })
            
            return Response({
                'dialogue_id': dialogue.id,
                'messages': messages_data
            })
            
        except AIDialogue.DoesNotExist:
            # Если диалога нет, возвращаем пустой список
            return Response({
                'dialogue_id': None,
                'messages': []
            })
            
    except Exception:
        return Response({'error': 'Ошибка получения истории диалогов'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def send_support_message(request):
    """Получает сообщение поддержки от авторизованного пользователя и пересылает в Telegram группу"""
    try:
        user = request.user
        message_text = request.data.get('message', '').strip()
        if not message_text:
            return Response({'error': 'Сообщение не может быть пустым'}, status=status.HTTP_400_BAD_REQUEST)

        # Собираем информацию о пользователе
        profile_data = {}
        try:
            profile = UserProfile.objects.get(user=user)
            profile_data = {
                'specialization': getattr(profile, 'specialization', None),
                'phone': getattr(profile, 'phone', None),
                'region': getattr(profile.region, 'name', None) if getattr(profile, 'region', None) else None,
                'city': getattr(profile.city, 'name', None) if getattr(profile, 'city', None) else None,
            }
        except UserProfile.DoesNotExist:
            pass

        # Подготовка текста для Telegram (экранируем спецсимволы)
        def esc(s):
            return html.escape(str(s or ''))

        tg_lines = [
            f"🆘 Новое обращение в поддержку",
            f"👤 Пользователь: {esc(user.full_name)} (ID: {user.id})",
            f"📧 Email: {esc(user.email)}",
            f"📱 Phone: {esc(profile_data.get('phone'))}",
            f"🌍 Регион: {esc(profile_data.get('region'))}, Город: {esc(profile_data.get('city'))}",
            f"🔖 Роль: {esc(user.role)}",
            "",
            f"✉️ Сообщение:\n{esc(message_text)}",
        ]

        tg_text = "\n".join(tg_lines)

        bot_token = getattr(settings, 'TELEGRAM_BOT_TOKEN', '')
        chat_id = getattr(settings, 'TELEGRAM_SUPPORT_CHAT_ID', '')
        if not bot_token or not chat_id:
            return Response({'error': 'Не настроены параметры Telegram'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        # Отправляем в Telegram
        try:
            resp = requests.post(
                f"https://api.telegram.org/bot{bot_token}/sendMessage",
                json={
                    'chat_id': chat_id,
                    'text': tg_text,
                    'parse_mode': 'HTML',
                    'disable_web_page_preview': True,
                },
                timeout=5
            )
        except Exception:
            return Response({'error': 'Ошибка отправки в Telegram'}, status=status.HTTP_502_BAD_GATEWAY)

        if resp.status_code != 200:
            return Response({'error': 'Не удалось отправить сообщение в Telegram'}, status=status.HTTP_502_BAD_GATEWAY)

        return Response({'message': 'Сообщение отправлено в поддержку'}, status=status.HTTP_200_OK)
    except Exception:
        return Response({'error': 'Внутренняя ошибка'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def protected_media(request, subpath):
    """Выдаёт файл из MEDIA только админам; остальным 403. Путь указывается относительно MEDIA_ROOT."""
    user = request.user
    if not (user.is_staff or user.is_superuser or getattr(user, 'role', '') == 'admin'):
        return Response({'error': 'Доступ запрещен'}, status=status.HTTP_403_FORBIDDEN)

    # Нормализуем путь, не даём выходить выше MEDIA_ROOT
    from django.conf import settings as dj_settings
    import os
    safe_subpath = os.path.normpath(subpath).lstrip('/\\')
    abs_path = os.path.join(dj_settings.MEDIA_ROOT, safe_subpath)
    if not abs_path.startswith(str(dj_settings.MEDIA_ROOT)):
        return Response({'error': 'Некорректный путь'}, status=status.HTTP_400_BAD_REQUEST)

    if not os.path.exists(abs_path):
        raise Http404()

    # Отдаём файл безопасно
    return FileResponse(open(abs_path, 'rb'))

# APPOINTMENT BOOKING SYSTEM

from .models import Appointment, DoctorSchedule, MedicalRecord, VitalSigns, Notification, UserProfile, Review
from datetime import datetime, date, timedelta

@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated])
def appointments(request):
    """Get all appointments or create a new one"""
    if request.method == 'GET':
        user = request.user
        if user.role == 'patient':
            appts = Appointment.objects.filter(patient=user).select_related('doctor', 'doctor__profile')
        elif user.role == 'doctor':
            appts = Appointment.objects.filter(doctor=user).select_related('patient', 'patient__profile')
        else:
            appts = Appointment.objects.all().select_related('patient', 'doctor')

        data = []
        for a in appts:
            data.append({
                'id': a.id,
                'patient': {
                    'id': a.patient.id,
                    'full_name': a.patient.full_name,
                    'email': a.patient.email,
                    'avatar': a.patient.avatar,
                },
                'doctor': {
                    'id': a.doctor.id,
                    'full_name': a.doctor.full_name,
                    'email': a.doctor.email,
                    'avatar': a.doctor.avatar,
                    'specialization': getattr(a.doctor.profile, 'specialization', None) if hasattr(a.doctor, 'profile') else None,
                },
                'appointment_date': str(a.appointment_date),
                'appointment_time': str(a.appointment_time),
                'duration_minutes': a.duration_minutes,
                'status': a.status,
                'reason': a.reason,
                'notes': a.notes,
                'doctor_notes': a.doctor_notes,
                'is_upcoming': a.is_upcoming,
                'created_at': a.created_at.isoformat(),
            })
        return Response(data)

    if request.method == 'POST':
        if request.user.role != 'patient':
            return Response({'error': 'Only patients can book appointments'}, status=403)

        doctor_id = request.data.get('doctor_id')
        appointment_date = request.data.get('appointment_date')
        appointment_time = request.data.get('appointment_time')
        reason = request.data.get('reason', '')
        duration_minutes = request.data.get('duration_minutes', 30)

        if not all([doctor_id, appointment_date, appointment_time]):
            return Response({'error': 'doctor_id, appointment_date and appointment_time are required'}, status=400)

        try:
            doctor = User.objects.get(id=doctor_id, role='doctor')
        except User.DoesNotExist:
            return Response({'error': 'Doctor not found'}, status=404)

        # Check if slot is already taken
        if Appointment.objects.filter(
            doctor=doctor,
            appointment_date=appointment_date,
            appointment_time=appointment_time,
            status__in=['pending', 'confirmed']
        ).exists():
            return Response({'error': 'This time slot is already booked'}, status=400)

        # Check date is not in the past
        try:
            appt_date = datetime.strptime(appointment_date, '%Y-%m-%d').date()
            if appt_date < date.today():
                return Response({'error': 'Cannot book appointments in the past'}, status=400)
        except ValueError:
            return Response({'error': 'Invalid date format. Use YYYY-MM-DD'}, status=400)

        appointment = Appointment.objects.create(
            patient=request.user,
            doctor=doctor,
            appointment_date=appointment_date,
            appointment_time=appointment_time,
            duration_minutes=duration_minutes,
            reason=reason,
            status='pending',
        )

        send_appointment_confirmation_email(appointment)
        send_appointment_sms(appointment, event='booked')

        # Push notification to doctor
        send_push_notification(
            user=doctor,
            title='New Appointment Booked',
            body=f'{request.user.full_name} booked an appointment on {appointment_date} at {appointment_time}.',
            data={'appointment_id': str(appointment.id), 'url': f'/appointments/{appointment.id}/'},
            notification_type='appointment_booked',
        )

        return Response({

            'id': appointment.id,
            'message': 'Appointment booked successfully',
            'status': appointment.status,
            'appointment_date': str(appointment.appointment_date),
            'appointment_time': str(appointment.appointment_time),
        }, status=201)


@api_view(['GET', 'PATCH', 'DELETE'])
@permission_classes([IsAuthenticated])
def appointment_detail(request, appointment_id):
    """Get, update or cancel a specific appointment"""
    try:
        appointment = Appointment.objects.get(id=appointment_id)
    except Appointment.DoesNotExist:
        return Response({'error': 'Appointment not found'}, status=404)

    # Only patient, doctor or admin can access
    if request.user not in [appointment.patient, appointment.doctor] and request.user.role != 'admin':
        return Response({'error': 'Permission denied'}, status=403)

    if request.method == 'GET':
        return Response({
            'id': appointment.id,
            'patient': {
                'id': appointment.patient.id,
                'full_name': appointment.patient.full_name,
                'email': appointment.patient.email,
                'avatar': appointment.patient.avatar,
            },
            'doctor': {
                'id': appointment.doctor.id,
                'full_name': appointment.doctor.full_name,
                'specialization': getattr(appointment.doctor.profile, 'specialization', None) if hasattr(appointment.doctor, 'profile') else None,
            },
            'appointment_date': str(appointment.appointment_date),
            'appointment_time': str(appointment.appointment_time),
            'duration_minutes': appointment.duration_minutes,
            'status': appointment.status,
            'reason': appointment.reason,
            'notes': appointment.notes,
            'doctor_notes': appointment.doctor_notes,
            'is_upcoming': appointment.is_upcoming,
            'created_at': appointment.created_at.isoformat(),
        })

    if request.method == 'PATCH':
        # Doctor can confirm or add notes
        if request.user == appointment.doctor:
            if 'status' in request.data:
                new_status = request.data['status']
                if new_status in ['confirmed', 'completed', 'no_show']:
                    appointment.status = new_status
            if 'doctor_notes' in request.data:
                appointment.doctor_notes = request.data['doctor_notes']
            appointment.save()
            return Response({'message': 'Appointment updated', 'status': appointment.status})

        # Patient can update reason/notes
        if request.user == appointment.patient:
            if 'reason' in request.data:
                appointment.reason = request.data['reason']
            if 'notes' in request.data:
                appointment.notes = request.data['notes']
            appointment.save()
            return Response({'message': 'Appointment updated'})

        return Response({'error': 'Permission denied'}, status=403)

    if request.method == 'DELETE':
        # Both patient and doctor can cancel
        if appointment.status in ['completed', 'cancelled']:
            return Response({'error': 'Cannot cancel a completed or already cancelled appointment'}, status=400)

        appointment.status = 'cancelled'
        appointment.cancelled_by = request.user
        appointment.cancellation_reason = request.data.get('reason', '')
        appointment.save()
        return Response({'message': 'Appointment cancelled successfully'})

@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated])
def doctor_schedule(request):
    """Get or set doctor's weekly schedule"""
    if request.user.role != 'doctor':
        return Response({'error': 'Only doctors can manage schedules'}, status=403)

    if request.method == 'GET':
        schedules = DoctorSchedule.objects.filter(doctor=request.user)
        data = [{
            'id': s.id,
            'day_of_week': s.day_of_week,
            'day_name': s.get_day_of_week_display(),
            'start_time': str(s.start_time),
            'end_time': str(s.end_time),
            'is_available': s.is_available,
            'slot_duration_minutes': s.slot_duration_minutes,
        } for s in schedules]
        return Response(data)

    if request.method == 'POST':
        day_of_week = request.data.get('day_of_week')
        start_time = request.data.get('start_time')
        end_time = request.data.get('end_time')
        is_available = request.data.get('is_available', True)
        slot_duration = request.data.get('slot_duration_minutes', 30)

        if day_of_week is None or not start_time or not end_time:
            return Response({'error': 'day_of_week, start_time and end_time are required'}, status=400)

        schedule, created = DoctorSchedule.objects.update_or_create(
            doctor=request.user,
            day_of_week=day_of_week,
            defaults={
                'start_time': start_time,
                'end_time': end_time,
                'is_available': is_available,
                'slot_duration_minutes': slot_duration,
            }
        )

        return Response({
            'message': 'Schedule saved successfully',
            'day_name': schedule.get_day_of_week_display(),
            'start_time': str(schedule.start_time),
            'end_time': str(schedule.end_time),
            'is_available': schedule.is_available,
        }, status=201 if created else 200)

# MEDICAL RECORDS SYSTEM

@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated])
def medical_records(request):
    """Get all medical records or create a new one"""
    if request.method == 'GET':
        user = request.user
        if user.role == 'patient':
            records = MedicalRecord.objects.filter(
                patient=user, is_visible_to_patient=True
            ).select_related('doctor', 'doctor__profile').prefetch_related('prescriptions')
        elif user.role == 'doctor':
            records = MedicalRecord.objects.filter(
                doctor=user
            ).select_related('patient', 'patient__profile').prefetch_related('prescriptions')
        else:
            records = MedicalRecord.objects.all().select_related('patient', 'doctor').prefetch_related('prescriptions')

        data = []
        for r in records:
            data.append({
                'id': r.id,
                'record_type': r.record_type,
                'title': r.title,
                'description': r.description,
                'diagnosis_code': r.diagnosis_code,
                'medications': r.medications,
                'patient': {'id': r.patient.id, 'full_name': r.patient.full_name},
                'doctor': {
                    'id': r.doctor.id,
                    'full_name': r.doctor.full_name,
                    'specialization': getattr(r.doctor.profile, 'specialization', None) if hasattr(r.doctor, 'profile') else None,
                },
                'consultation_id': r.consultation_id,
                'appointment_id': r.appointment_id,
                'created_at': r.created_at.isoformat(),
            })
        return Response(data)

    if request.method == 'POST':
        if request.user.role != 'doctor':
            return Response({'error': 'Only doctors can create medical records'}, status=403)

        required = ['patient_id', 'record_type', 'title', 'description']
        for field in required:
            if not request.data.get(field):
                return Response({'error': f'{field} is required'}, status=400)

        try:
            patient = User.objects.get(id=request.data['patient_id'], role='patient')
        except User.DoesNotExist:
            return Response({'error': 'Patient not found'}, status=404)

        record = MedicalRecord.objects.create(
            patient=patient,
            doctor=request.user,
            record_type=request.data['record_type'],
            title=request.data['title'],
            description=request.data['description'],
            diagnosis_code=request.data.get('diagnosis_code', ''),
            medications=request.data.get('medications', []),
            consultation_id=request.data.get('consultation_id'),
            appointment_id=request.data.get('appointment_id'),
            is_visible_to_patient=request.data.get('is_visible_to_patient', True),
        )
        return Response({'id': record.id, 'message': 'Medical record created'}, status=201)


@api_view(['GET', 'PATCH', 'DELETE'])
@permission_classes([IsAuthenticated])
def medical_record_detail(request, record_id):
    """Get, update or delete a medical record"""
    try:
        record = MedicalRecord.objects.get(id=record_id)
    except MedicalRecord.DoesNotExist:
        return Response({'error': 'Record not found'}, status=404)

    if request.user not in [record.patient, record.doctor] and request.user.role != 'admin':
        return Response({'error': 'Permission denied'}, status=403)

    if request.method == 'GET':
        prescriptions = [{
            'id': p.id,
            'medication_name': p.medication_name,
            'dosage': p.dosage,
            'frequency': p.frequency,
            'duration_days': p.duration_days,
            'instructions': p.instructions,
            'status': p.status,
            'prescribed_at': p.prescribed_at.isoformat(),
        } for p in record.prescriptions.all()]

        return Response({
            'id': record.id,
            'record_type': record.record_type,
            'title': record.title,
            'description': record.description,
            'diagnosis_code': record.diagnosis_code,
            'medications': record.medications,
            'attachments': record.attachments,
            'patient': {'id': record.patient.id, 'full_name': record.patient.full_name},
            'doctor': {'id': record.doctor.id, 'full_name': record.doctor.full_name},
            'prescriptions': prescriptions,
            'created_at': record.created_at.isoformat(),
            'updated_at': record.updated_at.isoformat(),
        })

    if request.method == 'PATCH':
        if request.user != record.doctor:
            return Response({'error': 'Only the doctor can edit this record'}, status=403)
        for field in ['title', 'description', 'diagnosis_code', 'medications', 'is_visible_to_patient']:
            if field in request.data:
                setattr(record, field, request.data[field])
        record.save()
        return Response({'message': 'Record updated'})

    if request.method == 'DELETE':
        if request.user != record.doctor and request.user.role != 'admin':
            return Response({'error': 'Permission denied'}, status=403)
        record.delete()
        return Response({'message': 'Record deleted'})


@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated])
def vital_signs(request, patient_id=None):
    """Get or record vital signs"""
    if request.method == 'GET':
        pid = patient_id or request.user.id
        if request.user.id != pid and request.user.role not in ['doctor', 'admin']:
            return Response({'error': 'Permission denied'}, status=403)
        vitals = VitalSigns.objects.filter(patient_id=pid)[:20]
        data = [{
            'id': v.id,
            'blood_pressure': f"{v.blood_pressure_systolic}/{v.blood_pressure_diastolic}" if v.blood_pressure_systolic else None,
            'heart_rate': v.heart_rate,
            'temperature': float(v.temperature) if v.temperature else None,
            'weight_kg': float(v.weight_kg) if v.weight_kg else None,
            'height_cm': float(v.height_cm) if v.height_cm else None,
            'oxygen_saturation': v.oxygen_saturation,
            'bmi': v.bmi,
            'notes': v.notes,
            'recorded_at': v.recorded_at.isoformat(),
        } for v in vitals]
        return Response(data)

    if request.method == 'POST':
        target_patient = request.user
        if request.data.get('patient_id') and request.user.role in ['doctor', 'admin']:
            try:
                target_patient = User.objects.get(id=request.data['patient_id'])
            except User.DoesNotExist:
                return Response({'error': 'Patient not found'}, status=404)

        vital = VitalSigns.objects.create(
            patient=target_patient,
            recorded_by=request.user,
            blood_pressure_systolic=request.data.get('blood_pressure_systolic'),
            blood_pressure_diastolic=request.data.get('blood_pressure_diastolic'),
            heart_rate=request.data.get('heart_rate'),
            temperature=request.data.get('temperature'),
            weight_kg=request.data.get('weight_kg'),
            height_cm=request.data.get('height_cm'),
            oxygen_saturation=request.data.get('oxygen_saturation'),
            notes=request.data.get('notes', ''),
        )
        return Response({'id': vital.id, 'bmi': vital.bmi, 'message': 'Vitals recorded'}, status=201)

# NOTIFICATIONS SYSTEM

def create_notification(recipient, notification_type, title, message, sender=None, link=None, data=None):
    """Helper function to create a notification"""
    Notification.objects.create(
        recipient=recipient,
        sender=sender,
        notification_type=notification_type,
        title=title,
        message=message,
        link=link or '',
        data=data or {},
    )


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def notifications(request):
    """Get all notifications for the current user"""
    notifs = Notification.objects.filter(
        recipient=request.user
    ).select_related('sender')[:50]
    unread_count = Notification.objects.filter(recipient=request.user, is_read=False).count()

    data = [{
        'id': n.id,
        'type': n.notification_type,
        'title': n.title,
        'message': n.message,
        'is_read': n.is_read,
        'link': n.link,
        'data': n.data,
        'created_at': n.created_at.isoformat(),
    } for n in notifs]

    return Response({
        'notifications': data,
        'unread_count': unread_count,
    })


@api_view(['PATCH'])
@permission_classes([IsAuthenticated])
def mark_notification_read(request, notification_id):
    """Mark a single notification as read"""
    try:
        notif = Notification.objects.get(id=notification_id, recipient=request.user)
        notif.mark_as_read()
        return Response({'message': 'Marked as read'})
    except Notification.DoesNotExist:
        return Response({'error': 'Notification not found'}, status=404)


@api_view(['PATCH'])
@permission_classes([IsAuthenticated])
def mark_all_notifications_read(request):
    """Mark all notifications as read"""
    Notification.objects.filter(
        recipient=request.user, is_read=False
    ).update(is_read=True, read_at=timezone.now())
    return Response({'message': 'All notifications marked as read'})


@api_view(['DELETE'])
@permission_classes([IsAuthenticated])
def delete_notification(request, notification_id):
    """Delete a notification"""
    try:
        notif = Notification.objects.get(id=notification_id, recipient=request.user)
        notif.delete()
        return Response({'message': 'Notification deleted'})
    except Notification.DoesNotExist:
        return Response({'error': 'Notification not found'}, status=404) 

# PATIENT DASHBOARD API

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def patient_dashboard(request):
    """Complete dashboard summary for a patient"""
    if request.user.role != 'patient':
        return Response({'error': 'Only patients can access this dashboard'}, status=403)

    user = request.user
    today = date.today()

    # Upcoming appointments
    upcoming_appointments = Appointment.objects.filter(
        patient=user,
        status__in=['pending', 'confirmed'],
        appointment_date__gte=today
    ).select_related('doctor', 'doctor__profile').order_by('appointment_date', 'appointment_time')[:5]

    # Recent medical records
    recent_records = MedicalRecord.objects.filter(
        patient=user,
        is_visible_to_patient=True
    ).select_related('doctor').order_by('-created_at')[:5]

    # Active prescriptions
    active_prescriptions = Prescription.objects.filter(
        patient=user,
        status='active'
    ).select_related('doctor', 'medical_record').order_by('-prescribed_at')[:5]

    # Latest vital signs
    latest_vitals = VitalSigns.objects.filter(patient=user).order_by('-recorded_at').first()

    # Unread notifications
    unread_notifications = Notification.objects.filter(
        recipient=user, is_read=False
    ).order_by('-created_at')[:5]

    # Stats
    total_consultations = user.patient_consultations.count()
    total_appointments = user.patient_appointments.count()
    total_records = user.medical_records.filter(is_visible_to_patient=True).count()
    unread_count = Notification.objects.filter(recipient=user, is_read=False).count()

    return Response({
        'user': {
            'id': user.id,
            'full_name': user.full_name,
            'email': user.email,
            'avatar': user.avatar,
        },
        'stats': {
            'total_consultations': total_consultations,
            'total_appointments': total_appointments,
            'total_medical_records': total_records,
            'unread_notifications': unread_count,
        },
        'upcoming_appointments': [{
            'id': a.id,
            'doctor_name': a.doctor.full_name,
            'doctor_avatar': a.doctor.avatar,
            'specialization': getattr(a.doctor.profile, 'specialization', None) if hasattr(a.doctor, 'profile') else None,
            'appointment_date': str(a.appointment_date),
            'appointment_time': str(a.appointment_time),
            'status': a.status,
            'reason': a.reason,
        } for a in upcoming_appointments],
        'recent_medical_records': [{
            'id': r.id,
            'record_type': r.record_type,
            'title': r.title,
            'doctor_name': r.doctor.full_name,
            'created_at': r.created_at.isoformat(),
        } for r in recent_records],
        'active_prescriptions': [{
            'id': p.id,
            'medication_name': p.medication_name,
            'dosage': p.dosage,
            'frequency': p.frequency,
            'duration_days': p.duration_days,
            'doctor_name': p.doctor.full_name,
            'prescribed_at': p.prescribed_at.isoformat(),
            'expires_at': str(p.expires_at) if p.expires_at else None,
        } for p in active_prescriptions],
        'latest_vitals': {
            'blood_pressure': f"{latest_vitals.blood_pressure_systolic}/{latest_vitals.blood_pressure_diastolic}" if latest_vitals and latest_vitals.blood_pressure_systolic else None,
            'heart_rate': latest_vitals.heart_rate if latest_vitals else None,
            'temperature': float(latest_vitals.temperature) if latest_vitals and latest_vitals.temperature else None,
            'weight_kg': float(latest_vitals.weight_kg) if latest_vitals and latest_vitals.weight_kg else None,
            'bmi': latest_vitals.bmi if latest_vitals else None,
            'recorded_at': latest_vitals.recorded_at.isoformat() if latest_vitals else None,
        },
        'unread_notifications': [{
            'id': n.id,
            'type': n.notification_type,
            'title': n.title,
            'message': n.message,
            'created_at': n.created_at.isoformat(),
        } for n in unread_notifications],
    })


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def doctor_dashboard(request):
    """Complete dashboard summary for a doctor"""
    if request.user.role != 'doctor':
        return Response({'error': 'Only doctors can access this dashboard'}, status=403)

    user = request.user
    today = date.today()

    # Today's appointments
    todays_appointments = Appointment.objects.filter(
        doctor=user,
        appointment_date=today,
        status__in=['pending', 'confirmed']
    ).select_related('patient', 'patient__profile').order_by('appointment_time')

    # Upcoming appointments (next 7 days)
    upcoming_appointments = Appointment.objects.filter(
        doctor=user,
        status__in=['pending', 'confirmed'],
        appointment_date__gt=today,
        appointment_date__lte=today + timedelta(days=7)
    ).select_related('patient').order_by('appointment_date', 'appointment_time')[:10]

    # Recent patients (distinct patients from consultations)
    recent_consultations = user.doctor_consultations.filter(
        status='completed'
    ).select_related('patient').order_by('-completed_at')[:5]

    # Unread notifications
    unread_notifications = Notification.objects.filter(
        recipient=user, is_read=False
    ).order_by('-created_at')[:5]

    # Stats
    total_patients = user.doctor_consultations.values('patient').distinct().count()
    total_consultations = user.doctor_consultations.count()
    total_appointments = user.doctor_appointments.count()
    pending_appointments = user.doctor_appointments.filter(status='pending').count()
    unread_count = Notification.objects.filter(recipient=user, is_read=False).count()

    return Response({
        'user': {
            'id': user.id,
            'full_name': user.full_name,
            'email': user.email,
            'avatar': user.avatar,
            'specialization': getattr(user.profile, 'specialization', None) if hasattr(user, 'profile') else None,
        },
        'stats': {
            'total_patients': total_patients,
            'total_consultations': total_consultations,
            'total_appointments': total_appointments,
            'pending_appointments': pending_appointments,
            'unread_notifications': unread_count,
        },
        'todays_appointments': [{
            'id': a.id,
            'patient_name': a.patient.full_name,
            'patient_avatar': a.patient.avatar,
            'appointment_time': str(a.appointment_time),
            'duration_minutes': a.duration_minutes,
            'status': a.status,
            'reason': a.reason,
        } for a in todays_appointments],
        'upcoming_appointments': [{
            'id': a.id,
            'patient_name': a.patient.full_name,
            'appointment_date': str(a.appointment_date),
            'appointment_time': str(a.appointment_time),
            'status': a.status,
        } for a in upcoming_appointments],
        'recent_patients': [{
            'id': c.patient.id,
            'full_name': c.patient.full_name,
            'avatar': c.patient.avatar,
            'last_consultation': c.completed_at.isoformat() if c.completed_at else None,
        } for c in recent_consultations],
        'unread_notifications': [{
            'id': n.id,
            'type': n.notification_type,
            'title': n.title,
            'message': n.message,
            'created_at': n.created_at.isoformat(),
        } for n in unread_notifications],
    })

# DOCTOR SEARCH & FILTERING

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def search_doctors(request):
    """Search and filter doctors by specialization, city, language, name"""
    queryset = User.objects.filter(
        role='doctor',
        is_active=True
    ).select_related('profile', 'profile__city', 'profile__region').prefetch_related(
        'schedules', 'received_reviews', 'doctor_consultations'
    ) 

    # Filter by name
    name = request.query_params.get('name')
    if name:
        queryset = queryset.filter(
            models.Q(first_name__icontains=name) |
            models.Q(last_name__icontains=name)
        )

    # Filter by specialization
    specialization = request.query_params.get('specialization')
    if specialization:
        queryset = queryset.filter(
            profile__specialization__icontains=specialization
        )

    # Filter by city
    city = request.query_params.get('city')
    if city:
        queryset = queryset.filter(
            profile__city__name__icontains=city
        )

    # Filter by region
    region = request.query_params.get('region')
    if region:
        queryset = queryset.filter(
            profile__region__name__icontains=region
        )

    # Filter by language
    language = request.query_params.get('language')
    if language:
        queryset = queryset.filter(
            profile__languages__icontains=language
        )

    # Filter by availability (has schedule set up)
    available_only = request.query_params.get('available_only')
    if available_only == 'true':
        queryset = queryset.filter(schedules__is_available=True).distinct()

    # Build response
    data = []
    for doctor in queryset:
        profile = getattr(doctor, 'profile', None)

        # Get average rating if reviews exist
        avg_rating = None
        review_count = 0
        if hasattr(doctor, 'received_reviews'):
            reviews = doctor.received_reviews.all()
            review_count = reviews.count()
            if review_count > 0:
                avg_rating = round(sum(r.rating for r in reviews) / review_count, 1)

        # Get next available appointment slot
        has_schedule = doctor.schedules.filter(is_available=True).exists()

        data.append({
            'id': doctor.id,
            'full_name': doctor.full_name,
            'avatar': doctor.avatar,
            'email': doctor.email,
            'specialization': profile.specialization if profile else None,
            'experience': profile.experience if profile else None,
            'education': profile.education if profile else None,
            'languages': profile.languages if profile else [],
            'city': profile.city.name if profile and profile.city else None,
            'region': profile.region.name if profile and profile.region else None,
            'license_number': profile.license_number if profile else None,
            'additional_info': profile.additional_info if profile else None,
            'avg_rating': avg_rating,
            'review_count': review_count,
            'has_schedule': has_schedule,
            'total_consultations': doctor.doctor_consultations.filter(status='completed').count(),
        })

    # Sort by total consultations (most experienced first)
    data.sort(key=lambda x: x['total_consultations'], reverse=True)

    # Pagination
    page = int(request.query_params.get('page', 1))
    page_size = int(request.query_params.get('page_size', 20))
    start = (page - 1) * page_size
    end = start + page_size
    total = len(data)
    paginated = data[start:end]

    return Response({
        'count': total,
        'page': page,
        'page_size': page_size,
        'total_pages': (total + page_size - 1) // page_size,
        'doctors': paginated,
    })

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def doctor_profile_detail(request, doctor_id):
    """Get full profile of a specific doctor"""
    try:
        doctor = User.objects.get(id=doctor_id, role='doctor')
    except User.DoesNotExist:
        return Response({'error': 'Doctor not found'}, status=404)

    profile = getattr(doctor, 'profile', None)

    # Get schedule
    schedules = [{
        'day_of_week': s.day_of_week,
        'day_name': s.get_day_of_week_display(),
        'start_time': str(s.start_time),
        'end_time': str(s.end_time),
        'is_available': s.is_available,
        'slot_duration_minutes': s.slot_duration_minutes,
    } for s in doctor.schedules.filter(is_available=True)]

    # Get completed consultations count
    total_consultations = doctor.doctor_consultations.filter(status='completed').count()

    return Response({
        'id': doctor.id,
        'full_name': doctor.full_name,
        'avatar': doctor.avatar,
        'email': doctor.email,
        'specialization': profile.specialization if profile else None,
        'experience': profile.experience if profile else None,
        'education': profile.education if profile else None,
        'languages': profile.languages if profile else [],
        'city': profile.city.name if profile and profile.city else None,
        'region': profile.region.name if profile and profile.region else None,
        'license_number': profile.license_number if profile else None,
        'additional_info': profile.additional_info if profile else None,
        'total_consultations': total_consultations,
        'schedule': schedules,
    })


@api_view(['GET'])
def specializations_list(request):
    """Get all unique specializations for filter dropdown"""
    cache_key = 'specializations_list'
    cached = cache.get(cache_key)
    if cached:
        return Response(cached)

    from django.db.models import Count
    specs = UserProfile.objects.filter(
        user__role='doctor',
        user__is_active=True,
        specialization__isnull=False
    ).exclude(
        specialization=''
    ).values('specialization').annotate(
        count=Count('specialization')
    ).order_by('-count')

    data = [{'specialization': s['specialization'], 'doctor_count': s['count']} for s in specs]
    cache.set(cache_key, data, 3600)  # Cache for 1 hour
    return Response(data)

# REVIEWS & RATINGS SYSTEM

@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated])
def doctor_reviews(request, doctor_id):
    """Get all reviews for a doctor or submit a new review"""

    try:
        doctor = User.objects.get(id=doctor_id, role='doctor')
    except User.DoesNotExist:
        return Response({'error': 'Doctor not found'}, status=404)

    if request.method == 'GET':
        reviews = Review.objects.filter(
            doctor=doctor, is_visible=True
        ).select_related('patient')

        # Calculate stats
        total = reviews.count()
        avg_rating = 0
        rating_breakdown = {1: 0, 2: 0, 3: 0, 4: 0, 5: 0}

        if total > 0:
            total_score = sum(r.rating for r in reviews)
            avg_rating = round(total_score / total, 1)
            for r in reviews:
                rating_breakdown[r.rating] += 1

        data = []
        for r in reviews:
            data.append({
                'id': r.id,
                'rating': r.rating,
                'comment': r.comment,
                'is_anonymous': r.is_anonymous,
                'patient_name': 'Anonymous' if r.is_anonymous else r.patient.full_name,
                'patient_avatar': None if r.is_anonymous else r.patient.avatar,
                'created_at': r.created_at.isoformat(),
            })

        return Response({
            'doctor_id': doctor_id,
            'avg_rating': avg_rating,
            'total_reviews': total,
            'rating_breakdown': rating_breakdown,
            'reviews': data,
        })

    if request.method == 'POST':
        if request.user.role != 'patient':
            return Response({'error': 'Only patients can submit reviews'}, status=403)

        rating = request.data.get('rating')
        if not rating or int(rating) not in [1, 2, 3, 4, 5]:
            return Response({'error': 'Rating must be between 1 and 5'}, status=400)

        consultation_id = request.data.get('consultation_id')

        # Check if patient already reviewed this doctor for this consultation
        if consultation_id:
            if Review.objects.filter(
                patient=request.user,
                doctor=doctor,
                consultation_id=consultation_id
            ).exists():
                return Response({'error': 'You have already reviewed this doctor for this consultation'}, status=400)
        else:
            # Allow one review per doctor if no consultation specified
            if Review.objects.filter(
                patient=request.user,
                doctor=doctor,
                consultation__isnull=True
            ).exists():
                return Response({'error': 'You have already reviewed this doctor'}, status=400)

        review = Review.objects.create(
            patient=request.user,
            doctor=doctor,
            rating=int(rating),
            comment=request.data.get('comment', ''),
            is_anonymous=request.data.get('is_anonymous', False),
            consultation_id=consultation_id,
            appointment_id=request.data.get('appointment_id'),
        )

        # Send notification to doctor
        create_notification(
            recipient=doctor,
            sender=request.user,
            notification_type='general',
            title='New Review Received',
            message=f'You received a {rating}-star review from a patient.',
            link=f'/doctor/reviews/',
        )

        return Response({
            'id': review.id,
            'message': 'Review submitted successfully',
            'rating': review.rating,
        }, status=201)


@api_view(['PATCH', 'DELETE'])
@permission_classes([IsAuthenticated])
def review_detail(request, review_id):
    """Edit or delete a review"""
    try:
        review = Review.objects.get(id=review_id)
    except Review.DoesNotExist:
        return Response({'error': 'Review not found'}, status=404)

    if request.user != review.patient and request.user.role != 'admin':
        return Response({'error': 'Permission denied'}, status=403)

    if request.method == 'PATCH':
        if 'rating' in request.data:
            new_rating = int(request.data['rating'])
            if new_rating not in [1, 2, 3, 4, 5]:
                return Response({'error': 'Rating must be between 1 and 5'}, status=400)
            review.rating = new_rating
        if 'comment' in request.data:
            review.comment = request.data['comment']
        if 'is_anonymous' in request.data:
            review.is_anonymous = request.data['is_anonymous']
        review.save()
        return Response({'message': 'Review updated'})

    if request.method == 'DELETE':
        review.delete()
        return Response({'message': 'Review deleted'})
    


# ============================================
# ADMIN PANEL & DOCTOR APPROVAL SYSTEM
# ============================================

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def admin_dashboard(request):
    """Admin overview stats"""
    if request.user.role != 'admin':
        return Response({'error': 'Admin access required'}, status=403)

    today = date.today()

    total_users = User.objects.count()
    total_patients = User.objects.filter(role='patient').count()
    total_doctors = User.objects.filter(role='doctor').count()
    pending_doctors = User.objects.filter(role='doctor', is_active=False).count()
    total_consultations = Consultation.objects.count()
    total_appointments = Appointment.objects.count()
    today_appointments = Appointment.objects.filter(appointment_date=today).count()
    total_reviews = Review.objects.count()

    recent_users = User.objects.order_by('-date_joined')[:5]
    pending_doctor_list = User.objects.filter(
        role='doctor', is_active=False
    ).select_related('profile').order_by('-date_joined')[:10]

    return Response({
        'stats': {
            'total_users': total_users,
            'total_patients': total_patients,
            'total_doctors': total_doctors,
            'pending_doctors': pending_doctors,
            'total_consultations': total_consultations,
            'total_appointments': total_appointments,
            'today_appointments': today_appointments,
            'total_reviews': total_reviews,
        },
        'recent_users': [{
            'id': u.id,
            'full_name': u.full_name,
            'email': u.email,
            'role': u.role,
            'is_active': u.is_active,
            'date_joined': u.date_joined.isoformat(),
        } for u in recent_users],
        'pending_doctors': [{
            'id': d.id,
            'full_name': d.full_name,
            'email': d.email,
            'specialization': getattr(d.profile, 'specialization', None) if hasattr(d, 'profile') else None,
            'license_number': getattr(d.profile, 'license_number', None) if hasattr(d, 'profile') else None,
            'date_joined': d.date_joined.isoformat(),
        } for d in pending_doctor_list],
    })


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def admin_users_list(request):
    """List all users with filters"""
    if request.user.role != 'admin':
        return Response({'error': 'Admin access required'}, status=403)

    queryset = User.objects.all().order_by('-date_joined')

    role = request.query_params.get('role')
    if role:
        queryset = queryset.filter(role=role)

    is_active = request.query_params.get('is_active')
    if is_active is not None:
        queryset = queryset.filter(is_active=is_active == 'true')

    search = request.query_params.get('search')
    if search:
        queryset = queryset.filter(
            models.Q(first_name__icontains=search) |
            models.Q(last_name__icontains=search) |
            models.Q(email__icontains=search)
        )

    page = int(request.query_params.get('page', 1))
    page_size = int(request.query_params.get('page_size', 20))
    start = (page - 1) * page_size
    end = start + page_size

    total = queryset.count()
    users = queryset[start:end]

    data = [{
        'id': u.id,
        'full_name': u.full_name,
        'email': u.email,
        'role': u.role,
        'is_active': u.is_active,
        'date_joined': u.date_joined.isoformat(),
        'last_login': u.last_login.isoformat() if u.last_login else None,
    } for u in users]

    return Response({
        'count': total,
        'page': page,
        'page_size': page_size,
        'total_pages': (total + page_size - 1) // page_size,
        'users': data,
    })


@api_view(['PATCH'])
@permission_classes([IsAuthenticated])
def admin_approve_doctor(request, doctor_id):
    """Approve or reject a doctor application"""
    if request.user.role != 'admin':
        return Response({'error': 'Admin access required'}, status=403)

    try:
        doctor = User.objects.get(id=doctor_id, role='doctor')
    except User.DoesNotExist:
        return Response({'error': 'Doctor not found'}, status=404)

    action = request.data.get('action')  # 'approve' or 'reject'
    if action not in ['approve', 'reject']:
        return Response({'error': 'action must be approve or reject'}, status=400)

    if action == 'approve':
        doctor.is_active = True
        doctor.save()
        create_notification(
            recipient=doctor,
            sender=request.user,
            notification_type='doctor_approved',
            title='Your application has been approved!',
            message='Congratulations! Your doctor profile has been approved. You can now receive patients.',
            link='/doctor/dashboard/',
        )
        send_doctor_approval_email(doctor, approved=True)
        send_doctor_approval_sms(doctor, approved=True)

        return Response({'message': f'Dr. {doctor.full_name} has been approved'})

    if action == 'reject':
        reason = request.data.get('reason', 'Your application did not meet our requirements.')
        doctor.is_active = False
        doctor.save()
        create_notification(
            recipient=doctor,
            sender=request.user,
            notification_type='doctor_rejected',
            title='Your application was not approved',
            message=reason,
        )
        send_doctor_approval_email(doctor, approved=False, reason=reason)
        send_doctor_approval_sms(doctor, approved=False)


        return Response({'message': f'Dr. {doctor.full_name} has been rejected'})


@api_view(['PATCH'])
@permission_classes([IsAuthenticated])
def admin_toggle_user(request, user_id):
    """Activate or deactivate any user account"""
    if request.user.role != 'admin':
        return Response({'error': 'Admin access required'}, status=403)

    try:
        user = User.objects.get(id=user_id)
    except User.DoesNotExist:
        return Response({'error': 'User not found'}, status=404)

    if user == request.user:
        return Response({'error': 'You cannot deactivate your own account'}, status=400)

    user.is_active = not user.is_active
    user.save()

    status_text = 'activated' if user.is_active else 'deactivated'
    return Response({'message': f'User {user.full_name} has been {status_text}', 'is_active': user.is_active})


@api_view(['DELETE'])
@permission_classes([IsAuthenticated])
def admin_delete_user(request, user_id):
    """Delete a user account"""
    if request.user.role != 'admin':
        return Response({'error': 'Admin access required'}, status=403)

    try:
        user = User.objects.get(id=user_id)
    except User.DoesNotExist:
        return Response({'error': 'User not found'}, status=404)

    if user == request.user:
        return Response({'error': 'You cannot delete your own account'}, status=400)

    name = user.full_name
    user.delete()
    return Response({'message': f'User {name} has been deleted'})


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def admin_consultations_list(request):
    """List all consultations for admin"""
    if request.user.role != 'admin':
        return Response({'error': 'Admin access required'}, status=403)

    queryset = Consultation.objects.all().select_related(
        'patient', 'doctor'
    ).order_by('-created_at')[:100]

    data = [{
        'id': c.id,
        'patient_name': c.patient.full_name,
        'doctor_name': c.doctor.full_name,
        'status': c.status,
        'created_at': c.created_at.isoformat(),
        'completed_at': c.completed_at.isoformat() if c.completed_at else None,
    } for c in queryset]

    return Response({'count': len(data), 'consultations': data})

# FILE UPLOADS SYSTEM

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def upload_avatar(request):
    """Upload or update profile avatar"""
    if 'avatar' not in request.FILES:
        return Response({'error': 'No file provided'}, status=400)

    file = request.FILES['avatar']

    # Validate file type
    allowed_types = ['image/jpeg', 'image/png', 'image/webp', 'image/gif']
    if file.content_type not in allowed_types:
        return Response({'error': 'Only JPEG, PNG, WebP and GIF images are allowed'}, status=400)

    # Validate file size (max 5MB)
    if file.size > 5 * 1024 * 1024:
        return Response({'error': 'File size must be under 5MB'}, status=400)

    # Delete old avatar if exists
    user = request.user
    if user.avatar:
        old_path = os.path.join(settings.MEDIA_ROOT, user.avatar)
        if os.path.exists(old_path):
            os.remove(old_path)

    # Save new avatar
    ext = file.name.split('.')[-1].lower()
    filename = f"avatars/{user.id}_{uuid.uuid4().hex[:8]}.{ext}"
    saved_path = default_storage.save(filename, file)

    user.avatar = saved_path
    user.save()

    return Response({
        'message': 'Avatar uploaded successfully',
        'avatar_url': request.build_absolute_uri(settings.MEDIA_URL + saved_path),
        'avatar': saved_path,
    })


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def upload_medical_document(request):
    """Upload a medical document (PDF, image)"""
    if 'file' not in request.FILES:
        return Response({'error': 'No file provided'}, status=400)

    file = request.FILES['file']

    # Validate file type
    allowed_types = [
        'image/jpeg', 'image/png', 'image/webp',
        'application/pdf',
    ]
    if file.content_type not in allowed_types:
        return Response({'error': 'Only JPEG, PNG, WebP and PDF files are allowed'}, status=400)

    # Validate file size (max 20MB)
    if file.size > 20 * 1024 * 1024:
        return Response({'error': 'File size must be under 20MB'}, status=400)

    # Save file
    ext = file.name.split('.')[-1].lower()
    folder = f"medical_docs/{request.user.id}/"
    filename = f"{folder}{uuid.uuid4().hex}.{ext}"
    saved_path = default_storage.save(filename, file)

    file_url = request.build_absolute_uri(settings.MEDIA_URL + saved_path)

    return Response({
        'message': 'File uploaded successfully',
        'file_url': file_url,
        'file_path': saved_path,
        'file_name': file.name,
        'file_size': file.size,
        'content_type': file.content_type,
    }, status=201)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def upload_consultation_file(request, consultation_id):
    """Upload a file to a specific consultation"""
    try:
        consultation = Consultation.objects.get(id=consultation_id)
    except Consultation.DoesNotExist:
        return Response({'error': 'Consultation not found'}, status=404)

    if request.user not in [consultation.patient, consultation.doctor]:
        return Response({'error': 'Permission denied'}, status=403)

    if 'file' not in request.FILES:
        return Response({'error': 'No file provided'}, status=400)

    file = request.FILES['file']

    allowed_types = [
        'image/jpeg', 'image/png', 'image/webp',
        'application/pdf',
    ]
    if file.content_type not in allowed_types:
        return Response({'error': 'Only JPEG, PNG, WebP and PDF files are allowed'}, status=400)

    if file.size > 20 * 1024 * 1024:
        return Response({'error': 'File size must be under 20MB'}, status=400)

    ext = file.name.split('.')[-1].lower()
    folder = f"consultations/{consultation_id}/"
    filename = f"{folder}{uuid.uuid4().hex}.{ext}"
    saved_path = default_storage.save(filename, file)

    file_url = request.build_absolute_uri(settings.MEDIA_URL + saved_path)

    return Response({
        'message': 'File uploaded successfully',
        'file_url': file_url,
        'file_path': saved_path,
        'file_name': file.name,
        'file_size': file.size,
        'content_type': file.content_type,
    }, status=201)


@api_view(['DELETE'])
@permission_classes([IsAuthenticated])
def delete_file(request):
    """Delete an uploaded file"""
    file_path = request.data.get('file_path')
    if not file_path:
        return Response({'error': 'file_path is required'}, status=400)

    # Security: make sure user can only delete their own files
    if str(request.user.id) not in file_path:
        if request.user.role != 'admin':
            return Response({'error': 'Permission denied'}, status=403)

    full_path = os.path.join(settings.MEDIA_ROOT, file_path)
    if os.path.exists(full_path):
        os.remove(full_path)
        return Response({'message': 'File deleted successfully'})

    return Response({'error': 'File not found'}, status=404)

# EMAIL NOTIFICATIONS SYSTEM

from django.core.mail import send_mail
from django.utils.html import strip_tags


def send_email_notification(recipient_email, subject, html_message):
    """Helper function to send email notifications"""
    try:
        plain_message = strip_tags(html_message)
        send_mail(
            subject=subject,
            message=plain_message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[recipient_email],
            html_message=html_message,
            fail_silently=True,
        )
    except Exception as e:
        print(f"Email sending failed: {e}")


def send_appointment_confirmation_email(appointment):
    """Send confirmation email when appointment is booked"""
    # Email to patient
    patient_html = f"""
    <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
        <h2 style="color: #2563eb;">Healzy — Appointment Confirmed</h2>
        <p>Dear {appointment.patient.full_name},</p>
        <p>Your appointment has been successfully booked.</p>
        <div style="background: #f3f4f6; padding: 20px; border-radius: 8px; margin: 20px 0;">
            <p><strong>Doctor:</strong> Dr. {appointment.doctor.full_name}</p>
            <p><strong>Date:</strong> {appointment.appointment_date}</p>
            <p><strong>Time:</strong> {appointment.appointment_time}</p>
            <p><strong>Duration:</strong> {appointment.duration_minutes} minutes</p>
            <p><strong>Status:</strong> {appointment.get_status_display()}</p>
        </div>
        <p>You can view your appointment details in the Healzy app.</p>
        <p style="color: #6b7280; font-size: 12px;">This is an automated message from Healzy Medical Platform.</p>
    </div>
    """
    send_email_notification(
        appointment.patient.email,
        f"Appointment Confirmed — Dr. {appointment.doctor.full_name}",
        patient_html
    )

    # Email to doctor
    doctor_html = f"""
    <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
        <h2 style="color: #2563eb;">Healzy — New Appointment</h2>
        <p>Dear Dr. {appointment.doctor.full_name},</p>
        <p>You have a new appointment booked.</p>
        <div style="background: #f3f4f6; padding: 20px; border-radius: 8px; margin: 20px 0;">
            <p><strong>Patient:</strong> {appointment.patient.full_name}</p>
            <p><strong>Date:</strong> {appointment.appointment_date}</p>
            <p><strong>Time:</strong> {appointment.appointment_time}</p>
            <p><strong>Reason:</strong> {appointment.reason or 'Not specified'}</p>
        </div>
        <p>You can manage your appointments in the Healzy app.</p>
        <p style="color: #6b7280; font-size: 12px;">This is an automated message from Healzy Medical Platform.</p>
    </div>
    """
    send_email_notification(
        appointment.doctor.email,
        f"New Appointment — {appointment.patient.full_name}",
        doctor_html
    )


def send_doctor_approval_email(doctor, approved=True, reason=None):
    """Send email when doctor is approved or rejected"""
    if approved:
        html = f"""
        <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
            <h2 style="color: #16a34a;">Healzy — Application Approved! 🎉</h2>
            <p>Dear Dr. {doctor.full_name},</p>
            <p>Congratulations! Your doctor profile on Healzy has been <strong>approved</strong>.</p>
            <p>You can now:</p>
            <ul>
                <li>Receive patient appointments</li>
                <li>Start online consultations</li>
                <li>Create medical records and prescriptions</li>
                <li>Set your weekly schedule</li>
            </ul>
            <p>Log in to your Healzy account to get started.</p>
            <p style="color: #6b7280; font-size: 12px;">This is an automated message from Healzy Medical Platform.</p>
        </div>
        """
        subject = "Your Healzy Doctor Application is Approved!"
    else:
        html = f"""
        <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
            <h2 style="color: #dc2626;">Healzy — Application Update</h2>
            <p>Dear Dr. {doctor.full_name},</p>
            <p>We have reviewed your application and unfortunately it was not approved at this time.</p>
            <div style="background: #fef2f2; padding: 20px; border-radius: 8px; margin: 20px 0;">
                <p><strong>Reason:</strong> {reason or 'Your application did not meet our requirements.'}</p>
            </div>
            <p>You may reapply after addressing the issues mentioned above.</p>
            <p style="color: #6b7280; font-size: 12px;">This is an automated message from Healzy Medical Platform.</p>
        </div>
        """
        subject = "Update on Your Healzy Doctor Application"

    send_email_notification(doctor.email, subject, html)


def send_welcome_email(user):
    """Send welcome email when user registers"""
    role_text = "doctor" if user.role == "doctor" else "patient"
    html = f"""
    <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
        <h2 style="color: #2563eb;">Welcome to Healzy! 👋</h2>
        <p>Dear {user.full_name},</p>
        <p>Thank you for joining Healzy as a <strong>{role_text}</strong>.</p>
        <p>With Healzy you can:</p>
        <ul>
            <li>Connect with qualified doctors online</li>
            <li>Book appointments easily</li>
            <li>Access your medical records securely</li>
            <li>Get AI-powered health guidance</li>
        </ul>
        <p>We're glad to have you on board!</p>
        <p style="color: #6b7280; font-size: 12px;">This is an automated message from Healzy Medical Platform.</p>
    </div>
    """
    send_email_notification(
        user.email,
        "Welcome to Healzy!",
        html
    )


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def send_test_email(request):
    """Admin endpoint to test email sending"""
    if request.user.role != 'admin':
        return Response({'error': 'Admin access required'}, status=403)

    recipient = request.data.get('email', request.user.email)
    html = """
    <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
        <h2 style="color: #2563eb;">Healzy — Test Email</h2>
        <p>This is a test email from Healzy Medical Platform.</p>
        <p>If you received this, email notifications are working correctly! ✅</p>
    </div>
    """
    send_email_notification(recipient, "Healzy — Test Email", html)
    return Response({'message': f'Test email sent to {recipient}'})

# ADDITIONAL API FEATURES

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def change_password(request):
    """Change user password"""
    old_password = request.data.get('old_password')
    new_password = request.data.get('new_password')

    if not old_password or not new_password:
        return Response({'error': 'old_password and new_password are required'}, status=400)

    if not request.user.check_password(old_password):
        return Response({'error': 'Current password is incorrect'}, status=400)

    if len(new_password) < 8:
        return Response({'error': 'New password must be at least 8 characters'}, status=400)

    request.user.set_password(new_password)
    request.user.save()
    return Response({'message': 'Password changed successfully'})


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def user_statistics(request):
    """Get statistics for the current user"""
    user = request.user

    if user.role == 'patient':
        stats = {
            'total_appointments': user.patient_appointments.count(),
            'upcoming_appointments': user.patient_appointments.filter(
                status__in=['pending', 'confirmed'],
                appointment_date__gte=date.today()
            ).count(),
            'completed_appointments': user.patient_appointments.filter(status='completed').count(),
            'total_consultations': user.patient_consultations.count(),
            'total_medical_records': user.medical_records.filter(is_visible_to_patient=True).count(),
            'active_prescriptions': user.prescriptions.filter(status='active').count(),
            'total_reviews_given': user.given_reviews.count(),
            'unread_notifications': user.notifications.filter(is_read=False).count(),
        }
    elif user.role == 'doctor':
        stats = {
            'total_appointments': user.doctor_appointments.count(),
            'upcoming_appointments': user.doctor_appointments.filter(
                status__in=['pending', 'confirmed'],
                appointment_date__gte=date.today()
            ).count(),
            'completed_appointments': user.doctor_appointments.filter(status='completed').count(),
            'total_consultations': user.doctor_consultations.count(),
            'completed_consultations': user.doctor_consultations.filter(status='completed').count(),
            'total_patients': user.doctor_consultations.values('patient').distinct().count(),
            'total_medical_records_created': user.created_records.count(),
            'avg_rating': None,
            'total_reviews': user.received_reviews.count(),
            'unread_notifications': user.notifications.filter(is_read=False).count(),
        }
        reviews = user.received_reviews.all()
        if reviews.exists():
            stats['avg_rating'] = round(
                sum(r.rating for r in reviews) / reviews.count(), 1
            )
    else:
        stats = {
            'total_users': User.objects.count(),
            'total_doctors': User.objects.filter(role='doctor').count(),
            'total_patients': User.objects.filter(role='patient').count(),
            'total_consultations': Consultation.objects.count(),
            'total_appointments': Appointment.objects.count(),
        }

    return Response({'role': user.role, 'statistics': stats})


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def report_issue(request):
    """Report a bug or issue"""
    title = request.data.get('title', '').strip()
    description = request.data.get('description', '').strip()
    category = request.data.get('category', 'general')

    if not title or not description:
        return Response({'error': 'title and description are required'}, status=400)

    # Send to Telegram support
    import html as html_lib
    bot_token = getattr(settings, 'TELEGRAM_BOT_TOKEN', '')
    chat_id = getattr(settings, 'TELEGRAM_SUPPORT_CHAT_ID', '')

    if bot_token and chat_id:
        try:
            import requests as req
            text = (
                f"🐛 Bug Report\n"
                f"👤 User: {html_lib.escape(request.user.full_name)} (ID: {request.user.id})\n"
                f"📧 Email: {html_lib.escape(request.user.email)}\n"
                f"🔖 Category: {html_lib.escape(category)}\n"
                f"📌 Title: {html_lib.escape(title)}\n\n"
                f"📝 Description:\n{html_lib.escape(description)}"
            )
            req.post(
                f"https://api.telegram.org/bot{bot_token}/sendMessage",
                json={'chat_id': chat_id, 'text': text},
                timeout=5
            )
        except Exception:
            pass

    return Response({'message': 'Issue reported successfully. Thank you!'})


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def search_global(request):
    """Global search across doctors, records and appointments"""
    query = request.query_params.get('q', '').strip()
    if len(query) < 2:
        return Response({'error': 'Query must be at least 2 characters'}, status=400)

    results = {}
    user = request.user

    # Search doctors
    doctors = User.objects.filter(
        role='doctor',
        is_active=True
    ).filter(
        models.Q(first_name__icontains=query) |
        models.Q(last_name__icontains=query) |
        models.Q(profile__specialization__icontains=query)
    ).select_related('profile')[:5]

    results['doctors'] = [{
        'id': d.id,
        'full_name': d.full_name,
        'specialization': getattr(d.profile, 'specialization', None) if hasattr(d, 'profile') else None,
        'avatar': d.avatar,
    } for d in doctors]

    # Search medical records (for patients and doctors)
    if user.role == 'patient':
        records = MedicalRecord.objects.filter(
            patient=user,
            is_visible_to_patient=True
        ).filter(
            models.Q(title__icontains=query) |
            models.Q(description__icontains=query)
        )[:5]
    elif user.role == 'doctor':
        records = MedicalRecord.objects.filter(
            doctor=user
        ).filter(
            models.Q(title__icontains=query) |
            models.Q(description__icontains=query)
        )[:5]
    else:
        records = MedicalRecord.objects.none()

    results['medical_records'] = [{
        'id': r.id,
        'title': r.title,
        'record_type': r.record_type,
        'created_at': r.created_at.isoformat(),
    } for r in records]

    return Response({'query': query, 'results': results})

# APPOINTMENT REMINDERS & CALENDAR

from datetime import datetime, date, timedelta


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def doctor_calendar(request, doctor_id):
    """Get full month calendar for a doctor — available and booked slots"""
    year = int(request.query_params.get('year', date.today().year))
    month = int(request.query_params.get('month', date.today().month))

    try:
        doctor = User.objects.get(id=doctor_id, role='doctor')
    except User.DoesNotExist:
        return Response({'error': 'Doctor not found'}, status=404)

    # Get doctor's weekly schedule
    schedules = DoctorSchedule.objects.filter(doctor=doctor, is_available=True)
    schedule_map = {s.day_of_week: s for s in schedules}

    # Get all booked appointments for that month
    booked = Appointment.objects.filter(
        doctor=doctor,
        appointment_date__year=year,
        appointment_date__month=month,
        status__in=['pending', 'confirmed']
    ).values('appointment_date', 'appointment_time', 'status')

    booked_map = {}
    for b in booked:
        d = str(b['appointment_date'])
        if d not in booked_map:
            booked_map[d] = []
        booked_map[d].append(b['appointment_time'].strftime('%H:%M'))

    # Build calendar days
    import calendar
    _, days_in_month = calendar.monthrange(year, month)

    calendar_data = []
    for day in range(1, days_in_month + 1):
        current_date = date(year, month, day)
        day_of_week = current_date.weekday()
        date_str = str(current_date)

        if day_of_week not in schedule_map:
            calendar_data.append({
                'date': date_str,
                'is_working_day': False,
                'available_slots': [],
                'booked_slots': [],
                'total_slots': 0,
                'available_count': 0,
            })
            continue

        schedule = schedule_map[day_of_week]
        slot_duration = schedule.slot_duration_minutes

        # Generate all slots
        all_slots = []
        current = datetime.combine(current_date, schedule.start_time)
        end = datetime.combine(current_date, schedule.end_time)
        while current + timedelta(minutes=slot_duration) <= end:
            all_slots.append(current.strftime('%H:%M'))
            current += timedelta(minutes=slot_duration)

        booked_times = booked_map.get(date_str, [])
        available_slots = [s for s in all_slots if s not in booked_times]

        calendar_data.append({
            'date': date_str,
            'is_working_day': True,
            'is_past': current_date < date.today(),
            'available_slots': available_slots if current_date >= date.today() else [],
            'booked_slots': booked_times,
            'total_slots': len(all_slots),
            'available_count': len(available_slots) if current_date >= date.today() else 0,
        })

    return Response({
        'doctor_id': doctor_id,
        'doctor_name': doctor.full_name,
        'year': year,
        'month': month,
        'calendar': calendar_data,
    })


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def appointment_reminders(request):
    """Get upcoming appointments that need reminders (24h and 1h)"""
    user = request.user
    now = timezone.now()
    today = now.date()
    tomorrow = today + timedelta(days=1)

    if user.role == 'patient':
        base_qs = Appointment.objects.filter(
            patient=user,
            status__in=['pending', 'confirmed']
        ).select_related('doctor', 'doctor__profile')
    elif user.role == 'doctor':
        base_qs = Appointment.objects.filter(
            doctor=user,
            status__in=['pending', 'confirmed']
        ).select_related('patient', 'patient__profile')
    else:
        return Response({'error': 'Permission denied'}, status=403)

    # Appointments in next 24 hours
    next_24h = base_qs.filter(
        appointment_date__in=[today, tomorrow]
    ).order_by('appointment_date', 'appointment_time')

    reminders = []
    for appt in next_24h:
        appt_datetime = datetime.combine(appt.appointment_date, appt.appointment_time)
        appt_datetime = timezone.make_aware(appt_datetime)
        hours_until = (appt_datetime - now).total_seconds() / 3600

        if hours_until < 0:
            continue

        if hours_until <= 1:
            urgency = 'now'
            message = 'Your appointment is in less than 1 hour!'
        elif hours_until <= 3:
            urgency = 'soon'
            message = f'Your appointment is in {int(hours_until)} hours.'
        elif hours_until <= 24:
            urgency = 'tomorrow'
            message = 'Your appointment is tomorrow.'
        else:
            continue

        if user.role == 'patient':
            other_person = appt.doctor.full_name
            other_label = 'doctor'
        else:
            other_person = appt.patient.full_name
            other_label = 'patient'

        reminders.append({
            'appointment_id': appt.id,
            'urgency': urgency,
            'message': message,
            'hours_until': round(hours_until, 1),
            other_label: other_person,
            'appointment_date': str(appt.appointment_date),
            'appointment_time': str(appt.appointment_time),
            'status': appt.status,
            'reason': appt.reason,
        })

    return Response({
        'reminders': reminders,
        'count': len(reminders),
    })


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def appointment_history(request):
    """Get paginated appointment history with stats"""
    user = request.user

    if user.role == 'patient':
        queryset = Appointment.objects.filter(
            patient=user
        ).select_related('doctor', 'doctor__profile').order_by('-appointment_date', '-appointment_time')
    elif user.role == 'doctor':
        queryset = Appointment.objects.filter(
            doctor=user
        ).select_related('patient', 'patient__profile').order_by('-appointment_date', '-appointment_time')
    else:
        queryset = Appointment.objects.all().select_related(
            'patient', 'doctor'
        ).order_by('-appointment_date', '-appointment_time')

    # Filters
    status_filter = request.query_params.get('status')
    if status_filter:
        queryset = queryset.filter(status=status_filter)

    date_from = request.query_params.get('date_from')
    if date_from:
        queryset = queryset.filter(appointment_date__gte=date_from)

    date_to = request.query_params.get('date_to')
    if date_to:
        queryset = queryset.filter(appointment_date__lte=date_to)

    # Stats
    total = queryset.count()
    completed = queryset.filter(status='completed').count()
    cancelled = queryset.filter(status='cancelled').count()
    upcoming = queryset.filter(
        status__in=['pending', 'confirmed'],
        appointment_date__gte=date.today()
    ).count()

    # Pagination
    page = int(request.query_params.get('page', 1))
    page_size = int(request.query_params.get('page_size', 10))
    start = (page - 1) * page_size
    end = start + page_size
    paginated = queryset[start:end]

    data = []
    for a in paginated:
        entry = {
            'id': a.id,
            'appointment_date': str(a.appointment_date),
            'appointment_time': str(a.appointment_time),
            'duration_minutes': a.duration_minutes,
            'status': a.status,
            'reason': a.reason,
            'notes': a.notes,
            'doctor_notes': a.doctor_notes,
            'created_at': a.created_at.isoformat(),
        }
        if user.role == 'patient':
            entry['doctor'] = {
                'id': a.doctor.id,
                'full_name': a.doctor.full_name,
                'avatar': a.doctor.avatar,
                'specialization': getattr(a.doctor.profile, 'specialization', None) if hasattr(a.doctor, 'profile') else None,
            }
        else:
            entry['patient'] = {
                'id': a.patient.id,
                'full_name': a.patient.full_name,
                'avatar': a.patient.avatar,
            }
        data.append(entry)

    return Response({
        'stats': {
            'total': total,
            'completed': completed,
            'cancelled': cancelled,
            'upcoming': upcoming,
        },
        'count': total,
        'page': page,
        'page_size': page_size,
        'total_pages': (total + page_size - 1) // page_size,
        'appointments': data,
    })


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def reschedule_appointment(request, appointment_id):
    """Reschedule an existing appointment to a new date/time"""
    try:
        appointment = Appointment.objects.get(id=appointment_id)
    except Appointment.DoesNotExist:
        return Response({'error': 'Appointment not found'}, status=404)

    if request.user not in [appointment.patient, appointment.doctor]:
        return Response({'error': 'Permission denied'}, status=403)

    if appointment.status in ['completed', 'cancelled']:
        return Response({'error': 'Cannot reschedule a completed or cancelled appointment'}, status=400)

    new_date = request.data.get('appointment_date')
    new_time = request.data.get('appointment_time')

    if not new_date or not new_time:
        return Response({'error': 'appointment_date and appointment_time are required'}, status=400)

    # Check new slot is not taken
    if Appointment.objects.filter(
        doctor=appointment.doctor,
        appointment_date=new_date,
        appointment_time=new_time,
        status__in=['pending', 'confirmed']
    ).exclude(id=appointment_id).exists():
        return Response({'error': 'This time slot is already booked'}, status=400)

    # Check not in the past
    try:
        new_date_obj = datetime.strptime(new_date, '%Y-%m-%d').date()
        if new_date_obj < date.today():
            return Response({'error': 'Cannot reschedule to a past date'}, status=400)
    except ValueError:
        return Response({'error': 'Invalid date format. Use YYYY-MM-DD'}, status=400)

    old_date = appointment.appointment_date
    old_time = appointment.appointment_time

    appointment.appointment_date = new_date
    appointment.appointment_time = new_time
    appointment.status = 'pending'
    appointment.save()

    # Notify the other party
    if request.user == appointment.patient:
        recipient = appointment.doctor
        msg = f'Patient {appointment.patient.full_name} rescheduled their appointment.'
    else:
        recipient = appointment.patient
        msg = f'Dr. {appointment.doctor.full_name} rescheduled your appointment.'

    create_notification(
        recipient=recipient,
        sender=request.user,
        notification_type='appointment_reminder',
        title='Appointment Rescheduled',
        message=f'{msg} New time: {new_date} at {new_time}.',
        link=f'/appointments/{appointment.id}/',
    )

    return Response({
        'message': 'Appointment rescheduled successfully',
        'old_date': str(old_date),
        'old_time': str(old_time),
        'new_date': new_date,
        'new_time': new_time,
        'status': appointment.status,
    })


# AI DIALOGUE MANAGEMENT

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def start_new_ai_dialogue(request):
    """Start a fresh AI dialogue (clears history)"""
    title = request.data.get('title', '')
    dialogue = ai_service.start_new_dialogue(request.user, title or None)
    return Response({
        'message': 'New dialogue started',
        'dialogue_id': dialogue.id,
        'title': dialogue.title,
    }, status=201)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def close_ai_dialogue(request, dialogue_id):
    """Close a specific AI dialogue"""
    success = ai_service.close_dialogue(request.user, dialogue_id)
    if success:
        return Response({'message': 'Dialogue closed'})
    return Response({'error': 'Dialogue not found'}, status=404)


# ============================================
# DOCTOR AVAILABILITY & BOOKING SLOTS
# ============================================

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def doctor_available_slots(request, doctor_id):
    """Get available time slots for a doctor on a specific date"""
    date_str = request.query_params.get('date')
    if not date_str:
        return Response({'error': 'date parameter is required (YYYY-MM-DD)'}, status=400)

    try:
        requested_date = datetime.strptime(date_str, '%Y-%m-%d').date()
    except ValueError:
        return Response({'error': 'Invalid date format. Use YYYY-MM-DD'}, status=400)

    if requested_date < date.today():
        return Response({'error': 'Cannot check slots for past dates'}, status=400)

    try:
        doctor = User.objects.get(id=doctor_id, role='doctor', is_active=True)
    except User.DoesNotExist:
        return Response({'error': 'Doctor not found'}, status=404)

    # Get doctor's schedule for that day of week
    day_of_week = requested_date.weekday()
    try:
        schedule = DoctorSchedule.objects.get(
            doctor=doctor, day_of_week=day_of_week, is_available=True
        )
    except DoctorSchedule.DoesNotExist:
        return Response({
            'doctor_id': doctor_id,
            'date': date_str,
            'is_working_day': False,
            'available_slots': [],
            'message': 'Doctor does not work on this day',
        })

    # Generate all time slots
    slot_duration = schedule.slot_duration_minutes
    all_slots = []
    current = datetime.combine(requested_date, schedule.start_time)
    end = datetime.combine(requested_date, schedule.end_time)
    while current + timedelta(minutes=slot_duration) <= end:
        all_slots.append(current.strftime('%H:%M'))
        current += timedelta(minutes=slot_duration)

    # Get already booked slots
    booked_times = set(
        Appointment.objects.filter(
            doctor=doctor,
            appointment_date=requested_date,
            status__in=['pending', 'confirmed']
        ).values_list('appointment_time', flat=True)
    )
    booked_str = {t.strftime('%H:%M') if hasattr(t, 'strftime') else str(t)[:5] for t in booked_times}

    # Build slot list with availability
    slots = []
    now = timezone.now()
    for slot_time in all_slots:
        slot_dt = datetime.combine(requested_date, datetime.strptime(slot_time, '%H:%M').time())
        slot_dt_aware = timezone.make_aware(slot_dt)
        is_past = slot_dt_aware <= now
        is_booked = slot_time in booked_str

        slots.append({
            'time': slot_time,
            'is_available': not is_booked and not is_past,
            'is_booked': is_booked,
            'is_past': is_past,
        })

    available_count = sum(1 for s in slots if s['is_available'])

    return Response({
        'doctor_id': doctor_id,
        'doctor_name': doctor.full_name,
        'date': date_str,
        'day_of_week': requested_date.strftime('%A'),
        'is_working_day': True,
        'working_hours': {
            'start': schedule.start_time.strftime('%H:%M'),
            'end': schedule.end_time.strftime('%H:%M'),
            'slot_duration_minutes': slot_duration,
        },
        'total_slots': len(slots),
        'available_count': available_count,
        'booked_count': len(booked_str),
        'slots': slots,
    })


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def doctor_available_dates(request, doctor_id):
    """Get available dates for a doctor in the next N days"""
    days_ahead = int(request.query_params.get('days', 30))
    days_ahead = min(days_ahead, 90)  # Max 90 days

    try:
        doctor = User.objects.get(id=doctor_id, role='doctor', is_active=True)
    except User.DoesNotExist:
        return Response({'error': 'Doctor not found'}, status=404)

    schedules = DoctorSchedule.objects.filter(doctor=doctor, is_available=True)
    working_days = {s.day_of_week for s in schedules}

    if not working_days:
        return Response({
            'doctor_id': doctor_id,
            'available_dates': [],
            'message': 'Doctor has no schedule set up',
        })

    # Get all booked dates in range
    start_date = date.today()
    end_date = start_date + timedelta(days=days_ahead)
    booked = Appointment.objects.filter(
        doctor=doctor,
        appointment_date__range=[start_date, end_date],
        status__in=['pending', 'confirmed']
    ).values('appointment_date').annotate(
        booked_count=models.Count('id')
    )
    booked_map = {str(b['appointment_date']): b['booked_count'] for b in booked}

    # Build available dates
    available_dates = []
    for i in range(days_ahead):
        check_date = start_date + timedelta(days=i)
        if check_date.weekday() not in working_days:
            continue

        schedule = schedules.filter(day_of_week=check_date.weekday()).first()
        if not schedule:
            continue

        # Calculate total slots
        total_slots = 0
        current = datetime.combine(check_date, schedule.start_time)
        end = datetime.combine(check_date, schedule.end_time)
        while current + timedelta(minutes=schedule.slot_duration_minutes) <= end:
            total_slots += 1
            current += timedelta(minutes=schedule.slot_duration_minutes)

        date_str = str(check_date)
        booked_count = booked_map.get(date_str, 0)
        available = total_slots - booked_count

        if available > 0:
            available_dates.append({
                'date': date_str,
                'day_of_week': check_date.strftime('%A'),
                'available_slots': available,
                'total_slots': total_slots,
            })

    return Response({
        'doctor_id': doctor_id,
        'doctor_name': doctor.full_name,
        'days_checked': days_ahead,
        'available_dates': available_dates,
        'total_available_days': len(available_dates),
    })


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def next_available_slot(request, doctor_id):
    """Get the next available appointment slot for a doctor"""
    try:
        doctor = User.objects.get(id=doctor_id, role='doctor', is_active=True)
    except User.DoesNotExist:
        return Response({'error': 'Doctor not found'}, status=404)

    schedules = DoctorSchedule.objects.filter(doctor=doctor, is_available=True)
    working_days = {s.day_of_week: s for s in schedules}

    now = timezone.now()

    for i in range(60):  # Check next 60 days
        check_date = date.today() + timedelta(days=i)
        if check_date.weekday() not in working_days:
            continue

        schedule = working_days[check_date.weekday()]
        current = datetime.combine(check_date, schedule.start_time)
        end = datetime.combine(check_date, schedule.end_time)

        booked_times = set(
            Appointment.objects.filter(
                doctor=doctor,
                appointment_date=check_date,
                status__in=['pending', 'confirmed']
            ).values_list('appointment_time', flat=True)
        )
        booked_str = {t.strftime('%H:%M') if hasattr(t, 'strftime') else str(t)[:5] for t in booked_times}

        while current + timedelta(minutes=schedule.slot_duration_minutes) <= end:
            slot_time = current.strftime('%H:%M')
            slot_aware = timezone.make_aware(current)
            if slot_time not in booked_str and slot_aware > now:
                return Response({
                    'doctor_id': doctor_id,
                    'doctor_name': doctor.full_name,
                    'next_available_date': str(check_date),
                    'next_available_time': slot_time,
                    'day_of_week': check_date.strftime('%A'),
                })
            current += timedelta(minutes=schedule.slot_duration_minutes)

    return Response({
        'doctor_id': doctor_id,
        'message': 'No available slots in the next 60 days',
        'next_available_date': None,
    })

# ============================================
# SMS NOTIFICATIONS
# ============================================

def send_sms(phone_number, message):
    """Send SMS via Twilio"""
    if not settings.SMS_ENABLED:
        print(f"[SMS disabled] To: {phone_number} | Message: {message}")
        return False

    if not phone_number:
        return False

    try:
        from twilio.rest import Client
        client_twilio = Client(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN)
        client_twilio.messages.create(
            body=message,
            from_=settings.TWILIO_PHONE_NUMBER,
            to=phone_number,
        )
        return True
    except Exception as e:
        print(f"SMS sending failed: {e}")
        return False


def send_appointment_sms(appointment, event='booked'):
    """Send SMS for appointment events"""
    if event == 'booked':
        patient_msg = (
            f"Healzy: Ваша запись подтверждена!\n"
            f"Врач: Dr. {appointment.doctor.full_name}\n"
            f"Дата: {appointment.appointment_date} в {appointment.appointment_time}\n"
            f"healzy.uz"
        )
        doctor_msg = (
            f"Healzy: Новая запись!\n"
            f"Пациент: {appointment.patient.full_name}\n"
            f"Дата: {appointment.appointment_date} в {appointment.appointment_time}\n"
            f"healzy.uz"
        )
    elif event == 'cancelled':
        patient_msg = (
            f"Healzy: Ваша запись отменена.\n"
            f"Врач: Dr. {appointment.doctor.full_name}\n"
            f"Дата: {appointment.appointment_date} в {appointment.appointment_time}\n"
            f"Для записи снова: healzy.uz"
        )
        doctor_msg = (
            f"Healzy: Запись отменена.\n"
            f"Пациент: {appointment.patient.full_name}\n"
            f"Дата: {appointment.appointment_date} в {appointment.appointment_time}"
        )
    elif event == 'reminder':
        patient_msg = (
            f"Healzy: Напоминание!\n"
            f"Завтра у вас запись к Dr. {appointment.doctor.full_name}\n"
            f"Время: {appointment.appointment_time}\n"
            f"healzy.uz"
        )
        doctor_msg = (
            f"Healzy: Напоминание!\n"
            f"Завтра: {appointment.patient.full_name}\n"
            f"Время: {appointment.appointment_time}"
        )
    elif event == 'rescheduled':
        patient_msg = (
            f"Healzy: Запись перенесена.\n"
            f"Врач: Dr. {appointment.doctor.full_name}\n"
            f"Новая дата: {appointment.appointment_date} в {appointment.appointment_time}\n"
            f"healzy.uz"
        )
        doctor_msg = (
            f"Healzy: Запись перенесена.\n"
            f"Пациент: {appointment.patient.full_name}\n"
            f"Новая дата: {appointment.appointment_date} в {appointment.appointment_time}"
        )
    else:
        return

    patient_phone = getattr(appointment.patient, 'phone_number', None)
    doctor_phone = getattr(appointment.doctor, 'phone_number', None)

    if patient_phone:
        send_sms(patient_phone, patient_msg)
    if doctor_phone:
        send_sms(doctor_phone, doctor_msg)


def send_doctor_approval_sms(doctor, approved=True):
    """Send SMS when doctor application is approved or rejected"""
    phone = getattr(doctor, 'phone_number', None)
    if not phone:
        return

    if approved:
        msg = (
            f"Healzy: Поздравляем, Dr. {doctor.full_name}!\n"
            f"Ваш профиль врача одобрен.\n"
            f"Войдите на healzy.uz чтобы начать принимать пациентов."
        )
    else:
        msg = (
            f"Healzy: Dr. {doctor.full_name},\n"
            f"К сожалению, ваша заявка не была одобрена.\n"
            f"Свяжитесь с нами для уточнения деталей."
        )
    send_sms(phone, msg)


def send_welcome_sms(user):
    """Send welcome SMS when user registers"""
    phone = getattr(user, 'phone_number', None)
    if not phone:
        return

    if user.role == 'doctor':
        msg = (
            f"Healzy: Добро пожаловать, Dr. {user.full_name}!\n"
            f"Ваша заявка на рассмотрении. Мы уведомим вас об одобрении.\n"
            f"healzy.uz"
        )
    else:
        msg = (
            f"Healzy: Добро пожаловать, {user.full_name}!\n"
            f"Ваш аккаунт создан. Записывайтесь к врачам онлайн.\n"
            f"healzy.uz"
        )
    send_sms(phone, msg)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def send_test_sms(request):
    """Admin endpoint to test SMS sending"""
    if request.user.role != 'admin':
        return Response({'error': 'Admin access required'}, status=403)

    phone = request.data.get('phone')
    if not phone:
        return Response({'error': 'phone is required'}, status=400)

    success = send_sms(phone, 'Healzy: Тестовое SMS сообщение. Если вы получили это — SMS работает! ✅')
    if success:
        return Response({'message': f'Test SMS sent to {phone}'})
    return Response({'message': f'SMS disabled or failed. Check SMS_ENABLED in .env', 'sent': False})

# ============================================
# AI MEDICAL HISTORY SUMMARY
# ============================================

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def ai_medical_summary(request, patient_id=None):
    """Generate AI-powered medical history summary for a patient"""
    user = request.user

    # Determine which patient to summarize
    if user.role == 'patient':
        target_patient = user
    elif user.role in ['doctor', 'admin']:
        if not patient_id:
            return Response({'error': 'patient_id is required for doctors/admins'}, status=400)
        try:
            target_patient = User.objects.get(id=patient_id, role='patient')
        except User.DoesNotExist:
            return Response({'error': 'Patient not found'}, status=404)
    else:
        return Response({'error': 'Permission denied'}, status=403)

    # Gather all medical data
    medical_records = MedicalRecord.objects.filter(
        patient=target_patient
    ).select_related('doctor').order_by('-created_at')[:20]

    appointments = Appointment.objects.filter(
        patient=target_patient,
        status='completed'
    ).select_related('doctor').order_by('-appointment_date')[:10]

    vital_signs = VitalSigns.objects.filter(
        patient=target_patient
    ).order_by('-recorded_at')[:10] if hasattr(target_patient, 'vital_signs') else []

    if not medical_records.exists() and not appointments.exists():
        return Response({
            'patient_id': target_patient.id,
            'patient_name': target_patient.full_name,
            'summary': None,
            'message': 'No medical history found for this patient',
        })

    # Build context for Claude
    records_text = ""
    for r in medical_records:
        records_text += (
            f"\n- [{r.record_type.upper()}] {r.title} "
            f"(by Dr. {r.doctor.full_name}, {r.created_at.strftime('%Y-%m-%d')}): "
            f"{r.description[:300]}"
        )

    appointments_text = ""
    for a in appointments:
        appointments_text += (
            f"\n- {a.appointment_date} with Dr. {a.doctor.full_name}"
            f"{' — ' + a.doctor_notes[:200] if a.doctor_notes else ''}"
        )

    vitals_text = ""
    if vital_signs:
        latest = vital_signs[0] if vital_signs else None
        if latest:
            vitals_text = (
                f"\nLatest vitals ({latest.recorded_at.strftime('%Y-%m-%d')}): "
                f"BP: {getattr(latest, 'blood_pressure', 'N/A')}, "
                f"HR: {getattr(latest, 'heart_rate', 'N/A')} bpm, "
                f"Temp: {getattr(latest, 'temperature', 'N/A')}°C, "
                f"Weight: {getattr(latest, 'weight', 'N/A')} kg"
            )

    patient_age = ""
    if hasattr(target_patient, 'profile') and target_patient.profile:
        dob = getattr(target_patient.profile, 'date_of_birth', None)
        if dob:
            from datetime import date as date_type
            age = (date_type.today() - dob).days // 365
            patient_age = f", Age: {age}"

    prompt = f"""You are a medical AI assistant. Analyze this patient's medical history and create a comprehensive summary in Russian.

Patient: {target_patient.full_name}{patient_age}

MEDICAL RECORDS:
{records_text if records_text else 'No records available'}

COMPLETED APPOINTMENTS:
{appointments_text if appointments_text else 'No completed appointments'}

VITAL SIGNS:
{vitals_text if vitals_text else 'No vital signs recorded'}

Please provide a structured medical summary in Russian with these sections:
1. **Общая картина здоровья** — overall health status
2. **Основные диагнозы и состояния** — main diagnoses and conditions
3. **История лечения** — treatment history
4. **Текущие показатели** — current vitals if available
5. **Рекомендации** — recommendations for the patient or doctor
6. **Важные предупреждения** — any red flags or urgent concerns (if any)

Be concise, professional, and clinically accurate. Use simple language where possible."""

    try:
        from django.conf import settings as django_settings
        import anthropic
        claude_client = anthropic.Anthropic(api_key=django_settings.ANTHROPIC_API_KEY)
        response = claude_client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=1500,
            messages=[{'role': 'user', 'content': prompt}],
        )
        summary_text = response.content[0].text

        return Response({
            'patient_id': target_patient.id,
            'patient_name': target_patient.full_name,
            'generated_at': timezone.now().isoformat(),
            'data_points': {
                'medical_records': medical_records.count(),
                'appointments': appointments.count(),
                'has_vitals': bool(vitals_text),
            },
            'summary': summary_text,
        })

    except Exception as e:
        return Response({'error': f'AI summary generation failed: {str(e)}'}, status=500)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def ai_patient_risk_assessment(request, patient_id=None):
    """AI-powered risk assessment for a patient based on their history"""
    user = request.user

    if user.role == 'patient':
        target_patient = user
    elif user.role in ['doctor', 'admin']:
        if not patient_id:
            return Response({'error': 'patient_id is required'}, status=400)
        try:
            target_patient = User.objects.get(id=patient_id, role='patient')
        except User.DoesNotExist:
            return Response({'error': 'Patient not found'}, status=404)
    else:
        return Response({'error': 'Permission denied'}, status=403)

    # Gather records
    medical_records = MedicalRecord.objects.filter(
        patient=target_patient
    ).order_by('-created_at')[:15]

    if not medical_records.exists():
        return Response({
            'patient_id': target_patient.id,
            'risk_level': 'unknown',
            'message': 'Insufficient medical history for risk assessment',
        })

    records_text = "\n".join([
        f"- [{r.record_type}] {r.title}: {r.description[:200]}"
        for r in medical_records
    ])

    prompt = f"""Based on this patient's medical records, provide a brief risk assessment in Russian.

Patient: {target_patient.full_name}
Medical Records:
{records_text}

Respond ONLY with a JSON object (no markdown, no extra text):
{{
  "risk_level": "low|medium|high",
  "risk_factors": ["factor1", "factor2"],
  "protective_factors": ["factor1", "factor2"],
  "immediate_concerns": ["concern1"],
  "recommended_screenings": ["screening1", "screening2"],
  "lifestyle_recommendations": ["recommendation1"],
  "summary": "2-3 sentence summary in Russian"
}}"""

    try:
        from django.conf import settings as django_settings
        import anthropic
        claude_client = anthropic.Anthropic(api_key=django_settings.ANTHROPIC_API_KEY)
        response = claude_client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=800,
            messages=[{'role': 'user', 'content': prompt}],
        )
        raw = response.content[0].text.strip()
        # Clean JSON
        if '```' in raw:
            raw = raw.split('```')[1]
            if raw.startswith('json'):
                raw = raw[4:]
        assessment = json.loads(raw)

        return Response({
            'patient_id': target_patient.id,
            'patient_name': target_patient.full_name,
            'generated_at': timezone.now().isoformat(),
            'assessment': assessment,
        })

    except json.JSONDecodeError:
        return Response({'error': 'Failed to parse AI response'}, status=500)
    except Exception as e:
        return Response({'error': f'Risk assessment failed: {str(e)}'}, status=500)
    
# VIDEO CALL / TELEMEDICINE

from .models import VideoCall, VideoCallSignal

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def create_video_call(request):
    """Create a new video call room"""
    user = request.user
    other_user_id = request.data.get('user_id')
    appointment_id = request.data.get('appointment_id')

    if not other_user_id:
        return Response({'error': 'user_id is required'}, status=400)

    try:
        other_user = User.objects.get(id=other_user_id)
    except User.DoesNotExist:
        return Response({'error': 'User not found'}, status=404)

    # Determine doctor and patient
    if user.role == 'doctor' and other_user.role == 'patient':
        doctor, patient = user, other_user
    elif user.role == 'patient' and other_user.role == 'doctor':
        doctor, patient = other_user, user
    else:
        return Response({'error': 'Video call must be between a doctor and a patient'}, status=400)

    # Get appointment if provided
    appointment = None
    if appointment_id:
        try:
            appointment = Appointment.objects.get(
                id=appointment_id, doctor=doctor, patient=patient
            )
        except Appointment.DoesNotExist:
            pass

    # Generate unique room ID
    room_id = f"healzy_{uuid.uuid4().hex[:12]}"

    # Create video call
    call = VideoCall.objects.create(
        doctor=doctor,
        patient=patient,
        appointment=appointment,
        room_id=room_id,
        status='waiting',
    )

    # Notify the other user
    create_notification(
        recipient=other_user,
        sender=user,
        notification_type='general',
        title='Incoming Video Call',
        message=f'{user.full_name} is calling you. Join the video call now.',
        link=f'/video-call/{room_id}/',
    )

    # Send SMS notification
    call_msg = f"Healzy: {user.full_name} начинает видеозвонок. Присоединитесь: healzy.uz/video-call/{room_id}/"
    other_phone = getattr(other_user, 'phone_number', None)
    if other_phone:
        send_sms(other_phone, call_msg)

    return Response({
        'room_id': room_id,
        'call_id': call.id,
        'doctor': {'id': doctor.id, 'full_name': doctor.full_name, 'avatar': doctor.avatar},
        'patient': {'id': patient.id, 'full_name': patient.full_name, 'avatar': patient.avatar},
        'status': call.status,
        'created_at': call.created_at.isoformat(),
    }, status=201)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_video_call(request, room_id):
    """Get video call details by room ID"""
    try:
        call = VideoCall.objects.get(room_id=room_id)
    except VideoCall.DoesNotExist:
        return Response({'error': 'Video call room not found'}, status=404)

    if request.user not in [call.doctor, call.patient]:
        return Response({'error': 'Permission denied'}, status=403)

    return Response({
        'room_id': call.room_id,
        'call_id': call.id,
        'status': call.status,
        'doctor': {'id': call.doctor.id, 'full_name': call.doctor.full_name, 'avatar': call.doctor.avatar},
        'patient': {'id': call.patient.id, 'full_name': call.patient.full_name, 'avatar': call.patient.avatar},
        'started_at': call.started_at.isoformat() if call.started_at else None,
        'ended_at': call.ended_at.isoformat() if call.ended_at else None,
        'duration_minutes': call.duration_minutes,
        'created_at': call.created_at.isoformat(),
    })


@api_view(['PATCH'])
@permission_classes([IsAuthenticated])
def update_video_call_status(request, room_id):
    """Update video call status (active, ended, missed)"""
    try:
        call = VideoCall.objects.get(room_id=room_id)
    except VideoCall.DoesNotExist:
        return Response({'error': 'Video call room not found'}, status=404)

    if request.user not in [call.doctor, call.patient]:
        return Response({'error': 'Permission denied'}, status=403)

    new_status = request.data.get('status')
    if new_status not in ['active', 'ended', 'missed']:
        return Response({'error': 'status must be active, ended or missed'}, status=400)

    if new_status == 'active' and call.status == 'waiting':
        call.started_at = timezone.now()

    if new_status == 'ended' and call.started_at:
        call.ended_at = timezone.now()
        call.duration_seconds = int((call.ended_at - call.started_at).total_seconds())

    call.status = new_status
    call.save()

    return Response({
        'room_id': room_id,
        'status': call.status,
        'duration_seconds': call.duration_seconds,
        'duration_minutes': call.duration_minutes,
    })


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def send_webrtc_signal(request, room_id):
    """Send WebRTC signaling data (offer, answer, ICE candidate)"""
    try:
        call = VideoCall.objects.get(room_id=room_id)
    except VideoCall.DoesNotExist:
        return Response({'error': 'Video call room not found'}, status=404)

    if request.user not in [call.doctor, call.patient]:
        return Response({'error': 'Permission denied'}, status=403)

    signal_type = request.data.get('signal_type')
    payload = request.data.get('payload')

    if signal_type not in ['offer', 'answer', 'ice_candidate', 'end_call']:
        return Response({'error': 'Invalid signal_type'}, status=400)

    if not payload:
        return Response({'error': 'payload is required'}, status=400)

    signal = VideoCallSignal.objects.create(
        call=call,
        sender=request.user,
        signal_type=signal_type,
        payload=payload,
    )

    return Response({
        'signal_id': signal.id,
        'signal_type': signal_type,
        'created_at': signal.created_at.isoformat(),
    }, status=201)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_webrtc_signals(request, room_id):
    """Poll for new WebRTC signals (for the other participant)"""
    try:
        call = VideoCall.objects.get(room_id=room_id)
    except VideoCall.DoesNotExist:
        return Response({'error': 'Video call room not found'}, status=404)

    if request.user not in [call.doctor, call.patient]:
        return Response({'error': 'Permission denied'}, status=403)

    # Get signals sent by the OTHER user (not self)
    after_id = request.query_params.get('after_id', 0)
    signals = VideoCallSignal.objects.filter(
        call=call,
        id__gt=after_id,
    ).exclude(sender=request.user).order_by('created_at')

    return Response({
        'signals': [{
            'id': s.id,
            'signal_type': s.signal_type,
            'payload': s.payload,
            'created_at': s.created_at.isoformat(),
        } for s in signals],
        'count': signals.count(),
    })


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def my_video_calls(request):
    """Get video call history for the current user"""
    user = request.user

    if user.role == 'doctor':
        calls = VideoCall.objects.filter(doctor=user).order_by('-created_at')[:20]
    else:
        calls = VideoCall.objects.filter(patient=user).order_by('-created_at')[:20]

    data = [{
        'room_id': c.room_id,
        'call_id': c.id,
        'status': c.status,
        'doctor': {'id': c.doctor.id, 'full_name': c.doctor.full_name},
        'patient': {'id': c.patient.id, 'full_name': c.patient.full_name},
        'duration_minutes': c.duration_minutes,
        'created_at': c.created_at.isoformat(),
    } for c in calls]

    return Response({'calls': data, 'count': len(data)})

# DENTAL TOOTH HISTORY SYSTEM

from .models import DentalChart, Tooth, ToothTreatment, ToothXray

def get_or_create_dental_chart(patient):
    """Get or create a dental chart for a patient, with all 32 teeth"""
    chart, created = DentalChart.objects.get_or_create(patient=patient)
    if created:
        # Create all 32 teeth using FDI numbering
        fdi_numbers = (
            list(range(11, 19)) +  # Upper right
            list(range(21, 29)) +  # Upper left
            list(range(31, 39)) +  # Lower left
            list(range(41, 49))    # Lower right
        )
        Tooth.objects.bulk_create([
            Tooth(chart=chart, fdi_number=n, condition='healthy')
            for n in fdi_numbers
        ])
    return chart


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_dental_chart(request, patient_id=None):
    """Get full dental chart for a patient"""
    user = request.user

    if user.role == 'patient':
        target_patient = user
    elif user.role in ['doctor', 'admin']:
        if not patient_id:
            return Response({'error': 'patient_id is required'}, status=400)
        try:
            target_patient = User.objects.get(id=patient_id, role='patient')
        except User.DoesNotExist:
            return Response({'error': 'Patient not found'}, status=404)
    else:
        return Response({'error': 'Permission denied'}, status=403)

    chart = get_or_create_dental_chart(target_patient)
    teeth = Tooth.objects.filter(chart=chart).prefetch_related(
        'treatments', 'treatments__doctor', 'xrays'
    ).order_by('fdi_number')

    # Group teeth by quadrant
    quadrants = {
        'upper_right': [],  # 11-18
        'upper_left': [],   # 21-28
        'lower_left': [],   # 31-38
        'lower_right': [],  # 41-48
    }

    quadrant_map = {
        1: 'upper_right', 2: 'upper_left',
        3: 'lower_left', 4: 'lower_right'
    }

    for tooth in teeth:
        quadrant_key = quadrant_map.get(tooth.fdi_number // 10)
        if not quadrant_key:
            continue

        tooth_data = {
            'id': tooth.id,
            'fdi_number': tooth.fdi_number,
            'condition': tooth.condition,
            'quadrant': tooth.quadrant,
            'notes': tooth.notes,
            'last_updated': tooth.last_updated.isoformat(),
            'last_updated_by': tooth.last_updated_by.full_name if tooth.last_updated_by else None,
            'treatment_count': tooth.treatments.count(),
            'xray_count': tooth.xrays.count(),
            'latest_treatment': None,
        }

        latest = tooth.treatments.first()
        if latest:
            tooth_data['latest_treatment'] = {
                'treatment_type': latest.treatment_type,
                'treatment_date': str(latest.treatment_date),
                'doctor': latest.doctor.full_name if latest.doctor else None,
            }

        quadrants[quadrant_key].append(tooth_data)

    # Overall stats
    condition_summary = {}
    for tooth in teeth:
        condition_summary[tooth.condition] = condition_summary.get(tooth.condition, 0) + 1

    return Response({
        'chart_id': chart.id,
        'patient_id': target_patient.id,
        'patient_name': target_patient.full_name,
        'created_at': chart.created_at.isoformat(),
        'updated_at': chart.updated_at.isoformat(),
        'notes': chart.notes,
        'condition_summary': condition_summary,
        'total_teeth': teeth.count(),
        'quadrants': quadrants,
    })


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_tooth_detail(request, patient_id, fdi_number):
    """Get full history of a single tooth"""
    user = request.user

    if user.role == 'patient':
        if str(user.id) != str(patient_id):
            return Response({'error': 'Permission denied'}, status=403)
        target_patient = user
    elif user.role in ['doctor', 'admin']:
        try:
            target_patient = User.objects.get(id=patient_id, role='patient')
        except User.DoesNotExist:
            return Response({'error': 'Patient not found'}, status=404)
    else:
        return Response({'error': 'Permission denied'}, status=403)

    chart = get_or_create_dental_chart(target_patient)

    try:
        tooth = Tooth.objects.get(chart=chart, fdi_number=fdi_number)
    except Tooth.DoesNotExist:
        return Response({'error': f'Tooth {fdi_number} not found'}, status=404)

    treatments = ToothTreatment.objects.filter(tooth=tooth).select_related('doctor').order_by('-treatment_date')
    xrays = ToothXray.objects.filter(tooth=tooth).select_related('uploaded_by').order_by('-taken_at')

    return Response({
        'tooth_id': tooth.id,
        'fdi_number': tooth.fdi_number,
        'quadrant': tooth.quadrant,
        'condition': tooth.condition,
        'notes': tooth.notes,
        'last_updated': tooth.last_updated.isoformat(),
        'last_updated_by': tooth.last_updated_by.full_name if tooth.last_updated_by else None,
        'patient': {
            'id': target_patient.id,
            'full_name': target_patient.full_name,
        },
        'treatments': [{
            'id': t.id,
            'treatment_type': t.treatment_type,
            'treatment_date': str(t.treatment_date),
            'doctor': t.doctor.full_name if t.doctor else None,
            'doctor_id': t.doctor.id if t.doctor else None,
            'description': t.description,
            'materials_used': t.materials_used,
            'cost': str(t.cost) if t.cost else None,
            'next_visit_recommended': str(t.next_visit_recommended) if t.next_visit_recommended else None,
            'created_at': t.created_at.isoformat(),
        } for t in treatments],
        'xrays': [{
            'id': x.id,
            'file_url': request.build_absolute_uri(x.file.url) if x.file else None,
            'file_type': x.file_type,
            'notes': x.notes,
            'taken_at': str(x.taken_at),
            'uploaded_by': x.uploaded_by.full_name if x.uploaded_by else None,
            'treatment_id': x.treatment.id if x.treatment else None,
        } for x in xrays],
    })


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def add_tooth_treatment(request, patient_id, fdi_number):
    """Add a treatment record to a specific tooth (doctors only)"""
    if request.user.role not in ['doctor', 'admin']:
        return Response({'error': 'Only doctors can add treatment records'}, status=403)

    try:
        target_patient = User.objects.get(id=patient_id, role='patient')
    except User.DoesNotExist:
        return Response({'error': 'Patient not found'}, status=404)

    chart = get_or_create_dental_chart(target_patient)

    try:
        tooth = Tooth.objects.get(chart=chart, fdi_number=fdi_number)
    except Tooth.DoesNotExist:
        return Response({'error': f'Tooth {fdi_number} not found'}, status=404)

    treatment_type = request.data.get('treatment_type')
    treatment_date = request.data.get('treatment_date')

    if not treatment_type or not treatment_date:
        return Response({'error': 'treatment_type and treatment_date are required'}, status=400)

    valid_treatments = [t[0] for t in ToothTreatment.TREATMENT_CHOICES]
    if treatment_type not in valid_treatments:
        return Response({
            'error': f'Invalid treatment_type. Valid options: {valid_treatments}'
        }, status=400)

    treatment = ToothTreatment.objects.create(
        tooth=tooth,
        doctor=request.user,
        treatment_type=treatment_type,
        treatment_date=treatment_date,
        description=request.data.get('description', ''),
        materials_used=request.data.get('materials_used', ''),
        cost=request.data.get('cost'),
        next_visit_recommended=request.data.get('next_visit_recommended'),
    )

    # Update tooth condition based on treatment
    condition_map = {
        'filling': 'filled',
        'composite_filling': 'filled',
        'amalgam_filling': 'filled',
        'crown': 'crowned',
        'root_canal': 'root_canal',
        'extraction': 'extracted',
        'implant': 'implant',
        'implant_crown': 'implant',
        'bridge': 'bridge',
        'veneer': 'veneer',
    }
    new_condition = condition_map.get(treatment_type)
    if new_condition:
        tooth.condition = new_condition

    tooth.notes = request.data.get('tooth_notes', tooth.notes)
    tooth.last_updated_by = request.user
    tooth.save()

    # Notify patient
    create_notification(
        recipient=target_patient,
        sender=request.user,
        notification_type='general',
        title='Dental Record Updated',
        message=f'Dr. {request.user.full_name} added a {treatment_type} record for tooth {fdi_number}.',
        link='/dental-chart/',
    )

    return Response({
        'message': 'Treatment added successfully',
        'treatment_id': treatment.id,
        'tooth_fdi': fdi_number,
        'new_condition': tooth.condition,
        'treatment_type': treatment_type,
        'treatment_date': str(treatment_date),
    }, status=201)


@api_view(['PATCH'])
@permission_classes([IsAuthenticated])
def update_tooth_condition(request, patient_id, fdi_number):
    """Update the condition of a tooth (doctors only)"""
    if request.user.role not in ['doctor', 'admin']:
        return Response({'error': 'Only doctors can update tooth conditions'}, status=403)

    try:
        target_patient = User.objects.get(id=patient_id, role='patient')
    except User.DoesNotExist:
        return Response({'error': 'Patient not found'}, status=404)

    chart = get_or_create_dental_chart(target_patient)

    try:
        tooth = Tooth.objects.get(chart=chart, fdi_number=fdi_number)
    except Tooth.DoesNotExist:
        return Response({'error': f'Tooth {fdi_number} not found'}, status=404)

    valid_conditions = [c[0] for c in Tooth.CONDITION_CHOICES]
    new_condition = request.data.get('condition')

    if new_condition and new_condition not in valid_conditions:
        return Response({
            'error': f'Invalid condition. Valid options: {valid_conditions}'
        }, status=400)

    if new_condition:
        tooth.condition = new_condition
    if 'notes' in request.data:
        tooth.notes = request.data['notes']

    tooth.last_updated_by = request.user
    tooth.save()

    return Response({
        'message': 'Tooth updated successfully',
        'fdi_number': fdi_number,
        'condition': tooth.condition,
        'notes': tooth.notes,
    })


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def upload_tooth_xray(request, patient_id, fdi_number):
    """Upload an X-ray or photo for a specific tooth (doctors only)"""
    if request.user.role not in ['doctor', 'admin']:
        return Response({'error': 'Only doctors can upload X-rays'}, status=403)

    try:
        target_patient = User.objects.get(id=patient_id, role='patient')
    except User.DoesNotExist:
        return Response({'error': 'Patient not found'}, status=404)

    chart = get_or_create_dental_chart(target_patient)

    try:
        tooth = Tooth.objects.get(chart=chart, fdi_number=fdi_number)
    except Tooth.DoesNotExist:
        return Response({'error': f'Tooth {fdi_number} not found'}, status=404)

    if 'file' not in request.FILES:
        return Response({'error': 'No file provided'}, status=400)

    file = request.FILES['file']
    allowed_types = ['image/jpeg', 'image/png', 'image/webp', 'application/pdf']
    if file.content_type not in allowed_types:
        return Response({'error': 'Only JPEG, PNG, WebP and PDF files are allowed'}, status=400)

    if file.size > 20 * 1024 * 1024:
        return Response({'error': 'File size must be under 20MB'}, status=400)

    taken_at = request.data.get('taken_at', str(date.today()))
    treatment_id = request.data.get('treatment_id')
    treatment = None
    if treatment_id:
        try:
            treatment = ToothTreatment.objects.get(id=treatment_id, tooth=tooth)
        except ToothTreatment.DoesNotExist:
            pass

    xray = ToothXray.objects.create(
        tooth=tooth,
        treatment=treatment,
        uploaded_by=request.user,
        file=file,
        file_type=request.data.get('file_type', 'xray'),
        notes=request.data.get('notes', ''),
        taken_at=taken_at,
    )

    return Response({
        'message': 'X-ray uploaded successfully',
        'xray_id': xray.id,
        'file_url': request.build_absolute_uri(xray.file.url),
        'tooth_fdi': fdi_number,
        'taken_at': str(taken_at),
    }, status=201)


@api_view(['DELETE'])
@permission_classes([IsAuthenticated])
def delete_tooth_treatment(request, treatment_id):
    """Delete a treatment record (doctors/admins only)"""
    if request.user.role not in ['doctor', 'admin']:
        return Response({'error': 'Only doctors can delete treatment records'}, status=403)

    try:
        treatment = ToothTreatment.objects.get(id=treatment_id)
    except ToothTreatment.DoesNotExist:
        return Response({'error': 'Treatment not found'}, status=404)

    if treatment.doctor != request.user and request.user.role != 'admin':
        return Response({'error': 'You can only delete your own treatment records'}, status=403)

    fdi = treatment.tooth.fdi_number
    treatment.delete()

    return Response({'message': f'Treatment record for tooth {fdi} deleted successfully'})


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def patient_dental_summary(request, patient_id=None):
    """Get AI-powered dental summary for a patient"""
    user = request.user

    if user.role == 'patient':
        target_patient = user
    elif user.role in ['doctor', 'admin']:
        if not patient_id:
            return Response({'error': 'patient_id is required'}, status=400)
        try:
            target_patient = User.objects.get(id=patient_id, role='patient')
        except User.DoesNotExist:
            return Response({'error': 'Patient not found'}, status=404)
    else:
        return Response({'error': 'Permission denied'}, status=403)

    chart = get_or_create_dental_chart(target_patient)
    teeth = Tooth.objects.filter(chart=chart).prefetch_related('treatments')

    # Build dental history text
    problem_teeth = []
    all_treatments = []

    for tooth in teeth:
        if tooth.condition != 'healthy':
            problem_teeth.append(f"Tooth {tooth.fdi_number} ({tooth.quadrant}): {tooth.condition}")
        for t in tooth.treatments.all():
            all_treatments.append(
                f"- Tooth {tooth.fdi_number}: {t.treatment_type} on {t.treatment_date}"
                f" by Dr. {t.doctor.full_name if t.doctor else 'Unknown'}"
            )

    if not problem_teeth and not all_treatments:
        return Response({
            'patient_name': target_patient.full_name,
            'summary': 'Нет данных о стоматологических процедурах. Зубы помечены как здоровые.',
            'problem_teeth_count': 0,
            'total_treatments': 0,
        })

    prompt = f"""Ты стоматолог-ассистент. Проанализируй историю зубов пациента и дай краткое резюме на русском языке.

Пациент: {target_patient.full_name}

Проблемные зубы:
{chr(10).join(problem_teeth) if problem_teeth else 'Нет'}

История лечения:
{chr(10).join(all_treatments[-20:]) if all_treatments else 'Нет'}

Дай структурированное резюме:
1. **Общее состояние зубов**
2. **Проведённые процедуры**
3. **Зубы требующие внимания**
4. **Рекомендации**

Будь краткой и профессиональной."""

    try:
        import anthropic
        from django.conf import settings as django_settings
        claude_client = anthropic.Anthropic(api_key=django_settings.ANTHROPIC_API_KEY)
        response = claude_client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=800,
            messages=[{'role': 'user', 'content': prompt}],
        )

        return Response({
            'patient_name': target_patient.full_name,
            'generated_at': timezone.now().isoformat(),
            'problem_teeth_count': len(problem_teeth),
            'total_treatments': len(all_treatments),
            'summary': response.content[0].text,
        })

    except Exception as e:
        return Response({'error': f'Summary generation failed: {str(e)}'}, status=500)
    
# ============================================
# NEUROLOGY MODULE
# ============================================

from .models import HeadacheDiary, SeizureRecord, NeurologyVisit


@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated])
def headache_diary(request):
    """Get or add headache diary entries"""
    user = request.user

    if request.method == 'GET':
        patient_id = request.query_params.get('patient_id')
        if patient_id and user.role in ['doctor', 'admin']:
            entries = HeadacheDiary.objects.filter(patient_id=patient_id)
        else:
            entries = HeadacheDiary.objects.filter(patient=user)

        # Filters
        headache_type = request.query_params.get('type')
        if headache_type:
            entries = entries.filter(headache_type=headache_type)

        date_from = request.query_params.get('date_from')
        if date_from:
            entries = entries.filter(started_at__date__gte=date_from)

        date_to = request.query_params.get('date_to')
        if date_to:
            entries = entries.filter(started_at__date__lte=date_to)

        min_severity = request.query_params.get('min_severity')
        if min_severity:
            entries = entries.filter(severity__gte=int(min_severity))

        # Stats
        total = entries.count()
        avg_severity = entries.aggregate(
            avg=models.Avg('severity')
        )['avg']

        # Frequency by type
        from django.db.models import Count
        by_type = entries.values('headache_type').annotate(
            count=Count('id')
        ).order_by('-count')

        # Pagination
        page = int(request.query_params.get('page', 1))
        page_size = int(request.query_params.get('page_size', 20))
        start = (page - 1) * page_size
        paginated = entries[start:start + page_size]

        return Response({
            'stats': {
                'total_entries': total,
                'avg_severity': round(avg_severity, 1) if avg_severity else None,
                'by_type': list(by_type),
            },
            'count': total,
            'page': page,
            'entries': [{
                'id': e.id,
                'headache_type': e.headache_type,
                'severity': e.severity,
                'location': e.location,
                'started_at': e.started_at.isoformat(),
                'ended_at': e.ended_at.isoformat() if e.ended_at else None,
                'duration_minutes': e.duration_minutes,
                'nausea': e.nausea,
                'vomiting': e.vomiting,
                'light_sensitivity': e.light_sensitivity,
                'sound_sensitivity': e.sound_sensitivity,
                'aura': e.aura,
                'aura_description': e.aura_description,
                'triggers': e.triggers,
                'medication_taken': e.medication_taken,
                'medication_helped': e.medication_helped,
                'notes': e.notes,
                'created_at': e.created_at.isoformat(),
            } for e in paginated],
        })

    # POST — add new entry
    required = ['severity', 'started_at']
    for field in required:
        if not request.data.get(field):
            return Response({'error': f'{field} is required'}, status=400)

    severity = int(request.data.get('severity'))
    if severity < 1 or severity > 10:
        return Response({'error': 'severity must be between 1 and 10'}, status=400)

    entry = HeadacheDiary.objects.create(
        patient=user,
        headache_type=request.data.get('headache_type', 'unknown'),
        severity=severity,
        location=request.data.get('location', 'whole_head'),
        started_at=request.data.get('started_at'),
        ended_at=request.data.get('ended_at'),
        nausea=request.data.get('nausea', False),
        vomiting=request.data.get('vomiting', False),
        light_sensitivity=request.data.get('light_sensitivity', False),
        sound_sensitivity=request.data.get('sound_sensitivity', False),
        aura=request.data.get('aura', False),
        aura_description=request.data.get('aura_description', ''),
        triggers=request.data.get('triggers', []),
        medication_taken=request.data.get('medication_taken', ''),
        medication_helped=request.data.get('medication_helped'),
        notes=request.data.get('notes', ''),
    )

    return Response({
        'message': 'Headache entry added successfully',
        'id': entry.id,
        'severity': entry.severity,
        'headache_type': entry.headache_type,
        'started_at': entry.started_at.isoformat(),
        'duration_minutes': entry.duration_minutes,
    }, status=201)


@api_view(['GET', 'PATCH', 'DELETE'])
@permission_classes([IsAuthenticated])
def headache_entry_detail(request, entry_id):
    """Get, update or delete a headache diary entry"""
    try:
        entry = HeadacheDiary.objects.get(id=entry_id)
    except HeadacheDiary.DoesNotExist:
        return Response({'error': 'Entry not found'}, status=404)

    if entry.patient != request.user and request.user.role not in ['doctor', 'admin']:
        return Response({'error': 'Permission denied'}, status=403)

    if request.method == 'GET':
        return Response({
            'id': entry.id,
            'headache_type': entry.headache_type,
            'severity': entry.severity,
            'location': entry.location,
            'started_at': entry.started_at.isoformat(),
            'ended_at': entry.ended_at.isoformat() if entry.ended_at else None,
            'duration_minutes': entry.duration_minutes,
            'nausea': entry.nausea,
            'vomiting': entry.vomiting,
            'light_sensitivity': entry.light_sensitivity,
            'sound_sensitivity': entry.sound_sensitivity,
            'aura': entry.aura,
            'aura_description': entry.aura_description,
            'triggers': entry.triggers,
            'medication_taken': entry.medication_taken,
            'medication_helped': entry.medication_helped,
            'notes': entry.notes,
        })

    if request.method == 'PATCH':
        if entry.patient != request.user:
            return Response({'error': 'Permission denied'}, status=403)
        fields = [
            'headache_type', 'severity', 'location', 'ended_at',
            'nausea', 'vomiting', 'light_sensitivity', 'sound_sensitivity',
            'aura', 'aura_description', 'triggers', 'medication_taken',
            'medication_helped', 'notes'
        ]
        for field in fields:
            if field in request.data:
                setattr(entry, field, request.data[field])
        entry.save()
        return Response({'message': 'Entry updated successfully'})

    if request.method == 'DELETE':
        if entry.patient != request.user and request.user.role != 'admin':
            return Response({'error': 'Permission denied'}, status=403)
        entry.delete()
        return Response({'message': 'Entry deleted successfully'})


@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated])
def seizure_records(request):
    """Get or add seizure records"""
    user = request.user

    if request.method == 'GET':
        patient_id = request.query_params.get('patient_id')
        if patient_id and user.role in ['doctor', 'admin']:
            records = SeizureRecord.objects.filter(patient_id=patient_id)
        else:
            records = SeizureRecord.objects.filter(patient=user)

        date_from = request.query_params.get('date_from')
        if date_from:
            records = records.filter(occurred_at__date__gte=date_from)

        total = records.count()
        from django.db.models import Count, Avg
        by_type = records.values('seizure_type').annotate(
            count=Count('id')
        ).order_by('-count')

        avg_duration = records.aggregate(avg=Avg('duration_seconds'))['avg']

        page = int(request.query_params.get('page', 1))
        page_size = int(request.query_params.get('page_size', 20))
        start = (page - 1) * page_size
        paginated = records[start:start + page_size]

        return Response({
            'stats': {
                'total_seizures': total,
                'avg_duration_seconds': round(avg_duration, 1) if avg_duration else None,
                'by_type': list(by_type),
            },
            'count': total,
            'records': [{
                'id': r.id,
                'seizure_type': r.seizure_type,
                'occurred_at': r.occurred_at.isoformat(),
                'duration_seconds': r.duration_seconds,
                'duration_minutes': r.duration_minutes,
                'consciousness': r.consciousness,
                'warning_signs': r.warning_signs,
                'potential_trigger': r.potential_trigger,
                'body_parts_affected': r.body_parts_affected,
                'fell_down': r.fell_down,
                'injury_occurred': r.injury_occurred,
                'injury_description': r.injury_description,
                'recovery_time_minutes': r.recovery_time_minutes,
                'post_seizure_symptoms': r.post_seizure_symptoms,
                'emergency_services_called': r.emergency_services_called,
                'witnessed_by': r.witnessed_by,
                'notes': r.notes,
                'created_at': r.created_at.isoformat(),
            } for r in paginated],
        })

    # POST
    required = ['occurred_at', 'duration_seconds', 'seizure_type']
    for field in required:
        if not request.data.get(field):
            return Response({'error': f'{field} is required'}, status=400)

    # Patients log their own, doctors can log for patients
    patient_id = request.data.get('patient_id')
    if patient_id and user.role in ['doctor', 'admin']:
        try:
            target_patient = User.objects.get(id=patient_id, role='patient')
        except User.DoesNotExist:
            return Response({'error': 'Patient not found'}, status=404)
    else:
        target_patient = user

    record = SeizureRecord.objects.create(
        patient=target_patient,
        seizure_type=request.data.get('seizure_type', 'unknown'),
        occurred_at=request.data.get('occurred_at'),
        duration_seconds=int(request.data.get('duration_seconds')),
        consciousness=request.data.get('consciousness', 'lost'),
        warning_signs=request.data.get('warning_signs', ''),
        potential_trigger=request.data.get('potential_trigger', ''),
        body_parts_affected=request.data.get('body_parts_affected', []),
        fell_down=request.data.get('fell_down', False),
        injury_occurred=request.data.get('injury_occurred', False),
        injury_description=request.data.get('injury_description', ''),
        recovery_time_minutes=request.data.get('recovery_time_minutes'),
        post_seizure_symptoms=request.data.get('post_seizure_symptoms', ''),
        emergency_services_called=request.data.get('emergency_services_called', False),
        witnessed_by=request.data.get('witnessed_by', ''),
        recorded_by=user,
        notes=request.data.get('notes', ''),
    )

    return Response({
        'message': 'Seizure record added successfully',
        'id': record.id,
        'seizure_type': record.seizure_type,
        'occurred_at': record.occurred_at.isoformat(),
        'duration_seconds': record.duration_seconds,
    }, status=201)


@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated])
def neurology_visits(request):
    """Get or add neurology visit records"""
    user = request.user

    if request.method == 'GET':
        patient_id = request.query_params.get('patient_id')
        if patient_id and user.role in ['doctor', 'admin']:
            visits = NeurologyVisit.objects.filter(
                patient_id=patient_id
            ).select_related('doctor')
        elif user.role == 'patient':
            visits = NeurologyVisit.objects.filter(
                patient=user
            ).select_related('doctor')
        elif user.role == 'doctor':
            visits = NeurologyVisit.objects.filter(
                doctor=user
            ).select_related('patient')
        else:
            visits = NeurologyVisit.objects.all().select_related('doctor', 'patient')

        return Response({
            'count': visits.count(),
            'visits': [{
                'id': v.id,
                'visit_date': str(v.visit_date),
                'doctor': v.doctor.full_name if v.doctor else None,
                'patient': v.patient.full_name,
                'diagnosis': v.diagnosis,
                'symptoms_reported': v.symptoms_reported,
                'examination_findings': v.examination_findings,
                'medications_prescribed': v.medications_prescribed,
                'tests_ordered': v.tests_ordered,
                'next_visit': str(v.next_visit) if v.next_visit else None,
                'notes': v.notes,
            } for v in visits],
        })

    # POST — doctors only
    if user.role not in ['doctor', 'admin']:
        return Response({'error': 'Only doctors can add neurology visits'}, status=403)

    patient_id = request.data.get('patient_id')
    if not patient_id:
        return Response({'error': 'patient_id is required'}, status=400)

    try:
        target_patient = User.objects.get(id=patient_id, role='patient')
    except User.DoesNotExist:
        return Response({'error': 'Patient not found'}, status=404)

    if not request.data.get('visit_date'):
        return Response({'error': 'visit_date is required'}, status=400)

    visit = NeurologyVisit.objects.create(
        patient=target_patient,
        doctor=user,
        visit_date=request.data.get('visit_date'),
        diagnosis=request.data.get('diagnosis', ''),
        symptoms_reported=request.data.get('symptoms_reported', ''),
        examination_findings=request.data.get('examination_findings', ''),
        medications_prescribed=request.data.get('medications_prescribed', []),
        tests_ordered=request.data.get('tests_ordered', []),
        next_visit=request.data.get('next_visit'),
        notes=request.data.get('notes', ''),
    )

    create_notification(
        recipient=target_patient,
        sender=user,
        notification_type='general',
        title='Neurology Visit Added',
        message=f'Dr. {user.full_name} added a neurology visit record for {visit.visit_date}.',
        link='/neurology/',
    )

    return Response({
        'message': 'Neurology visit added successfully',
        'id': visit.id,
        'visit_date': str(visit.visit_date),
        'diagnosis': visit.diagnosis,
    }, status=201)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def neurology_summary(request, patient_id=None):
    """AI-powered neurology summary for a patient"""
    user = request.user

    if user.role == 'patient':
        target_patient = user
    elif user.role in ['doctor', 'admin']:
        if not patient_id:
            return Response({'error': 'patient_id is required'}, status=400)
        try:
            target_patient = User.objects.get(id=patient_id, role='patient')
        except User.DoesNotExist:
            return Response({'error': 'Patient not found'}, status=404)
    else:
        return Response({'error': 'Permission denied'}, status=403)

    headaches = HeadacheDiary.objects.filter(patient=target_patient)
    seizures = SeizureRecord.objects.filter(patient=target_patient)
    visits = NeurologyVisit.objects.filter(patient=target_patient).select_related('doctor')

    if not headaches.exists() and not seizures.exists() and not visits.exists():
        return Response({
            'patient_name': target_patient.full_name,
            'summary': 'No neurological history found.',
            'headache_count': 0,
            'seizure_count': 0,
        })

    from django.db.models import Avg, Count
    headache_stats = headaches.aggregate(
        count=Count('id'),
        avg_severity=Avg('severity')
    )
    seizure_count = seizures.count()

    headache_text = f"Total headaches: {headache_stats['count']}, avg severity: {round(headache_stats['avg_severity'] or 0, 1)}/10"
    seizure_text = f"Total seizures: {seizure_count}"
    if seizures.exists():
        latest_seizure = seizures.first()
        seizure_text += f", latest: {latest_seizure.seizure_type} on {latest_seizure.occurred_at.date()}"

    visits_text = "\n".join([
        f"- {v.visit_date}: {v.diagnosis or 'No diagnosis'} (Dr. {v.doctor.full_name if v.doctor else 'Unknown'})"
        for v in visits[:5]
    ])

    prompt = f"""Ты невролог-ассистент. Проанализируй неврологическую историю пациента.

Пациент: {target_patient.full_name}

Головные боли: {headache_text}
Судороги/приступы: {seizure_text}
Визиты к неврологу:
{visits_text if visits_text else 'Нет'}

Дай краткое профессиональное резюме на русском языке:
1. **Общая картина**
2. **Основные проблемы**
3. **Паттерны и триггеры** (если есть)
4. **Рекомендации**
5. **Тревожные симптомы** (если есть 🔴)"""

    try:
        import anthropic
        from django.conf import settings as django_settings
        claude_client = anthropic.Anthropic(api_key=django_settings.ANTHROPIC_API_KEY)
        response = claude_client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=800,
            messages=[{'role': 'user', 'content': prompt}],
        )
        return Response({
            'patient_name': target_patient.full_name,
            'generated_at': timezone.now().isoformat(),
            'headache_count': headache_stats['count'],
            'seizure_count': seizure_count,
            'visit_count': visits.count(),
            'summary': response.content[0].text,
        })
    except Exception as e:
        return Response({'error': f'Summary failed: {str(e)}'}, status=500)


# PHARMACY MODULE

from .models import PatientMedication, MedicationIntakeLog, DrugInteractionCheck


@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated])
def patient_medications(request):
    """Get or add medications for a patient"""
    user = request.user

    if request.method == 'GET':
        patient_id = request.query_params.get('patient_id')
        if patient_id and user.role in ['doctor', 'admin']:
            meds = PatientMedication.objects.filter(
                patient_id=patient_id
            ).select_related('prescribed_by')
        else:
            meds = PatientMedication.objects.filter(
                patient=user
            ).select_related('prescribed_by')

        status_filter = request.query_params.get('status')
        if status_filter:
            meds = meds.filter(status=status_filter)

        # Refill alerts
        refill_soon = []
        for med in meds.filter(status='active'):
            if med.days_until_refill is not None and med.days_until_refill <= 7:
                refill_soon.append({
                    'id': med.id,
                    'medication_name': med.medication_name,
                    'days_until_refill': med.days_until_refill,
                    'refills_remaining': med.refills_remaining,
                })

        return Response({
            'count': meds.count(),
            'refill_alerts': refill_soon,
            'medications': [{
                'id': m.id,
                'medication_name': m.medication_name,
                'generic_name': m.generic_name,
                'dosage': m.dosage,
                'frequency': m.frequency,
                'frequency_custom': m.frequency_custom,
                'route': m.route,
                'start_date': str(m.start_date),
                'end_date': str(m.end_date) if m.end_date else None,
                'status': m.status,
                'purpose': m.purpose,
                'instructions': m.instructions,
                'side_effects_experienced': m.side_effects_experienced,
                'refills_remaining': m.refills_remaining,
                'last_refill_date': str(m.last_refill_date) if m.last_refill_date else None,
                'next_refill_date': str(m.next_refill_date) if m.next_refill_date else None,
                'days_until_refill': m.days_until_refill,
                'prescribed_by': m.prescribed_by.full_name if m.prescribed_by else None,
                'notes': m.notes,
                'created_at': m.created_at.isoformat(),
            } for m in meds],
        })

    # POST — doctors add, patients can add OTC meds
    required = ['medication_name', 'dosage', 'start_date']
    for field in required:
        if not request.data.get(field):
            return Response({'error': f'{field} is required'}, status=400)

    patient_id = request.data.get('patient_id')
    if patient_id and user.role in ['doctor', 'admin']:
        try:
            target_patient = User.objects.get(id=patient_id, role='patient')
        except User.DoesNotExist:
            return Response({'error': 'Patient not found'}, status=404)
        prescribed_by = user
    else:
        target_patient = user
        prescribed_by = None

    med = PatientMedication.objects.create(
        patient=target_patient,
        prescribed_by=prescribed_by,
        medication_name=request.data.get('medication_name'),
        generic_name=request.data.get('generic_name', ''),
        dosage=request.data.get('dosage'),
        frequency=request.data.get('frequency', 'once_daily'),
        frequency_custom=request.data.get('frequency_custom', ''),
        route=request.data.get('route', ''),
        start_date=request.data.get('start_date'),
        end_date=request.data.get('end_date'),
        status='active',
        purpose=request.data.get('purpose', ''),
        instructions=request.data.get('instructions', ''),
        refills_remaining=request.data.get('refills_remaining', 0),
        next_refill_date=request.data.get('next_refill_date'),
        notes=request.data.get('notes', ''),
    )

    # Notify patient if doctor added it
    if prescribed_by:
        create_notification(
            recipient=target_patient,
            sender=user,
            notification_type='general',
            title='New Medication Prescribed',
            message=f'Dr. {user.full_name} prescribed {med.medication_name} {med.dosage}.',
            link='/pharmacy/',
        )

    return Response({
        'message': 'Medication added successfully',
        'id': med.id,
        'medication_name': med.medication_name,
        'dosage': med.dosage,
        'frequency': med.frequency,
        'status': med.status,
    }, status=201)


@api_view(['GET', 'PATCH', 'DELETE'])
@permission_classes([IsAuthenticated])
def medication_detail(request, med_id):
    """Get, update or delete a medication record"""
    try:
        med = PatientMedication.objects.get(id=med_id)
    except PatientMedication.DoesNotExist:
        return Response({'error': 'Medication not found'}, status=404)

    user = request.user
    if med.patient != user and user.role not in ['doctor', 'admin']:
        return Response({'error': 'Permission denied'}, status=403)

    if request.method == 'GET':
        logs = MedicationIntakeLog.objects.filter(medication=med)[:10]
        return Response({
            'id': med.id,
            'medication_name': med.medication_name,
            'dosage': med.dosage,
            'frequency': med.frequency,
            'status': med.status,
            'start_date': str(med.start_date),
            'end_date': str(med.end_date) if med.end_date else None,
            'purpose': med.purpose,
            'instructions': med.instructions,
            'side_effects_experienced': med.side_effects_experienced,
            'refills_remaining': med.refills_remaining,
            'next_refill_date': str(med.next_refill_date) if med.next_refill_date else None,
            'days_until_refill': med.days_until_refill,
            'notes': med.notes,
            'recent_logs': [{
                'status': l.status,
                'scheduled_time': l.scheduled_time.isoformat(),
                'taken_at': l.taken_at.isoformat() if l.taken_at else None,
                'notes': l.notes,
            } for l in logs],
        })

    if request.method == 'PATCH':
        updatable = [
            'status', 'end_date', 'refills_remaining', 'last_refill_date',
            'next_refill_date', 'side_effects_experienced', 'notes',
            'instructions', 'dosage', 'frequency'
        ]
        for field in updatable:
            if field in request.data:
                setattr(med, field, request.data[field])
        med.save()
        return Response({'message': 'Medication updated successfully'})

    if request.method == 'DELETE':
        if med.patient != user and user.role != 'admin':
            return Response({'error': 'Permission denied'}, status=403)
        med.delete()
        return Response({'message': 'Medication deleted successfully'})


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def log_medication_intake(request, med_id):
    """Log a medication intake event"""
    try:
        med = PatientMedication.objects.get(id=med_id)
    except PatientMedication.DoesNotExist:
        return Response({'error': 'Medication not found'}, status=404)

    if med.patient != request.user:
        return Response({'error': 'Permission denied'}, status=403)

    status_val = request.data.get('status', 'taken')
    if status_val not in ['taken', 'missed', 'skipped', 'delayed']:
        return Response({'error': 'Invalid status'}, status=400)

    log = MedicationIntakeLog.objects.create(
        medication=med,
        scheduled_time=request.data.get('scheduled_time', timezone.now()),
        taken_at=timezone.now() if status_val == 'taken' else None,
        status=status_val,
        notes=request.data.get('notes', ''),
    )

    return Response({
        'message': f'Medication intake logged as {status_val}',
        'log_id': log.id,
        'medication': med.medication_name,
        'status': status_val,
        'taken_at': log.taken_at.isoformat() if log.taken_at else None,
    }, status=201)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def check_drug_interactions(request):
    """AI-powered drug interaction checker"""
    user = request.user
    medications = request.data.get('medications', [])

    if len(medications) < 2:
        return Response({
            'error': 'At least 2 medications are required to check interactions'
        }, status=400)

    if len(medications) > 10:
        return Response({'error': 'Maximum 10 medications per check'}, status=400)

    # Get patient's active meds to add context
    patient_id = request.data.get('patient_id')
    if patient_id and user.role in ['doctor', 'admin']:
        try:
            target_patient = User.objects.get(id=patient_id)
        except User.DoesNotExist:
            target_patient = user
    else:
        target_patient = user

    meds_list = "\n".join([f"- {m}" for m in medications])

    prompt = f"""Ты клинический фармацевт. Проверь взаимодействие между следующими препаратами и дай профессиональное заключение на русском языке.

Препараты для проверки:
{meds_list}

Ответь ТОЛЬКО в формате JSON (без markdown, без лишнего текста):
{{
  "severity": "none|minor|moderate|major|contraindicated",
  "interaction_found": true/false,
  "interactions": [
    {{
      "drug1": "название препарата 1",
      "drug2": "название препарата 2", 
      "severity": "minor|moderate|major|contraindicated",
      "description": "описание взаимодействия",
      "recommendation": "рекомендация"
    }}
  ],
  "general_recommendations": "общие рекомендации",
  "consult_doctor": true/false,
  "summary": "краткое резюме на русском (2-3 предложения)"
}}"""

    try:
        import anthropic
        from django.conf import settings as django_settings
        claude_client = anthropic.Anthropic(api_key=django_settings.ANTHROPIC_API_KEY)
        response = claude_client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=1000,
            messages=[{'role': 'user', 'content': prompt}],
        )

        raw = response.content[0].text.strip()
        if '```' in raw:
            raw = raw.split('```')[1]
            if raw.startswith('json'):
                raw = raw[4:]

        analysis = json.loads(raw)

        # Save the check
        check = DrugInteractionCheck.objects.create(
            patient=target_patient,
            medications_checked=medications,
            interaction_found=analysis.get('interaction_found', False),
            severity=analysis.get('severity', 'none'),
            ai_analysis=analysis.get('summary', ''),
            checked_by=user,
        )

        return Response({
            'check_id': check.id,
            'medications_checked': medications,
            'checked_at': check.checked_at.isoformat(),
            'analysis': analysis,
        })

    except json.JSONDecodeError:
        return Response({'error': 'Failed to parse AI response'}, status=500)
    except Exception as e:
        return Response({'error': f'Interaction check failed: {str(e)}'}, status=500)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def pharmacy_summary(request, patient_id=None):
    """AI-powered pharmacy summary — full medication overview"""
    user = request.user

    if user.role == 'patient':
        target_patient = user
    elif user.role in ['doctor', 'admin']:
        if not patient_id:
            return Response({'error': 'patient_id is required'}, status=400)
        try:
            target_patient = User.objects.get(id=patient_id, role='patient')
        except User.DoesNotExist:
            return Response({'error': 'Patient not found'}, status=404)
    else:
        return Response({'error': 'Permission denied'}, status=403)

    active_meds = PatientMedication.objects.filter(
        patient=target_patient, status='active'
    ).select_related('prescribed_by')

    all_meds = PatientMedication.objects.filter(
        patient=target_patient
    ).select_related('prescribed_by')

    if not all_meds.exists():
        return Response({
            'patient_name': target_patient.full_name,
            'active_count': 0,
            'summary': 'Нет данных о принимаемых препаратах.',
        })

    active_text = "\n".join([
        f"- {m.medication_name} {m.dosage} ({m.frequency})"
        f"{' — prescribed by Dr.' + m.prescribed_by.full_name if m.prescribed_by else ''}"
        for m in active_meds
    ])

    refill_alerts = [
        m for m in active_meds
        if m.days_until_refill is not None and m.days_until_refill <= 7
    ]

    prompt = f"""Ты клинический фармацевт. Проанализируй схему лечения пациента.

Пациент: {target_patient.full_name}

Активные препараты:
{active_text if active_text else 'Нет активных препаратов'}

Всего препаратов в истории: {all_meds.count()}
Требуют пополнения в течение 7 дней: {len(refill_alerts)}

Дай краткое профессиональное резюме на русском:
1. **Текущая схема лечения**
2. **Потенциальные взаимодействия** (если есть)
3. **Рекомендации по приёму**
4. **Предупреждения** (если есть 🔴)"""

    try:
        import anthropic
        from django.conf import settings as django_settings
        claude_client = anthropic.Anthropic(api_key=django_settings.ANTHROPIC_API_KEY)
        response = claude_client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=800,
            messages=[{'role': 'user', 'content': prompt}],
        )

        return Response({
            'patient_name': target_patient.full_name,
            'generated_at': timezone.now().isoformat(),
            'active_count': active_meds.count(),
            'total_count': all_meds.count(),
            'refill_alerts_count': len(refill_alerts),
            'summary': response.content[0].text,
        })

    except Exception as e:
        return Response({'error': f'Summary failed: {str(e)}'}, status=500)
    
# ============================================
# OPHTHALMOLOGY MODULE
# ============================================

from .models import EyeExam, VisionPrescription, EyeCondition


@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated])
def eye_exams(request):
    """Get or add eye exam records"""
    user = request.user

    if request.method == 'GET':
        patient_id = request.query_params.get('patient_id')
        if patient_id and user.role in ['doctor', 'admin']:
            exams = EyeExam.objects.filter(
                patient_id=patient_id
            ).select_related('doctor')
        elif user.role == 'patient':
            exams = EyeExam.objects.filter(
                patient=user
            ).select_related('doctor')
        elif user.role == 'doctor':
            exams = EyeExam.objects.filter(
                doctor=user
            ).select_related('patient')
        else:
            exams = EyeExam.objects.all().select_related('doctor', 'patient')

        return Response({
            'count': exams.count(),
            'exams': [{
                'id': e.id,
                'exam_date': str(e.exam_date),
                'exam_type': e.exam_type,
                'doctor': e.doctor.full_name if e.doctor else None,
                'va_right_eye': e.va_right_eye,
                'va_left_eye': e.va_left_eye,
                'va_right_corrected': e.va_right_corrected,
                'va_left_corrected': e.va_left_corrected,
                'iop_right': e.iop_right,
                'iop_left': e.iop_left,
                'diagnosis': e.diagnosis,
                'findings': e.findings,
                'recommendations': e.recommendations,
                'next_exam_date': str(e.next_exam_date) if e.next_exam_date else None,
                'notes': e.notes,
            } for e in exams],
        })

    # POST — doctors only
    if user.role not in ['doctor', 'admin']:
        return Response({'error': 'Only doctors can add eye exam records'}, status=403)

    patient_id = request.data.get('patient_id')
    if not patient_id:
        return Response({'error': 'patient_id is required'}, status=400)

    try:
        target_patient = User.objects.get(id=patient_id, role='patient')
    except User.DoesNotExist:
        return Response({'error': 'Patient not found'}, status=404)

    if not request.data.get('exam_date'):
        return Response({'error': 'exam_date is required'}, status=400)

    exam = EyeExam.objects.create(
        patient=target_patient,
        doctor=user,
        exam_date=request.data.get('exam_date'),
        exam_type=request.data.get('exam_type', 'routine'),
        va_right_eye=request.data.get('va_right_eye', ''),
        va_left_eye=request.data.get('va_left_eye', ''),
        va_right_corrected=request.data.get('va_right_corrected', ''),
        va_left_corrected=request.data.get('va_left_corrected', ''),
        iop_right=request.data.get('iop_right'),
        iop_left=request.data.get('iop_left'),
        diagnosis=request.data.get('diagnosis', ''),
        findings=request.data.get('findings', ''),
        recommendations=request.data.get('recommendations', ''),
        next_exam_date=request.data.get('next_exam_date'),
        notes=request.data.get('notes', ''),
    )

    create_notification(
        recipient=target_patient,
        sender=user,
        notification_type='general',
        title='Eye Exam Record Added',
        message=f'Dr. {user.full_name} added your eye exam record for {exam.exam_date}.',
        link='/ophthalmology/',
    )

    return Response({
        'message': 'Eye exam added successfully',
        'id': exam.id,
        'exam_date': str(exam.exam_date),
        'exam_type': exam.exam_type,
    }, status=201)


@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated])
def vision_prescriptions(request):
    """Get or add vision prescriptions"""
    user = request.user

    if request.method == 'GET':
        patient_id = request.query_params.get('patient_id')
        if patient_id and user.role in ['doctor', 'admin']:
            prescriptions = VisionPrescription.objects.filter(
                patient_id=patient_id
            ).select_related('doctor')
        else:
            prescriptions = VisionPrescription.objects.filter(
                patient=user
            ).select_related('doctor')

        return Response({
            'count': prescriptions.count(),
            'prescriptions': [{
                'id': p.id,
                'prescription_type': p.prescription_type,
                'issued_date': str(p.issued_date),
                'expiry_date': str(p.expiry_date) if p.expiry_date else None,
                'is_expired': p.is_expired,
                'doctor': p.doctor.full_name if p.doctor else None,
                'right_eye': {
                    'sphere': p.right_sphere,
                    'cylinder': p.right_cylinder,
                    'axis': p.right_axis,
                    'add': p.right_add,
                    'pd': p.right_pd,
                },
                'left_eye': {
                    'sphere': p.left_sphere,
                    'cylinder': p.left_cylinder,
                    'axis': p.left_axis,
                    'add': p.left_add,
                    'pd': p.left_pd,
                },
                'notes': p.notes,
            } for p in prescriptions],
        })

    # POST — doctors only
    if user.role not in ['doctor', 'admin']:
        return Response({'error': 'Only doctors can issue vision prescriptions'}, status=403)

    patient_id = request.data.get('patient_id')
    if not patient_id:
        return Response({'error': 'patient_id is required'}, status=400)

    try:
        target_patient = User.objects.get(id=patient_id, role='patient')
    except User.DoesNotExist:
        return Response({'error': 'Patient not found'}, status=404)

    if not request.data.get('issued_date'):
        return Response({'error': 'issued_date is required'}, status=400)

    exam_id = request.data.get('exam_id')
    exam = None
    if exam_id:
        try:
            exam = EyeExam.objects.get(id=exam_id, patient=target_patient)
        except EyeExam.DoesNotExist:
            pass

    prescription = VisionPrescription.objects.create(
        patient=target_patient,
        doctor=user,
        exam=exam,
        prescription_type=request.data.get('prescription_type', 'glasses'),
        issued_date=request.data.get('issued_date'),
        expiry_date=request.data.get('expiry_date'),
        right_sphere=request.data.get('right_sphere'),
        right_cylinder=request.data.get('right_cylinder'),
        right_axis=request.data.get('right_axis'),
        right_add=request.data.get('right_add'),
        right_pd=request.data.get('right_pd'),
        left_sphere=request.data.get('left_sphere'),
        left_cylinder=request.data.get('left_cylinder'),
        left_axis=request.data.get('left_axis'),
        left_add=request.data.get('left_add'),
        left_pd=request.data.get('left_pd'),
        notes=request.data.get('notes', ''),
    )

    create_notification(
        recipient=target_patient,
        sender=user,
        notification_type='general',
        title='New Vision Prescription',
        message=f'Dr. {user.full_name} issued a new {prescription.prescription_type} prescription.',
        link='/ophthalmology/prescriptions/',
    )

    return Response({
        'message': 'Vision prescription added successfully',
        'id': prescription.id,
        'prescription_type': prescription.prescription_type,
        'issued_date': str(prescription.issued_date),
    }, status=201)


@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated])
def eye_conditions(request):
    """Get or add eye conditions"""
    user = request.user

    if request.method == 'GET':
        patient_id = request.query_params.get('patient_id')
        if patient_id and user.role in ['doctor', 'admin']:
            conditions = EyeCondition.objects.filter(
                patient_id=patient_id
            ).select_related('doctor')
        else:
            conditions = EyeCondition.objects.filter(
                patient=user
            ).select_related('doctor')

        return Response({
            'count': conditions.count(),
            'conditions': [{
                'id': c.id,
                'condition': c.condition,
                'affected_eye': c.affected_eye,
                'status': c.status,
                'diagnosed_date': str(c.diagnosed_date) if c.diagnosed_date else None,
                'doctor': c.doctor.full_name if c.doctor else None,
                'notes': c.notes,
                'created_at': c.created_at.isoformat(),
            } for c in conditions],
        })

    # POST — doctors only
    if user.role not in ['doctor', 'admin']:
        return Response({'error': 'Only doctors can add eye conditions'}, status=403)

    patient_id = request.data.get('patient_id')
    if not patient_id or not request.data.get('condition'):
        return Response({'error': 'patient_id and condition are required'}, status=400)

    try:
        target_patient = User.objects.get(id=patient_id, role='patient')
    except User.DoesNotExist:
        return Response({'error': 'Patient not found'}, status=404)

    condition = EyeCondition.objects.create(
        patient=target_patient,
        doctor=user,
        condition=request.data.get('condition'),
        affected_eye=request.data.get('affected_eye', 'both'),
        status=request.data.get('status', 'active'),
        diagnosed_date=request.data.get('diagnosed_date'),
        notes=request.data.get('notes', ''),
    )

    return Response({
        'message': 'Eye condition added successfully',
        'id': condition.id,
        'condition': condition.condition,
        'status': condition.status,
    }, status=201)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def ophthalmology_summary(request, patient_id=None):
    """AI-powered ophthalmology summary"""
    user = request.user

    if user.role == 'patient':
        target_patient = user
    elif user.role in ['doctor', 'admin']:
        if not patient_id:
            return Response({'error': 'patient_id is required'}, status=400)
        try:
            target_patient = User.objects.get(id=patient_id, role='patient')
        except User.DoesNotExist:
            return Response({'error': 'Patient not found'}, status=404)
    else:
        return Response({'error': 'Permission denied'}, status=403)

    exams = EyeExam.objects.filter(patient=target_patient)
    prescriptions = VisionPrescription.objects.filter(patient=target_patient)
    conditions = EyeCondition.objects.filter(patient=target_patient)

    if not exams.exists() and not conditions.exists():
        return Response({
            'patient_name': target_patient.full_name,
            'summary': 'Нет данных об офтальмологических обследованиях.',
            'exam_count': 0,
            'condition_count': 0,
        })

    latest_exam = exams.first()
    exam_text = ""
    if latest_exam:
        exam_text = (
            f"Последний осмотр: {latest_exam.exam_date}\n"
            f"Острота зрения (без коррекции): OD {latest_exam.va_right_eye}, OS {latest_exam.va_left_eye}\n"
            f"Острота зрения (с коррекцией): OD {latest_exam.va_right_corrected}, OS {latest_exam.va_left_corrected}\n"
            f"ВГД: OD {latest_exam.iop_right} mmHg, OS {latest_exam.iop_left} mmHg\n"
            f"Диагноз: {latest_exam.diagnosis}"
        )

    conditions_text = "\n".join([
        f"- {c.condition} ({c.affected_eye} eye, {c.status})"
        for c in conditions
    ])

    latest_rx = prescriptions.first()
    rx_text = ""
    if latest_rx:
        rx_text = (
            f"Рецепт ({latest_rx.prescription_type}, {latest_rx.issued_date}):\n"
            f"OD: SPH {latest_rx.right_sphere}, CYL {latest_rx.right_cylinder}, AXIS {latest_rx.right_axis}\n"
            f"OS: SPH {latest_rx.left_sphere}, CYL {latest_rx.left_cylinder}, AXIS {latest_rx.left_axis}"
        )

    prompt = f"""Ты офтальмолог-ассистент. Проанализируй историю зрения пациента.

Пациент: {target_patient.full_name}

{exam_text}

Заболевания глаз:
{conditions_text if conditions_text else 'Нет'}

{rx_text}

Дай краткое профессиональное резюме на русском:
1. **Состояние зрения**
2. **Диагнозы и заболевания**
3. **Динамика** (если есть несколько осмотров)
4. **Рекомендации**
5. **Тревожные симптомы** (если есть 🔴)"""

    try:
        import anthropic
        from django.conf import settings as django_settings
        claude_client = anthropic.Anthropic(api_key=django_settings.ANTHROPIC_API_KEY)
        response = claude_client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=800,
            messages=[{'role': 'user', 'content': prompt}],
        )

        return Response({
            'patient_name': target_patient.full_name,
            'generated_at': timezone.now().isoformat(),
            'exam_count': exams.count(),
            'condition_count': conditions.count(),
            'prescription_count': prescriptions.count(),
            'summary': response.content[0].text,
        })

    except Exception as e:
        return Response({'error': f'Summary failed: {str(e)}'}, status=500)
    
# ============================================
# CARDIOLOGY MODULE
# ============================================

from .models import BloodPressureLog, ECGRecord, HeartCondition, CardiologyVisit


@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated])
def blood_pressure_logs(request):
    """Get or add blood pressure logs"""
    user = request.user

    if request.method == 'GET':
        patient_id = request.query_params.get('patient_id')
        if patient_id and user.role in ['doctor', 'admin']:
            logs = BloodPressureLog.objects.filter(patient_id=patient_id)
        else:
            logs = BloodPressureLog.objects.filter(patient=user)

        date_from = request.query_params.get('date_from')
        if date_from:
            logs = logs.filter(measured_at__date__gte=date_from)

        date_to = request.query_params.get('date_to')
        if date_to:
            logs = logs.filter(measured_at__date__lte=date_to)

        from django.db.models import Avg, Max, Min, Count
        stats = logs.aggregate(
            avg_systolic=Avg('systolic'),
            avg_diastolic=Avg('diastolic'),
            avg_pulse=Avg('pulse'),
            max_systolic=Max('systolic'),
            min_systolic=Min('systolic'),
            total=Count('id'),
        )

        page = int(request.query_params.get('page', 1))
        page_size = int(request.query_params.get('page_size', 20))
        start = (page - 1) * page_size
        paginated = logs[start:start + page_size]

        return Response({
            'stats': {
                'total': stats['total'],
                'avg_systolic': round(stats['avg_systolic'], 1) if stats['avg_systolic'] else None,
                'avg_diastolic': round(stats['avg_diastolic'], 1) if stats['avg_diastolic'] else None,
                'avg_pulse': round(stats['avg_pulse'], 1) if stats['avg_pulse'] else None,
                'max_systolic': stats['max_systolic'],
                'min_systolic': stats['min_systolic'],
            },
            'count': stats['total'],
            'page': page,
            'logs': [{
                'id': l.id,
                'systolic': l.systolic,
                'diastolic': l.diastolic,
                'pulse': l.pulse,
                'position': l.position,
                'arm': l.arm,
                'measured_at': l.measured_at.isoformat(),
                'category': l.category,
                'category_label': l.category_label,
                'notes': l.notes,
            } for l in paginated],
        })

    # POST — patients and doctors can log BP
    required = ['systolic', 'diastolic', 'measured_at']
    for field in required:
        if not request.data.get(field):
            return Response({'error': f'{field} is required'}, status=400)

    patient_id = request.data.get('patient_id')
    if patient_id and user.role in ['doctor', 'admin']:
        try:
            target_patient = User.objects.get(id=patient_id, role='patient')
        except User.DoesNotExist:
            return Response({'error': 'Patient not found'}, status=404)
    else:
        target_patient = user

    systolic = int(request.data.get('systolic'))
    diastolic = int(request.data.get('diastolic'))

    if systolic < 50 or systolic > 300:
        return Response({'error': 'Invalid systolic value'}, status=400)
    if diastolic < 30 or diastolic > 200:
        return Response({'error': 'Invalid diastolic value'}, status=400)

    log = BloodPressureLog.objects.create(
        patient=target_patient,
        recorded_by=user if user != target_patient else None,
        systolic=systolic,
        diastolic=diastolic,
        pulse=request.data.get('pulse'),
        position=request.data.get('position', 'sitting'),
        arm=request.data.get('arm', 'left'),
        measured_at=request.data.get('measured_at'),
        notes=request.data.get('notes', ''),
    )

    # Alert if BP is critical
    if log.category in ['high_stage2', 'crisis']:
        create_notification(
            recipient=target_patient,
            sender=None,
            notification_type='general',
            title='⚠️ High Blood Pressure Alert',
            message=f'Your BP reading {systolic}/{diastolic} mmHg is {log.category_label}. Please consult your doctor.',
            link='/cardiology/',
        )

    return Response({
        'message': 'Blood pressure logged successfully',
        'id': log.id,
        'systolic': log.systolic,
        'diastolic': log.diastolic,
        'category': log.category,
        'category_label': log.category_label,
    }, status=201)


@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated])
def ecg_records(request):
    """Get or add ECG records"""
    user = request.user

    if request.method == 'GET':
        patient_id = request.query_params.get('patient_id')
        if patient_id and user.role in ['doctor', 'admin']:
            records = ECGRecord.objects.filter(
                patient_id=patient_id
            ).select_related('doctor')
        elif user.role == 'patient':
            records = ECGRecord.objects.filter(
                patient=user
            ).select_related('doctor')
        elif user.role == 'doctor':
            records = ECGRecord.objects.filter(
                doctor=user
            ).select_related('patient')
        else:
            records = ECGRecord.objects.all().select_related('doctor', 'patient')

        return Response({
            'count': records.count(),
            'records': [{
                'id': r.id,
                'recorded_at': r.recorded_at.isoformat(),
                'heart_rate': r.heart_rate,
                'rhythm': r.rhythm,
                'pr_interval': r.pr_interval,
                'qrs_duration': r.qrs_duration,
                'qt_interval': r.qt_interval,
                'qtc_interval': r.qtc_interval,
                'axis': r.axis,
                'interpretation': r.interpretation,
                'is_abnormal': r.is_abnormal,
                'ecg_file': request.build_absolute_uri(r.ecg_file.url) if r.ecg_file else None,
                'doctor': r.doctor.full_name if r.doctor else None,
                'notes': r.notes,
            } for r in records],
        })

    # POST — doctors only
    if user.role not in ['doctor', 'admin']:
        return Response({'error': 'Only doctors can add ECG records'}, status=403)

    patient_id = request.data.get('patient_id')
    if not patient_id:
        return Response({'error': 'patient_id is required'}, status=400)

    try:
        target_patient = User.objects.get(id=patient_id, role='patient')
    except User.DoesNotExist:
        return Response({'error': 'Patient not found'}, status=404)

    if not request.data.get('recorded_at'):
        return Response({'error': 'recorded_at is required'}, status=400)

    record = ECGRecord.objects.create(
        patient=target_patient,
        doctor=user,
        recorded_at=request.data.get('recorded_at'),
        heart_rate=request.data.get('heart_rate'),
        rhythm=request.data.get('rhythm', 'normal_sinus'),
        pr_interval=request.data.get('pr_interval'),
        qrs_duration=request.data.get('qrs_duration'),
        qt_interval=request.data.get('qt_interval'),
        qtc_interval=request.data.get('qtc_interval'),
        axis=request.data.get('axis', ''),
        interpretation=request.data.get('interpretation', ''),
        is_abnormal=request.data.get('is_abnormal', False),
        notes=request.data.get('notes', ''),
    )

    # Handle ECG file upload
    if 'ecg_file' in request.FILES:
        record.ecg_file = request.FILES['ecg_file']
        record.save()

    if record.is_abnormal:
        create_notification(
            recipient=target_patient,
            sender=user,
            notification_type='general',
            title='⚠️ Abnormal ECG Result',
            message=f'Dr. {user.full_name} recorded an abnormal ECG. Please review with your doctor.',
            link='/cardiology/ecg/',
        )

    return Response({
        'message': 'ECG record added successfully',
        'id': record.id,
        'rhythm': record.rhythm,
        'is_abnormal': record.is_abnormal,
    }, status=201)


@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated])
def heart_conditions(request):
    """Get or add heart conditions"""
    user = request.user

    if request.method == 'GET':
        patient_id = request.query_params.get('patient_id')
        if patient_id and user.role in ['doctor', 'admin']:
            conditions = HeartCondition.objects.filter(
                patient_id=patient_id
            ).select_related('doctor')
        else:
            conditions = HeartCondition.objects.filter(
                patient=user
            ).select_related('doctor')

        return Response({
            'count': conditions.count(),
            'conditions': [{
                'id': c.id,
                'condition': c.condition,
                'status': c.status,
                'diagnosed_date': str(c.diagnosed_date) if c.diagnosed_date else None,
                'doctor': c.doctor.full_name if c.doctor else None,
                'notes': c.notes,
                'created_at': c.created_at.isoformat(),
            } for c in conditions],
        })

    if user.role not in ['doctor', 'admin']:
        return Response({'error': 'Only doctors can add heart conditions'}, status=403)

    patient_id = request.data.get('patient_id')
    if not patient_id or not request.data.get('condition'):
        return Response({'error': 'patient_id and condition are required'}, status=400)

    try:
        target_patient = User.objects.get(id=patient_id, role='patient')
    except User.DoesNotExist:
        return Response({'error': 'Patient not found'}, status=404)

    condition = HeartCondition.objects.create(
        patient=target_patient,
        doctor=user,
        condition=request.data.get('condition'),
        status=request.data.get('status', 'active'),
        diagnosed_date=request.data.get('diagnosed_date'),
        notes=request.data.get('notes', ''),
    )

    create_notification(
        recipient=target_patient,
        sender=user,
        notification_type='general',
        title='Heart Condition Recorded',
        message=f'Dr. {user.full_name} recorded a heart condition: {condition.condition}.',
        link='/cardiology/',
    )

    return Response({
        'message': 'Heart condition added successfully',
        'id': condition.id,
        'condition': condition.condition,
    }, status=201)


@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated])
def cardiology_visits(request):
    """Get or add cardiology visit records"""
    user = request.user

    if request.method == 'GET':
        patient_id = request.query_params.get('patient_id')
        if patient_id and user.role in ['doctor', 'admin']:
            visits = CardiologyVisit.objects.filter(
                patient_id=patient_id
            ).select_related('doctor')
        elif user.role == 'patient':
            visits = CardiologyVisit.objects.filter(
                patient=user
            ).select_related('doctor')
        elif user.role == 'doctor':
            visits = CardiologyVisit.objects.filter(
                doctor=user
            ).select_related('patient')
        else:
            visits = CardiologyVisit.objects.all().select_related('doctor', 'patient')

        return Response({
            'count': visits.count(),
            'visits': [{
                'id': v.id,
                'visit_date': str(v.visit_date),
                'doctor': v.doctor.full_name if v.doctor else None,
                'patient': v.patient.full_name,
                'chief_complaint': v.chief_complaint,
                'diagnosis': v.diagnosis,
                'examination_findings': v.examination_findings,
                'medications_prescribed': v.medications_prescribed,
                'tests_ordered': v.tests_ordered,
                'lifestyle_recommendations': v.lifestyle_recommendations,
                'next_visit': str(v.next_visit) if v.next_visit else None,
                'notes': v.notes,
            } for v in visits],
        })

    if user.role not in ['doctor', 'admin']:
        return Response({'error': 'Only doctors can add cardiology visits'}, status=403)

    patient_id = request.data.get('patient_id')
    if not patient_id or not request.data.get('visit_date'):
        return Response({'error': 'patient_id and visit_date are required'}, status=400)

    try:
        target_patient = User.objects.get(id=patient_id, role='patient')
    except User.DoesNotExist:
        return Response({'error': 'Patient not found'}, status=404)

    visit = CardiologyVisit.objects.create(
        patient=target_patient,
        doctor=user,
        visit_date=request.data.get('visit_date'),
        chief_complaint=request.data.get('chief_complaint', ''),
        diagnosis=request.data.get('diagnosis', ''),
        examination_findings=request.data.get('examination_findings', ''),
        medications_prescribed=request.data.get('medications_prescribed', []),
        tests_ordered=request.data.get('tests_ordered', []),
        lifestyle_recommendations=request.data.get('lifestyle_recommendations', ''),
        next_visit=request.data.get('next_visit'),
        notes=request.data.get('notes', ''),
    )

    create_notification(
        recipient=target_patient,
        sender=user,
        notification_type='general',
        title='Cardiology Visit Added',
        message=f'Dr. {user.full_name} added a cardiology visit record for {visit.visit_date}.',
        link='/cardiology/',
    )

    return Response({
        'message': 'Cardiology visit added successfully',
        'id': visit.id,
        'visit_date': str(visit.visit_date),
    }, status=201)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def cardiology_summary(request, patient_id=None):
    """AI-powered cardiology summary and cardiac risk assessment"""
    user = request.user

    if user.role == 'patient':
        target_patient = user
    elif user.role in ['doctor', 'admin']:
        if not patient_id:
            return Response({'error': 'patient_id is required'}, status=400)
        try:
            target_patient = User.objects.get(id=patient_id, role='patient')
        except User.DoesNotExist:
            return Response({'error': 'Patient not found'}, status=404)
    else:
        return Response({'error': 'Permission denied'}, status=403)

    bp_logs = BloodPressureLog.objects.filter(patient=target_patient)
    ecgs = ECGRecord.objects.filter(patient=target_patient)
    conditions = HeartCondition.objects.filter(patient=target_patient)
    visits = CardiologyVisit.objects.filter(patient=target_patient)

    if not bp_logs.exists() and not ecgs.exists() and not conditions.exists():
        return Response({
            'patient_name': target_patient.full_name,
            'summary': 'Нет кардиологических данных.',
            'bp_count': 0,
            'ecg_count': 0,
        })

    from django.db.models import Avg
    bp_stats = bp_logs.aggregate(
        avg_sys=Avg('systolic'),
        avg_dia=Avg('diastolic'),
    )

    latest_bp = bp_logs.first()
    bp_text = ""
    if latest_bp:
        bp_text = (
            f"Последнее АД: {latest_bp.systolic}/{latest_bp.diastolic} mmHg "
            f"({latest_bp.category_label}) — {latest_bp.measured_at.date()}\n"
            f"Среднее АД: {round(bp_stats['avg_sys'] or 0, 1)}/{round(bp_stats['avg_dia'] or 0, 1)} mmHg"
        )

    ecg_text = ""
    latest_ecg = ecgs.first()
    if latest_ecg:
        ecg_text = (
            f"Последнее ЭКГ: {latest_ecg.recorded_at.date()}\n"
            f"Ритм: {latest_ecg.rhythm}, ЧСС: {latest_ecg.heart_rate} уд/мин\n"
            f"Патология: {'Да' if latest_ecg.is_abnormal else 'Нет'}"
        )

    conditions_text = "\n".join([
        f"- {c.condition} ({c.status})"
        for c in conditions
    ])

    prompt = f"""Ты кардиолог-ассистент. Проанализируй сердечно-сосудистую историю пациента.

Пациент: {target_patient.full_name}

Артериальное давление:
{bp_text if bp_text else 'Нет данных'}

ЭКГ:
{ecg_text if ecg_text else 'Нет данных'}

Сердечно-сосудистые заболевания:
{conditions_text if conditions_text else 'Нет'}

Дай краткое профессиональное резюме на русском:
1. **Состояние сердечно-сосудистой системы**
2. **Ключевые показатели**
3. **Факторы риска**
4. **Рекомендации**
5. **Тревожные симптомы** (если есть 🔴)"""

    try:
        import anthropic
        from django.conf import settings as django_settings
        claude_client = anthropic.Anthropic(api_key=django_settings.ANTHROPIC_API_KEY)
        response = claude_client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=800,
            messages=[{'role': 'user', 'content': prompt}],
        )

        return Response({
            'patient_name': target_patient.full_name,
            'generated_at': timezone.now().isoformat(),
            'bp_count': bp_logs.count(),
            'ecg_count': ecgs.count(),
            'condition_count': conditions.count(),
            'visit_count': visits.count(),
            'summary': response.content[0].text,
        })

    except Exception as e:
        return Response({'error': f'Summary failed: {str(e)}'}, status=500)
    



# ORTHOPEDICS MODULE

from .models import OrthoCondition, OrthoImaging, OrthoSurgery, RehabilitationPlan


@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated])
def ortho_conditions(request):
    """Get or add orthopedic conditions"""
    user = request.user

    if request.method == 'GET':
        patient_id = request.query_params.get('patient_id')
        if patient_id and user.role in ['doctor', 'admin']:
            conditions = OrthoCondition.objects.filter(
                patient_id=patient_id
            ).select_related('doctor')
        else:
            conditions = OrthoCondition.objects.filter(
                patient=user
            ).select_related('doctor')

        status_filter = request.query_params.get('status')
        if status_filter:
            conditions = conditions.filter(status=status_filter)

        body_part = request.query_params.get('body_part')
        if body_part:
            conditions = conditions.filter(body_part=body_part)

        return Response({
            'count': conditions.count(),
            'conditions': [{
                'id': c.id,
                'condition': c.condition,
                'body_part': c.body_part,
                'status': c.status,
                'severity': c.severity,
                'diagnosed_date': str(c.diagnosed_date) if c.diagnosed_date else None,
                'injury_date': str(c.injury_date) if c.injury_date else None,
                'injury_cause': c.injury_cause,
                'doctor': c.doctor.full_name if c.doctor else None,
                'notes': c.notes,
                'created_at': c.created_at.isoformat(),
            } for c in conditions],
        })

    if user.role not in ['doctor', 'admin']:
        return Response({'error': 'Only doctors can add orthopedic conditions'}, status=403)

    patient_id = request.data.get('patient_id')
    if not patient_id or not request.data.get('condition') or not request.data.get('body_part'):
        return Response({'error': 'patient_id, condition and body_part are required'}, status=400)

    try:
        target_patient = User.objects.get(id=patient_id, role='patient')
    except User.DoesNotExist:
        return Response({'error': 'Patient not found'}, status=404)

    condition = OrthoCondition.objects.create(
        patient=target_patient,
        doctor=user,
        condition=request.data.get('condition'),
        body_part=request.data.get('body_part'),
        status=request.data.get('status', 'active'),
        severity=request.data.get('severity'),
        diagnosed_date=request.data.get('diagnosed_date'),
        injury_date=request.data.get('injury_date'),
        injury_cause=request.data.get('injury_cause', ''),
        notes=request.data.get('notes', ''),
    )

    create_notification(
        recipient=target_patient,
        sender=user,
        notification_type='general',
        title='Orthopedic Condition Recorded',
        message=f'Dr. {user.full_name} recorded: {condition.condition} ({condition.body_part}).',
        link='/orthopedics/',
    )

    return Response({
        'message': 'Orthopedic condition added successfully',
        'id': condition.id,
        'condition': condition.condition,
        'body_part': condition.body_part,
    }, status=201)


@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated])
def ortho_imaging(request):
    """Get or add orthopedic imaging records"""
    user = request.user

    if request.method == 'GET':
        patient_id = request.query_params.get('patient_id')
        if patient_id and user.role in ['doctor', 'admin']:
            imaging = OrthoImaging.objects.filter(
                patient_id=patient_id
            ).select_related('doctor')
        else:
            imaging = OrthoImaging.objects.filter(
                patient=user
            ).select_related('doctor')

        imaging_type = request.query_params.get('type')
        if imaging_type:
            imaging = imaging.filter(imaging_type=imaging_type)

        return Response({
            'count': imaging.count(),
            'imaging': [{
                'id': i.id,
                'imaging_type': i.imaging_type,
                'body_part': i.body_part,
                'imaging_date': str(i.imaging_date),
                'findings': i.findings,
                'impression': i.impression,
                'file_url': request.build_absolute_uri(i.file.url) if i.file else None,
                'doctor': i.doctor.full_name if i.doctor else None,
                'notes': i.notes,
            } for i in imaging],
        })

    if user.role not in ['doctor', 'admin']:
        return Response({'error': 'Only doctors can add imaging records'}, status=403)

    patient_id = request.data.get('patient_id')
    if not patient_id or not request.data.get('imaging_type') or not request.data.get('imaging_date'):
        return Response({'error': 'patient_id, imaging_type and imaging_date are required'}, status=400)

    try:
        target_patient = User.objects.get(id=patient_id, role='patient')
    except User.DoesNotExist:
        return Response({'error': 'Patient not found'}, status=404)

    condition_id = request.data.get('condition_id')
    condition = None
    if condition_id:
        try:
            condition = OrthoCondition.objects.get(id=condition_id, patient=target_patient)
        except OrthoCondition.DoesNotExist:
            pass

    imaging = OrthoImaging.objects.create(
        patient=target_patient,
        doctor=user,
        condition=condition,
        imaging_type=request.data.get('imaging_type'),
        body_part=request.data.get('body_part', ''),
        imaging_date=request.data.get('imaging_date'),
        findings=request.data.get('findings', ''),
        impression=request.data.get('impression', ''),
        notes=request.data.get('notes', ''),
    )

    if 'file' in request.FILES:
        imaging.file = request.FILES['file']
        imaging.save()

    return Response({
        'message': 'Imaging record added successfully',
        'id': imaging.id,
        'imaging_type': imaging.imaging_type,
        'body_part': imaging.body_part,
        'imaging_date': str(imaging.imaging_date),
    }, status=201)


@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated])
def ortho_surgeries(request):
    """Get or add orthopedic surgery records"""
    user = request.user

    if request.method == 'GET':
        patient_id = request.query_params.get('patient_id')
        if patient_id and user.role in ['doctor', 'admin']:
            surgeries = OrthoSurgery.objects.filter(
                patient_id=patient_id
            ).select_related('surgeon')
        else:
            surgeries = OrthoSurgery.objects.filter(
                patient=user
            ).select_related('surgeon')

        return Response({
            'count': surgeries.count(),
            'surgeries': [{
                'id': s.id,
                'surgery_type': s.surgery_type,
                'body_part': s.body_part,
                'surgery_date': str(s.surgery_date),
                'duration_minutes': s.duration_minutes,
                'outcome': s.outcome,
                'complications': s.complications,
                'implants_used': s.implants_used,
                'rehabilitation_required': s.rehabilitation_required,
                'rehabilitation_duration_weeks': s.rehabilitation_duration_weeks,
                'follow_up_date': str(s.follow_up_date) if s.follow_up_date else None,
                'surgeon': s.surgeon.full_name if s.surgeon else None,
                'notes': s.notes,
            } for s in surgeries],
        })

    if user.role not in ['doctor', 'admin']:
        return Response({'error': 'Only doctors can add surgery records'}, status=403)

    patient_id = request.data.get('patient_id')
    if not patient_id or not request.data.get('surgery_type') or not request.data.get('surgery_date'):
        return Response({'error': 'patient_id, surgery_type and surgery_date are required'}, status=400)

    try:
        target_patient = User.objects.get(id=patient_id, role='patient')
    except User.DoesNotExist:
        return Response({'error': 'Patient not found'}, status=404)

    condition_id = request.data.get('condition_id')
    condition = None
    if condition_id:
        try:
            condition = OrthoCondition.objects.get(id=condition_id, patient=target_patient)
        except OrthoCondition.DoesNotExist:
            pass

    surgery = OrthoSurgery.objects.create(
        patient=target_patient,
        surgeon=user,
        condition=condition,
        surgery_type=request.data.get('surgery_type'),
        body_part=request.data.get('body_part', ''),
        surgery_date=request.data.get('surgery_date'),
        duration_minutes=request.data.get('duration_minutes'),
        outcome=request.data.get('outcome', 'successful'),
        complications=request.data.get('complications', ''),
        implants_used=request.data.get('implants_used', ''),
        rehabilitation_required=request.data.get('rehabilitation_required', True),
        rehabilitation_duration_weeks=request.data.get('rehabilitation_duration_weeks'),
        follow_up_date=request.data.get('follow_up_date'),
        notes=request.data.get('notes', ''),
    )

    create_notification(
        recipient=target_patient,
        sender=user,
        notification_type='general',
        title='Surgery Record Added',
        message=f'Dr. {user.full_name} added surgery record: {surgery.surgery_type} on {surgery.surgery_date}.',
        link='/orthopedics/surgeries/',
    )

    return Response({
        'message': 'Surgery record added successfully',
        'id': surgery.id,
        'surgery_type': surgery.surgery_type,
        'surgery_date': str(surgery.surgery_date),
        'outcome': surgery.outcome,
    }, status=201)


@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated])
def rehab_plans(request):
    """Get or add rehabilitation plans"""
    user = request.user

    if request.method == 'GET':
        patient_id = request.query_params.get('patient_id')
        if patient_id and user.role in ['doctor', 'admin']:
            plans = RehabilitationPlan.objects.filter(
                patient_id=patient_id
            ).select_related('doctor')
        else:
            plans = RehabilitationPlan.objects.filter(
                patient=user
            ).select_related('doctor')

        status_filter = request.query_params.get('status')
        if status_filter:
            plans = plans.filter(status=status_filter)

        return Response({
            'count': plans.count(),
            'plans': [{
                'id': p.id,
                'title': p.title,
                'status': p.status,
                'start_date': str(p.start_date),
                'end_date': str(p.end_date) if p.end_date else None,
                'frequency_per_week': p.frequency_per_week,
                'exercises': p.exercises,
                'goals': p.goals,
                'progress_notes': p.progress_notes,
                'pain_level_start': p.pain_level_start,
                'pain_level_current': p.pain_level_current,
                'doctor': p.doctor.full_name if p.doctor else None,
                'notes': p.notes,
                'updated_at': p.updated_at.isoformat(),
            } for p in plans],
        })

    if user.role not in ['doctor', 'admin']:
        return Response({'error': 'Only doctors can create rehabilitation plans'}, status=403)

    patient_id = request.data.get('patient_id')
    if not patient_id or not request.data.get('title') or not request.data.get('start_date'):
        return Response({'error': 'patient_id, title and start_date are required'}, status=400)

    try:
        target_patient = User.objects.get(id=patient_id, role='patient')
    except User.DoesNotExist:
        return Response({'error': 'Patient not found'}, status=404)

    condition_id = request.data.get('condition_id')
    condition = None
    if condition_id:
        try:
            condition = OrthoCondition.objects.get(id=condition_id, patient=target_patient)
        except OrthoCondition.DoesNotExist:
            pass

    surgery_id = request.data.get('surgery_id')
    surgery = None
    if surgery_id:
        try:
            surgery = OrthoSurgery.objects.get(id=surgery_id, patient=target_patient)
        except OrthoSurgery.DoesNotExist:
            pass

    plan = RehabilitationPlan.objects.create(
        patient=target_patient,
        doctor=user,
        condition=condition,
        surgery=surgery,
        title=request.data.get('title'),
        start_date=request.data.get('start_date'),
        end_date=request.data.get('end_date'),
        status='active',
        frequency_per_week=request.data.get('frequency_per_week', 3),
        exercises=request.data.get('exercises', []),
        goals=request.data.get('goals', ''),
        pain_level_start=request.data.get('pain_level_start'),
        pain_level_current=request.data.get('pain_level_current'),
        notes=request.data.get('notes', ''),
    )

    create_notification(
        recipient=target_patient,
        sender=user,
        notification_type='general',
        title='Rehabilitation Plan Created',
        message=f'Dr. {user.full_name} created a rehabilitation plan: {plan.title}.',
        link='/orthopedics/rehab/',
    )

    return Response({
        'message': 'Rehabilitation plan created successfully',
        'id': plan.id,
        'title': plan.title,
        'start_date': str(plan.start_date),
    }, status=201)


@api_view(['PATCH'])
@permission_classes([IsAuthenticated])
def update_rehab_plan(request, plan_id):
    """Update rehabilitation plan progress"""
    try:
        plan = RehabilitationPlan.objects.get(id=plan_id)
    except RehabilitationPlan.DoesNotExist:
        return Response({'error': 'Plan not found'}, status=404)

    if plan.patient != request.user and request.user.role not in ['doctor', 'admin']:
        return Response({'error': 'Permission denied'}, status=403)

    updatable = [
        'status', 'progress_notes', 'pain_level_current',
        'exercises', 'end_date', 'notes', 'frequency_per_week'
    ]
    for field in updatable:
        if field in request.data:
            setattr(plan, field, request.data[field])
    plan.save()

    return Response({'message': 'Rehabilitation plan updated successfully'})


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def orthopedics_summary(request, patient_id=None):
    """AI-powered orthopedics summary"""
    user = request.user

    if user.role == 'patient':
        target_patient = user
    elif user.role in ['doctor', 'admin']:
        if not patient_id:
            return Response({'error': 'patient_id is required'}, status=400)
        try:
            target_patient = User.objects.get(id=patient_id, role='patient')
        except User.DoesNotExist:
            return Response({'error': 'Patient not found'}, status=404)
    else:
        return Response({'error': 'Permission denied'}, status=403)

    conditions = OrthoCondition.objects.filter(patient=target_patient)
    surgeries = OrthoSurgery.objects.filter(patient=target_patient)
    imaging = OrthoImaging.objects.filter(patient=target_patient)
    rehab = RehabilitationPlan.objects.filter(patient=target_patient)

    if not conditions.exists() and not surgeries.exists():
        return Response({
            'patient_name': target_patient.full_name,
            'summary': 'Нет ортопедических данных.',
            'condition_count': 0,
            'surgery_count': 0,
        })

    conditions_text = "\n".join([
        f"- {c.condition} ({c.body_part}, {c.status})"
        f"{', severity: ' + str(c.severity) + '/10' if c.severity else ''}"
        for c in conditions
    ])

    surgeries_text = "\n".join([
        f"- {s.surgery_type} on {s.body_part} ({s.surgery_date}, outcome: {s.outcome})"
        for s in surgeries
    ])

    active_rehab = rehab.filter(status='active').first()
    rehab_text = ""
    if active_rehab:
        rehab_text = (
            f"Активная реабилитация: {active_rehab.title}\n"
            f"Частота: {active_rehab.frequency_per_week}x в неделю\n"
            f"Боль: {active_rehab.pain_level_current}/10"
        )

    prompt = f"""Ты ортопед-ассистент. Проанализируй ортопедическую историю пациента.

Пациент: {target_patient.full_name}

Диагнозы:
{conditions_text if conditions_text else 'Нет'}

Операции:
{surgeries_text if surgeries_text else 'Нет'}

Визуализация: {imaging.count()} записей (МРТ/рентген/КТ)

{rehab_text}

Дай краткое профессиональное резюме на русском:
1. **Общее состояние опорно-двигательного аппарата**
2. **Основные проблемы и травмы**
3. **История операций**
4. **Реабилитация**
5. **Рекомендации**
6. **Тревожные симптомы** (если есть 🔴)"""

    try:
        import anthropic
        from django.conf import settings as django_settings
        claude_client = anthropic.Anthropic(api_key=django_settings.ANTHROPIC_API_KEY)
        response = claude_client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=800,
            messages=[{'role': 'user', 'content': prompt}],
        )

        return Response({
            'patient_name': target_patient.full_name,
            'generated_at': timezone.now().isoformat(),
            'condition_count': conditions.count(),
            'surgery_count': surgeries.count(),
            'imaging_count': imaging.count(),
            'rehab_count': rehab.count(),
            'summary': response.content[0].text,
        })

    except Exception as e:
        return Response({'error': f'Summary failed: {str(e)}'}, status=500)
    
# PEDIATRICS MODULE

from .models import ChildProfile, GrowthRecord, VaccinationRecord, PediatricVisit


@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated])
def child_profiles(request):
    """Get or create child profiles"""
    user = request.user

    if request.method == 'GET':
        if user.role == 'patient':
            children = ChildProfile.objects.filter(parent=user)
        elif user.role in ['doctor', 'admin']:
            parent_id = request.query_params.get('parent_id')
            if parent_id:
                children = ChildProfile.objects.filter(parent_id=parent_id)
            else:
                children = ChildProfile.objects.all().select_related('parent')
        else:
            children = ChildProfile.objects.none()

        return Response({
            'count': children.count(),
            'children': [{
                'id': c.id,
                'full_name': c.full_name,
                'date_of_birth': str(c.date_of_birth),
                'age_months': c.age_months,
                'age_years': c.age_years,
                'gender': c.gender,
                'blood_type': c.blood_type,
                'birth_weight_kg': c.birth_weight_kg,
                'birth_height_cm': c.birth_height_cm,
                'allergies': c.allergies,
                'chronic_conditions': c.chronic_conditions,
                'notes': c.notes,
            } for c in children],
        })

    # POST — patients (parents) create child profiles
    required = ['full_name', 'date_of_birth', 'gender']
    for field in required:
        if not request.data.get(field):
            return Response({'error': f'{field} is required'}, status=400)

    parent = user
    if user.role in ['doctor', 'admin']:
        parent_id = request.data.get('parent_id')
        if not parent_id:
            return Response({'error': 'parent_id is required for doctors'}, status=400)
        try:
            parent = User.objects.get(id=parent_id, role='patient')
        except User.DoesNotExist:
            return Response({'error': 'Parent patient not found'}, status=404)

    child = ChildProfile.objects.create(
        parent=parent,
        full_name=request.data.get('full_name'),
        date_of_birth=request.data.get('date_of_birth'),
        gender=request.data.get('gender'),
        blood_type=request.data.get('blood_type', 'unknown'),
        birth_weight_kg=request.data.get('birth_weight_kg'),
        birth_height_cm=request.data.get('birth_height_cm'),
        allergies=request.data.get('allergies', ''),
        chronic_conditions=request.data.get('chronic_conditions', ''),
        notes=request.data.get('notes', ''),
    )

    return Response({
        'message': 'Child profile created successfully',
        'id': child.id,
        'full_name': child.full_name,
        'age_months': child.age_months,
    }, status=201)


@api_view(['GET', 'PUT', 'DELETE'])
@permission_classes([IsAuthenticated])
def child_profile_detail(request, child_id):
    """Get, update or delete a child profile"""
    try:
        child = ChildProfile.objects.get(id=child_id)
    except ChildProfile.DoesNotExist:
        return Response({'error': 'Child not found'}, status=404)

    if child.parent != request.user and request.user.role not in ['doctor', 'admin']:
        return Response({'error': 'Permission denied'}, status=403)

    if request.method == 'GET':
        return Response({
            'id': child.id,
            'full_name': child.full_name,
            'date_of_birth': str(child.date_of_birth),
            'age_months': child.age_months,
            'age_years': child.age_years,
            'gender': child.gender,
            'blood_type': child.blood_type,
            'birth_weight_kg': child.birth_weight_kg,
            'birth_height_cm': child.birth_height_cm,
            'allergies': child.allergies,
            'chronic_conditions': child.chronic_conditions,
            'notes': child.notes,
            'parent': child.parent.full_name,
        })

    if request.method == 'PUT':
        updatable = [
            'full_name', 'blood_type', 'allergies',
            'chronic_conditions', 'notes',
            'birth_weight_kg', 'birth_height_cm',
        ]
        for field in updatable:
            if field in request.data:
                setattr(child, field, request.data[field])
        child.save()
        return Response({'message': 'Child profile updated successfully'})

    if request.method == 'DELETE':
        if request.user.role not in ['admin']:
            return Response({'error': 'Only admins can delete child profiles'}, status=403)
        child.delete()
        return Response({'message': 'Child profile deleted'})


@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated])
def growth_records(request, child_id):
    """Get or add growth records for a child"""
    try:
        child = ChildProfile.objects.get(id=child_id)
    except ChildProfile.DoesNotExist:
        return Response({'error': 'Child not found'}, status=404)

    if child.parent != request.user and request.user.role not in ['doctor', 'admin']:
        return Response({'error': 'Permission denied'}, status=403)

    if request.method == 'GET':
        records = GrowthRecord.objects.filter(child=child)
        return Response({
            'child': child.full_name,
            'count': records.count(),
            'records': [{
                'id': r.id,
                'recorded_date': str(r.recorded_date),
                'age_months': r.age_months,
                'weight_kg': r.weight_kg,
                'height_cm': r.height_cm,
                'head_circumference_cm': r.head_circumference_cm,
                'bmi': r.bmi,
                'notes': r.notes,
            } for r in records],
        })

    if not request.data.get('recorded_date'):
        return Response({'error': 'recorded_date is required'}, status=400)

    record = GrowthRecord.objects.create(
        child=child,
        recorded_by=request.user,
        recorded_date=request.data.get('recorded_date'),
        age_months=request.data.get('age_months', child.age_months),
        weight_kg=request.data.get('weight_kg'),
        height_cm=request.data.get('height_cm'),
        head_circumference_cm=request.data.get('head_circumference_cm'),
        notes=request.data.get('notes', ''),
    )

    return Response({
        'message': 'Growth record added successfully',
        'id': record.id,
        'bmi': record.bmi,
        'age_months': record.age_months,
    }, status=201)


@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated])
def vaccination_records(request, child_id):
    """Get or add vaccination records"""
    try:
        child = ChildProfile.objects.get(id=child_id)
    except ChildProfile.DoesNotExist:
        return Response({'error': 'Child not found'}, status=404)

    if child.parent != request.user and request.user.role not in ['doctor', 'admin']:
        return Response({'error': 'Permission denied'}, status=403)

    if request.method == 'GET':
        vaccinations = VaccinationRecord.objects.filter(
            child=child
        ).select_related('administered_by')

        completed = vaccinations.filter(status='completed').count()
        scheduled = vaccinations.filter(status='scheduled').count()
        overdue = vaccinations.filter(status='overdue').count()

        return Response({
            'child': child.full_name,
            'stats': {
                'completed': completed,
                'scheduled': scheduled,
                'overdue': overdue,
                'total': vaccinations.count(),
            },
            'vaccinations': [{
                'id': v.id,
                'vaccine': v.vaccine,
                'dose_number': v.dose_number,
                'status': v.status,
                'administered_date': str(v.administered_date) if v.administered_date else None,
                'next_dose_date': str(v.next_dose_date) if v.next_dose_date else None,
                'batch_number': v.batch_number,
                'manufacturer': v.manufacturer,
                'site': v.site,
                'reactions': v.reactions,
                'administered_by': v.administered_by.full_name if v.administered_by else None,
                'notes': v.notes,
            } for v in vaccinations],
        })

    if user.role not in ['doctor', 'admin']:
        return Response({'error': 'Only doctors can add vaccination records'}, status=403)

    if not request.data.get('vaccine'):
        return Response({'error': 'vaccine is required'}, status=400)

    vaccination = VaccinationRecord.objects.create(
        child=child,
        administered_by=request.user,
        vaccine=request.data.get('vaccine'),
        dose_number=request.data.get('dose_number', 1),
        status=request.data.get('status', 'completed'),
        administered_date=request.data.get('administered_date'),
        next_dose_date=request.data.get('next_dose_date'),
        batch_number=request.data.get('batch_number', ''),
        manufacturer=request.data.get('manufacturer', ''),
        site=request.data.get('site', ''),
        reactions=request.data.get('reactions', ''),
        notes=request.data.get('notes', ''),
    )

    if vaccination.next_dose_date:
        create_notification(
            recipient=child.parent,
            sender=request.user,
            notification_type='general',
            title='Next Vaccination Reminder',
            message=f'{child.full_name} needs {vaccination.vaccine} dose {vaccination.dose_number + 1} on {vaccination.next_dose_date}.',
            link='/pediatrics/',
        )

    return Response({
        'message': 'Vaccination record added successfully',
        'id': vaccination.id,
        'vaccine': vaccination.vaccine,
        'status': vaccination.status,
    }, status=201)


@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated])
def pediatric_visits(request, child_id):
    """Get or add pediatric visits"""
    try:
        child = ChildProfile.objects.get(id=child_id)
    except ChildProfile.DoesNotExist:
        return Response({'error': 'Child not found'}, status=404)

    if child.parent != request.user and request.user.role not in ['doctor', 'admin']:
        return Response({'error': 'Permission denied'}, status=403)

    if request.method == 'GET':
        visits = PediatricVisit.objects.filter(
            child=child
        ).select_related('doctor')

        return Response({
            'child': child.full_name,
            'count': visits.count(),
            'visits': [{
                'id': v.id,
                'visit_date': str(v.visit_date),
                'visit_type': v.visit_type,
                'doctor': v.doctor.full_name if v.doctor else None,
                'chief_complaint': v.chief_complaint,
                'diagnosis': v.diagnosis,
                'weight_kg': v.weight_kg,
                'height_cm': v.height_cm,
                'temperature_c': v.temperature_c,
                'heart_rate': v.heart_rate,
                'developmental_notes': v.developmental_notes,
                'treatment_plan': v.treatment_plan,
                'medications_prescribed': v.medications_prescribed,
                'next_visit': str(v.next_visit) if v.next_visit else None,
                'notes': v.notes,
            } for v in visits],
        })

    if request.user.role not in ['doctor', 'admin']:
        return Response({'error': 'Only doctors can add pediatric visits'}, status=403)

    if not request.data.get('visit_date'):
        return Response({'error': 'visit_date is required'}, status=400)

    visit = PediatricVisit.objects.create(
        child=child,
        doctor=request.user,
        visit_date=request.data.get('visit_date'),
        visit_type=request.data.get('visit_type', 'well_child'),
        chief_complaint=request.data.get('chief_complaint', ''),
        diagnosis=request.data.get('diagnosis', ''),
        weight_kg=request.data.get('weight_kg'),
        height_cm=request.data.get('height_cm'),
        temperature_c=request.data.get('temperature_c'),
        heart_rate=request.data.get('heart_rate'),
        developmental_notes=request.data.get('developmental_notes', ''),
        treatment_plan=request.data.get('treatment_plan', ''),
        medications_prescribed=request.data.get('medications_prescribed', []),
        next_visit=request.data.get('next_visit'),
        notes=request.data.get('notes', ''),
    )

    create_notification(
        recipient=child.parent,
        sender=request.user,
        notification_type='general',
        title='Pediatric Visit Added',
        message=f'Dr. {request.user.full_name} added a visit record for {child.full_name} on {visit.visit_date}.',
        link='/pediatrics/',
    )

    return Response({
        'message': 'Pediatric visit added successfully',
        'id': visit.id,
        'visit_type': visit.visit_type,
        'visit_date': str(visit.visit_date),
    }, status=201)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def pediatrics_summary(request, child_id):
    """AI-powered pediatrics summary for a child"""
    try:
        child = ChildProfile.objects.get(id=child_id)
    except ChildProfile.DoesNotExist:
        return Response({'error': 'Child not found'}, status=404)

    if child.parent != request.user and request.user.role not in ['doctor', 'admin']:
        return Response({'error': 'Permission denied'}, status=403)

    growth = GrowthRecord.objects.filter(child=child)
    vaccinations = VaccinationRecord.objects.filter(child=child)
    visits = PediatricVisit.objects.filter(child=child)

    latest_growth = growth.first()
    growth_text = ""
    if latest_growth:
        growth_text = (
            f"Последние показатели роста ({latest_growth.recorded_date}):\n"
            f"Вес: {latest_growth.weight_kg} кг, Рост: {latest_growth.height_cm} см, "
            f"BMI: {latest_growth.bmi}, Возраст: {latest_growth.age_months} мес."
        )

    completed_vaccines = vaccinations.filter(status='completed').count()
    overdue_vaccines = vaccinations.filter(status='overdue').count()

    prompt = f"""Ты педиатр-ассистент. Проанализируй историю здоровья ребёнка.

Ребёнок: {child.full_name}
Возраст: {child.age_years} лет ({child.age_months} месяцев)
Пол: {child.gender}
Группа крови: {child.blood_type}
Аллергии: {child.allergies or 'Нет'}
Хронические заболевания: {child.chronic_conditions or 'Нет'}

{growth_text}

Прививки: {completed_vaccines} выполнено, {overdue_vaccines} просрочено
Визиты к врачу: {visits.count()}

Дай краткое профессиональное резюме на русском:
1. **Общее состояние здоровья**
2. **Физическое развитие**
3. **Вакцинация** (есть ли просроченные?)
4. **Рекомендации педиатра**
5. **На что обратить внимание** 🔴"""

    try:
        import anthropic
        from django.conf import settings as django_settings
        claude_client = anthropic.Anthropic(api_key=django_settings.ANTHROPIC_API_KEY)
        response = claude_client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=800,
            messages=[{'role': 'user', 'content': prompt}],
        )

        return Response({
            'child_name': child.full_name,
            'age_months': child.age_months,
            'generated_at': timezone.now().isoformat(),
            'growth_records': growth.count(),
            'vaccinations_completed': completed_vaccines,
            'vaccinations_overdue': overdue_vaccines,
            'visit_count': visits.count(),
            'summary': response.content[0].text,
        })

    except Exception as e:
        return Response({'error': f'Summary failed: {str(e)}'}, status=500)
    
# LAB RESULTS MODULE

from .models import LabOrder, LabTest, LabReport


@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated])
def lab_orders(request):
    """Get or create lab orders"""
    user = request.user

    if request.method == 'GET':
        patient_id = request.query_params.get('patient_id')
        if patient_id and user.role in ['doctor', 'admin']:
            orders = LabOrder.objects.filter(
                patient_id=patient_id
            ).select_related('doctor').prefetch_related('tests')
        elif user.role == 'patient':
            orders = LabOrder.objects.filter(
                patient=user
            ).select_related('doctor').prefetch_related('tests')
        elif user.role == 'doctor':
            orders = LabOrder.objects.filter(
                doctor=user
            ).select_related('patient').prefetch_related('tests')
        else:
            orders = LabOrder.objects.all().select_related('doctor', 'patient')

        status_filter = request.query_params.get('status')
        if status_filter:
            orders = orders.filter(status=status_filter)

        return Response({
            'count': orders.count(),
            'orders': [{
                'id': o.id,
                'order_date': str(o.order_date),
                'status': o.status,
                'priority': o.priority,
                'patient': o.patient.full_name,
                'doctor': o.doctor.full_name if o.doctor else None,
                'clinical_notes': o.clinical_notes,
                'tests_count': o.tests.count(),
                'abnormal_count': o.tests.filter(is_abnormal=True).count(),
                'created_at': o.created_at.isoformat(),
            } for o in orders],
        })

    # POST — doctors only
    if user.role not in ['doctor', 'admin']:
        return Response({'error': 'Only doctors can create lab orders'}, status=403)

    patient_id = request.data.get('patient_id')
    if not patient_id or not request.data.get('order_date'):
        return Response({'error': 'patient_id and order_date are required'}, status=400)

    try:
        target_patient = User.objects.get(id=patient_id, role='patient')
    except User.DoesNotExist:
        return Response({'error': 'Patient not found'}, status=404)

    order = LabOrder.objects.create(
        patient=target_patient,
        doctor=user,
        order_date=request.data.get('order_date'),
        status='ordered',
        priority=request.data.get('priority', 'routine'),
        clinical_notes=request.data.get('clinical_notes', ''),
        diagnosis_code=request.data.get('diagnosis_code', ''),
    )

    # Create individual tests if provided
    tests_data = request.data.get('tests', [])
    for test in tests_data:
        LabTest.objects.create(
            order=order,
            test_name=test.get('test_name', ''),
            category=test.get('category', 'other'),
            status='pending',
        )

    create_notification(
        recipient=target_patient,
        sender=user,
        notification_type='general',
        title='Lab Tests Ordered',
        message=f'Dr. {user.full_name} ordered {len(tests_data)} lab test(s) for you.',
        link='/lab/',
    )

    return Response({
        'message': 'Lab order created successfully',
        'id': order.id,
        'order_date': str(order.order_date),
        'tests_created': len(tests_data),
    }, status=201)


@api_view(['GET', 'PATCH'])
@permission_classes([IsAuthenticated])
def lab_order_detail(request, order_id):
    """Get or update a specific lab order"""
    try:
        order = LabOrder.objects.get(id=order_id)
    except LabOrder.DoesNotExist:
        return Response({'error': 'Lab order not found'}, status=404)

    user = request.user
    if order.patient != user and user.role not in ['doctor', 'admin']:
        return Response({'error': 'Permission denied'}, status=403)

    if request.method == 'GET':
        tests = order.tests.all()
        report = None
        try:
            r = order.report
            report = {
                'id': r.id,
                'report_date': r.report_date.isoformat(),
                'summary': r.summary,
                'ai_interpretation': r.ai_interpretation,
                'is_reviewed_by_doctor': r.is_reviewed_by_doctor,
                'report_file': request.build_absolute_uri(r.report_file.url) if r.report_file else None,
            }
        except LabReport.DoesNotExist:
            pass

        return Response({
            'id': order.id,
            'order_date': str(order.order_date),
            'status': order.status,
            'priority': order.priority,
            'patient': order.patient.full_name,
            'doctor': order.doctor.full_name if order.doctor else None,
            'clinical_notes': order.clinical_notes,
            'tests': [{
                'id': t.id,
                'test_name': t.test_name,
                'category': t.category,
                'status': t.status,
                'result_value': t.result_value,
                'result_unit': t.result_unit,
                'reference_range_min': t.reference_range_min,
                'reference_range_max': t.reference_range_max,
                'reference_range_text': t.reference_range_text,
                'is_abnormal': t.is_abnormal,
                'abnormal_flag': t.abnormal_flag,
                'result_date': t.result_date.isoformat() if t.result_date else None,
                'notes': t.notes,
            } for t in tests],
            'report': report,
        })

    # PATCH — update order status
    if user.role not in ['doctor', 'admin']:
        return Response({'error': 'Permission denied'}, status=403)

    if 'status' in request.data:
        order.status = request.data['status']
    if 'clinical_notes' in request.data:
        order.clinical_notes = request.data['clinical_notes']
    order.save()

    return Response({'message': 'Lab order updated successfully'})


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def submit_lab_results(request, order_id):
    """Submit results for lab tests in an order"""
    if request.user.role not in ['doctor', 'admin']:
        return Response({'error': 'Permission denied'}, status=403)

    try:
        order = LabOrder.objects.get(id=order_id)
    except LabOrder.DoesNotExist:
        return Response({'error': 'Lab order not found'}, status=404)

    results = request.data.get('results', [])
    if not results:
        return Response({'error': 'results array is required'}, status=400)

    updated_tests = []
    abnormal_tests = []

    for result in results:
        test_id = result.get('test_id')
        try:
            test = LabTest.objects.get(id=test_id, order=order)
        except LabTest.DoesNotExist:
            continue

        test.result_value = result.get('result_value', '')
        test.result_unit = result.get('result_unit', '')
        test.reference_range_min = result.get('reference_range_min')
        test.reference_range_max = result.get('reference_range_max')
        test.reference_range_text = result.get('reference_range_text', '')
        test.is_abnormal = result.get('is_abnormal', False)
        test.abnormal_flag = result.get('abnormal_flag', '')
        test.result_date = timezone.now()
        test.notes = result.get('notes', '')
        test.status = 'completed'
        test.save()

        updated_tests.append(test.test_name)
        if test.is_abnormal:
            abnormal_tests.append(f"{test.test_name} ({test.abnormal_flag})")

    # Update order status
    order.status = 'completed'
    order.save()

    # Notify patient
    msg = f'Your lab results are ready. {len(updated_tests)} test(s) completed.'
    if abnormal_tests:
        msg += f' ⚠️ {len(abnormal_tests)} abnormal result(s) found.'

    create_notification(
        recipient=order.patient,
        sender=request.user,
        notification_type='general',
        title='Lab Results Ready',
        message=msg,
        link=f'/lab/orders/{order.id}/',
    )

    return Response({
        'message': 'Lab results submitted successfully',
        'updated_tests': len(updated_tests),
        'abnormal_tests': abnormal_tests,
    })


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def generate_lab_ai_interpretation(request, order_id):
    """Generate AI interpretation of lab results"""
    try:
        order = LabOrder.objects.get(id=order_id)
    except LabOrder.DoesNotExist:
        return Response({'error': 'Lab order not found'}, status=404)

    if order.patient != request.user and request.user.role not in ['doctor', 'admin']:
        return Response({'error': 'Permission denied'}, status=403)

    tests = order.tests.filter(status='completed')
    if not tests.exists():
        return Response({'error': 'No completed tests to interpret'}, status=400)

    # Build test results text
    results_text = ""
    for t in tests:
        flag = f" [{t.abnormal_flag}]" if t.abnormal_flag else ""
        ref = f" (ref: {t.reference_range_text or f'{t.reference_range_min}-{t.reference_range_max}'})" if (t.reference_range_text or t.reference_range_min) else ""
        results_text += f"- {t.test_name}: {t.result_value} {t.result_unit}{ref}{flag}\n"

    prompt = f"""Ты лаборант-ассистент. Интерпретируй результаты анализов пациента.

Пациент: {order.patient.full_name}
Дата заказа: {order.order_date}
Клинические заметки: {order.clinical_notes or 'Нет'}

Результаты анализов:
{results_text}

Дай краткую клиническую интерпретацию на русском:
1. **Нормальные показатели**
2. **Отклонения от нормы** (если есть)
3. **Клиническое значение**
4. **Рекомендации**
5. **Требует срочного внимания** 🔴 (если есть критические значения)

Важно: не ставь диагноз, только интерпретируй лабораторные данные."""

    try:
        import anthropic
        from django.conf import settings as django_settings
        claude_client = anthropic.Anthropic(api_key=django_settings.ANTHROPIC_API_KEY)
        response = claude_client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=800,
            messages=[{'role': 'user', 'content': prompt}],
        )
        interpretation = response.content[0].text

        # Save to report
        report, created = LabReport.objects.get_or_create(
            order=order,
            defaults={
                'reported_by': request.user,
                'report_date': timezone.now(),
                'ai_interpretation': interpretation,
            }
        )
        if not created:
            report.ai_interpretation = interpretation
            report.save()

        return Response({
            'order_id': order.id,
            'patient': order.patient.full_name,
            'tests_interpreted': tests.count(),
            'abnormal_count': tests.filter(is_abnormal=True).count(),
            'interpretation': interpretation,
        })

    except Exception as e:
        return Response({'error': f'AI interpretation failed: {str(e)}'}, status=500)
    
# DOCTOR SCHEDULE MANAGEMENT

from .models import DoctorLeave, DoctorWorkingHours, ScheduleBlockout


@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated])
def doctor_leaves(request):
    """Get or request doctor leaves"""
    user = request.user

    if request.method == 'GET':
        doctor_id = request.query_params.get('doctor_id')
        if doctor_id and user.role == 'admin':
            leaves = DoctorLeave.objects.filter(
                doctor_id=doctor_id
            ).select_related('doctor', 'approved_by')
        elif user.role == 'doctor':
            leaves = DoctorLeave.objects.filter(
                doctor=user
            ).select_related('approved_by')
        elif user.role == 'admin':
            leaves = DoctorLeave.objects.all().select_related('doctor', 'approved_by')
        else:
            # Patients can see approved leaves for a specific doctor
            doctor_id = request.query_params.get('doctor_id')
            if not doctor_id:
                return Response({'error': 'doctor_id is required'}, status=400)
            leaves = DoctorLeave.objects.filter(
                doctor_id=doctor_id, status='approved'
            )

        status_filter = request.query_params.get('status')
        if status_filter:
            leaves = leaves.filter(status=status_filter)

        return Response({
            'count': leaves.count(),
            'leaves': [{
                'id': l.id,
                'doctor': l.doctor.full_name,
                'leave_type': l.leave_type,
                'start_date': str(l.start_date),
                'end_date': str(l.end_date),
                'duration_days': l.duration_days,
                'reason': l.reason,
                'status': l.status,
                'admin_notes': l.admin_notes,
                'approved_by': l.approved_by.full_name if l.approved_by else None,
                'created_at': l.created_at.isoformat(),
            } for l in leaves],
        })

    # POST — doctors request leave
    if user.role not in ['doctor', 'admin']:
        return Response({'error': 'Only doctors can request leave'}, status=403)

    required = ['leave_type', 'start_date', 'end_date']
    for field in required:
        if not request.data.get(field):
            return Response({'error': f'{field} is required'}, status=400)

    start = request.data.get('start_date')
    end = request.data.get('end_date')
    if start > end:
        return Response({'error': 'end_date must be after start_date'}, status=400)

    # Check for overlapping leaves
    overlapping = DoctorLeave.objects.filter(
        doctor=user,
        status__in=['pending', 'approved'],
        start_date__lte=end,
        end_date__gte=start,
    )
    if overlapping.exists():
        return Response({'error': 'You already have a leave request for this period'}, status=400)

    leave = DoctorLeave.objects.create(
        doctor=user,
        leave_type=request.data.get('leave_type'),
        start_date=start,
        end_date=end,
        reason=request.data.get('reason', ''),
        status='pending',
    )

    # Notify admins
    admins = User.objects.filter(role='admin')
    for admin in admins:
        create_notification(
            recipient=admin,
            sender=user,
            notification_type='general',
            title='Leave Request Submitted',
            message=f'Dr. {user.full_name} requested {leave.leave_type} from {leave.start_date} to {leave.end_date}.',
            link='/admin/leaves/',
        )

    return Response({
        'message': 'Leave request submitted successfully',
        'id': leave.id,
        'status': leave.status,
        'duration_days': leave.duration_days,
    }, status=201)


@api_view(['PATCH'])
@permission_classes([IsAuthenticated])
def manage_doctor_leave(request, leave_id):
    """Admin approves or rejects a leave request"""
    if request.user.role != 'admin':
        return Response({'error': 'Only admins can manage leave requests'}, status=403)

    try:
        leave = DoctorLeave.objects.get(id=leave_id)
    except DoctorLeave.DoesNotExist:
        return Response({'error': 'Leave request not found'}, status=404)

    new_status = request.data.get('status')
    if new_status not in ['approved', 'rejected', 'cancelled']:
        return Response({'error': 'status must be approved, rejected or cancelled'}, status=400)

    leave.status = new_status
    leave.approved_by = request.user
    leave.admin_notes = request.data.get('admin_notes', '')
    leave.save()

    # Notify doctor
    action = 'approved' if new_status == 'approved' else 'rejected'
    create_notification(
        recipient=leave.doctor,
        sender=request.user,
        notification_type='general',
        title=f'Leave Request {action.capitalize()}',
        message=f'Your {leave.leave_type} request from {leave.start_date} to {leave.end_date} has been {action}.',
        link='/doctor/leaves/',
    )

    return Response({
        'message': f'Leave request {action} successfully',
        'id': leave.id,
        'status': leave.status,
    })


@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated])
def doctor_working_hours(request):
    """Get or set custom working hours for a specific date"""
    user = request.user

    if request.method == 'GET':
        doctor_id = request.query_params.get('doctor_id', user.id)
        date_from = request.query_params.get('date_from')
        date_to = request.query_params.get('date_to')

        hours = DoctorWorkingHours.objects.filter(doctor_id=doctor_id)
        if date_from:
            hours = hours.filter(date__gte=date_from)
        if date_to:
            hours = hours.filter(date__lte=date_to)

        return Response({
            'count': hours.count(),
            'working_hours': [{
                'id': h.id,
                'date': str(h.date),
                'is_working': h.is_working,
                'start_time': str(h.start_time) if h.start_time else None,
                'end_time': str(h.end_time) if h.end_time else None,
                'slot_duration': h.slot_duration,
                'break_start': str(h.break_start) if h.break_start else None,
                'break_end': str(h.break_end) if h.break_end else None,
                'notes': h.notes,
            } for h in hours],
        })

    if user.role not in ['doctor', 'admin']:
        return Response({'error': 'Only doctors can set working hours'}, status=403)

    doctor = user
    if user.role == 'admin' and request.data.get('doctor_id'):
        try:
            doctor = User.objects.get(id=request.data.get('doctor_id'), role='doctor')
        except User.DoesNotExist:
            return Response({'error': 'Doctor not found'}, status=404)

    if not request.data.get('date'):
        return Response({'error': 'date is required'}, status=400)

    hours, created = DoctorWorkingHours.objects.update_or_create(
        doctor=doctor,
        date=request.data.get('date'),
        defaults={
            'is_working': request.data.get('is_working', True),
            'start_time': request.data.get('start_time'),
            'end_time': request.data.get('end_time'),
            'slot_duration': request.data.get('slot_duration', 30),
            'break_start': request.data.get('break_start'),
            'break_end': request.data.get('break_end'),
            'notes': request.data.get('notes', ''),
        }
    )

    return Response({
        'message': f'Working hours {"created" if created else "updated"} successfully',
        'id': hours.id,
        'date': str(hours.date),
        'is_working': hours.is_working,
    }, status=201 if created else 200)


@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated])
def schedule_blockouts(request):
    """Get or create schedule blockouts"""
    user = request.user

    if request.method == 'GET':
        doctor_id = request.query_params.get('doctor_id', user.id if user.role == 'doctor' else None)
        if not doctor_id:
            return Response({'error': 'doctor_id is required'}, status=400)

        blockouts = ScheduleBlockout.objects.filter(doctor_id=doctor_id)

        date_filter = request.query_params.get('date')
        if date_filter:
            blockouts = blockouts.filter(date=date_filter)

        return Response({
            'count': blockouts.count(),
            'blockouts': [{
                'id': b.id,
                'date': str(b.date),
                'start_time': str(b.start_time),
                'end_time': str(b.end_time),
                'reason': b.reason,
                'notes': b.notes,
                'is_recurring': b.is_recurring,
                'recurrence_days': b.recurrence_days,
            } for b in blockouts],
        })

    if user.role not in ['doctor', 'admin']:
        return Response({'error': 'Only doctors can create blockouts'}, status=403)

    required = ['date', 'start_time', 'end_time']
    for field in required:
        if not request.data.get(field):
            return Response({'error': f'{field} is required'}, status=400)

    doctor = user
    if user.role == 'admin' and request.data.get('doctor_id'):
        try:
            doctor = User.objects.get(id=request.data.get('doctor_id'), role='doctor')
        except User.DoesNotExist:
            return Response({'error': 'Doctor not found'}, status=404)

    blockout = ScheduleBlockout.objects.create(
        doctor=doctor,
        date=request.data.get('date'),
        start_time=request.data.get('start_time'),
        end_time=request.data.get('end_time'),
        reason=request.data.get('reason', 'other'),
        notes=request.data.get('notes', ''),
        is_recurring=request.data.get('is_recurring', False),
        recurrence_days=request.data.get('recurrence_days', []),
    )

    return Response({
        'message': 'Schedule blockout created successfully',
        'id': blockout.id,
        'date': str(blockout.date),
        'start_time': str(blockout.start_time),
        'end_time': str(blockout.end_time),
    }, status=201)


@api_view(['DELETE'])
@permission_classes([IsAuthenticated])
def delete_schedule_blockout(request, blockout_id):
    """Delete a schedule blockout"""
    try:
        blockout = ScheduleBlockout.objects.get(id=blockout_id)
    except ScheduleBlockout.DoesNotExist:
        return Response({'error': 'Blockout not found'}, status=404)

    if blockout.doctor != request.user and request.user.role != 'admin':
        return Response({'error': 'Permission denied'}, status=403)

    blockout.delete()
    return Response({'message': 'Blockout deleted successfully'})


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def doctor_schedule_overview(request, doctor_id):
    """Get full schedule overview for a doctor — leaves, blockouts, custom hours"""
    try:
        doctor = User.objects.get(id=doctor_id, role='doctor')
    except User.DoesNotExist:
        return Response({'error': 'Doctor not found'}, status=404)

    date_from = request.query_params.get('date_from', str(date.today()))
    date_to = request.query_params.get('date_to', str(
        date.today().replace(day=1) if date.today().month == 12
        else date(date.today().year, date.today().month + 1, 1)
    ))

    leaves = DoctorLeave.objects.filter(
        doctor=doctor,
        status='approved',
        start_date__lte=date_to,
        end_date__gte=date_from,
    )

    blockouts = ScheduleBlockout.objects.filter(
        doctor=doctor,
        date__range=[date_from, date_to],
    )

    custom_hours = DoctorWorkingHours.objects.filter(
        doctor=doctor,
        date__range=[date_from, date_to],
    )

    return Response({
        'doctor': doctor.full_name,
        'period': {'from': date_from, 'to': date_to},
        'approved_leaves': [{
            'start_date': str(l.start_date),
            'end_date': str(l.end_date),
            'leave_type': l.leave_type,
            'duration_days': l.duration_days,
        } for l in leaves],
        'blockouts': [{
            'date': str(b.date),
            'start_time': str(b.start_time),
            'end_time': str(b.end_time),
            'reason': b.reason,
        } for b in blockouts],
        'custom_hours': [{
            'date': str(h.date),
            'is_working': h.is_working,
            'start_time': str(h.start_time) if h.start_time else None,
            'end_time': str(h.end_time) if h.end_time else None,
        } for h in custom_hours],
    })

# FIREBASE PUSH NOTIFICATIONS

from .models import FCMDevice


def get_firebase_app():
    """Initialize Firebase app (singleton)"""
    import firebase_admin
    from firebase_admin import credentials
    from django.conf import settings as django_settings
    import os

    if not firebase_admin._apps:
        cred_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            django_settings.FIREBASE_CREDENTIALS_PATH
        )
        if os.path.exists(cred_path):
            cred = credentials.Certificate(cred_path)
            firebase_admin.initialize_app(cred)
    return firebase_admin.get_app() if firebase_admin._apps else None


def send_push_notification(user, title, body, data=None, notification_type='general'):
    """Send FCM push notification to all active devices of a user"""
    from django.conf import settings as django_settings
    if not django_settings.FCM_ENABLED:
        return {'sent': 0, 'reason': 'FCM disabled'}

    try:
        import firebase_admin
        from firebase_admin import messaging

        app = get_firebase_app()
        if not app:
            return {'sent': 0, 'reason': 'Firebase not initialized'}

        devices = FCMDevice.objects.filter(user=user, is_active=True)
        if not devices.exists():
            return {'sent': 0, 'reason': 'No active devices'}

        # Unread badge count
        try:
            from .models import Notification
            badge_count = Notification.objects.filter(
                recipient=user, is_read=False
            ).count()
        except Exception:
            badge_count = 1

        # Notification type config
        type_config = {
            'new_message':        {'icon': 'ic_message',      'color': '#4CAF50', 'sound': 'default'},
            'appointment_booked': {'icon': 'ic_appointment',  'color': '#2196F3', 'sound': 'default'},
            'appointment_reminder':{'icon': 'ic_reminder',    'color': '#FF9800', 'sound': 'default'},
            'consultation':       {'icon': 'ic_consultation', 'color': '#9C27B0', 'sound': 'default'},
            'general':            {'icon': 'ic_notification', 'color': '#2196F3', 'sound': 'default'},
        }
        cfg = type_config.get(notification_type, type_config['general'])

        # Ensure all data values are strings (FCM requirement)
        str_data = {k: str(v) for k, v in (data or {}).items()}
        str_data['notification_type'] = notification_type

        sent = 0
        failed_tokens = []

        for device in devices:
            try:
                message = messaging.Message(
                    notification=messaging.Notification(
                        title=title,
                        body=body,
                    ),
                    data=str_data,
                    token=device.token,
                    android=messaging.AndroidConfig(
                        priority='high',
                        notification=messaging.AndroidNotification(
                            icon=cfg['icon'],
                            color=cfg['color'],
                            sound=cfg['sound'],
                            notification_count=badge_count,
                        ),
                    ),
                    apns=messaging.APNSConfig(
                        payload=messaging.APNSPayload(
                            aps=messaging.Aps(
                                sound=cfg['sound'],
                                badge=badge_count,
                            ),
                        ),
                    ),
                )
                messaging.send(message)
                sent += 1
            except Exception as e:
                error_str = str(e)
                if 'registration-token-not-registered' in error_str or \
                   'invalid-registration-token' in error_str:
                    failed_tokens.append(device.token)

        if failed_tokens:
            FCMDevice.objects.filter(
                user=user, token__in=failed_tokens
            ).update(is_active=False)

        return {'sent': sent, 'failed': len(failed_tokens)}

    except Exception as e:
        return {'sent': 0, 'error': str(e)}


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def register_fcm_device(request):
    """Register or update FCM device token"""
    token = request.data.get('token')
    platform = request.data.get('platform', 'android')
    device_name = request.data.get('device_name', '')

    if not token:
        return Response({'error': 'token is required'}, status=400)

    if platform not in ['android', 'ios', 'web']:
        return Response({'error': 'platform must be android, ios or web'}, status=400)

    device, created = FCMDevice.objects.update_or_create(
        user=request.user,
        token=token,
        defaults={
            'platform': platform,
            'device_name': device_name,
            'is_active': True,
        }
    )

    return Response({
        'message': f'Device {"registered" if created else "updated"} successfully',
        'id': device.id,
        'platform': device.platform,
        'device_name': device.device_name,
    }, status=201 if created else 200)


@api_view(['DELETE'])
@permission_classes([IsAuthenticated])
def unregister_fcm_device(request):
    """Unregister FCM device token (logout)"""
    token = request.data.get('token')
    if not token:
        return Response({'error': 'token is required'}, status=400)

    deleted = FCMDevice.objects.filter(
        user=request.user, token=token
    ).delete()

    if deleted[0] == 0:
        return Response({'error': 'Device not found'}, status=404)

    return Response({'message': 'Device unregistered successfully'})


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def list_fcm_devices(request):
    """List all registered devices for the current user"""
    devices = FCMDevice.objects.filter(user=request.user)
    return Response({
        'count': devices.count(),
        'devices': [{
            'id': d.id,
            'platform': d.platform,
            'device_name': d.device_name,
            'is_active': d.is_active,
            'created_at': d.created_at.isoformat(),
        } for d in devices],
    })


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def send_test_push(request):
    """Send a test push notification to yourself"""
    result = send_push_notification(
        user=request.user,
        title='🔔 Healzy Test Notification',
        body='Push notifications are working correctly!',
        data={'type': 'test', 'url': '/'},
    )
    return Response({
        'message': 'Test notification sent',
        'result': result,
    })


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def send_push_to_user(request):
    """Admin sends push notification to any user"""
    if request.user.role != 'admin':
        return Response({'error': 'Only admins can send push notifications'}, status=403)

    user_id = request.data.get('user_id')
    title = request.data.get('title')
    body = request.data.get('body')

    if not all([user_id, title, body]):
        return Response({'error': 'user_id, title and body are required'}, status=400)

    try:
        target_user = User.objects.get(id=user_id)
    except User.DoesNotExist:
        return Response({'error': 'User not found'}, status=404)

    result = send_push_notification(
        user=target_user,
        title=title,
        body=body,
        data=request.data.get('data', {}),
    )

    return Response({
        'message': 'Push notification sent',
        'recipient': target_user.full_name,
        'result': result,
    })

# ADVANCED ANALYTICS & REPORTS

from django.db.models import Count, Avg, Q
from django.db.models.functions import TruncMonth, TruncWeek, TruncDate


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def platform_analytics(request):
    """Overall platform statistics — admin only"""
    if request.user.role != 'admin':
        return Response({'error': 'Admin access required'}, status=403)

    from .models import Appointment, Review
    today = date.today()
    this_month_start = today.replace(day=1)
    last_month_start = (this_month_start - timedelta(days=1)).replace(day=1)

    # User stats
    total_patients = User.objects.filter(role='patient').count()
    total_doctors = User.objects.filter(role='doctor', is_approved=True).count()
    new_patients_this_month = User.objects.filter(
        role='patient', date_joined__date__gte=this_month_start
    ).count()
    new_doctors_this_month = User.objects.filter(
        role='doctor', date_joined__date__gte=this_month_start
    ).count()

    # Appointment stats
    total_appointments = Appointment.objects.count()
    appointments_this_month = Appointment.objects.filter(
        date__gte=this_month_start
    ).count()
    completed_appointments = Appointment.objects.filter(status='completed').count()
    cancelled_appointments = Appointment.objects.filter(status='cancelled').count()
    completion_rate = round(
        (completed_appointments / total_appointments * 100) if total_appointments > 0 else 0, 1
    )

    # Revenue (if payment model exists)
    # Appointments by status
    appointment_status_breakdown = Appointment.objects.values('status').annotate(
        count=Count('id')
    ).order_by('-count')

    # Monthly growth — patients
    monthly_signups = User.objects.filter(
        role='patient',
        date_joined__date__gte=today - timedelta(days=180)
    ).annotate(
        month=TruncMonth('date_joined')
    ).values('month').annotate(count=Count('id')).order_by('month')

    # Monthly appointments
    monthly_appointments = Appointment.objects.filter(
        date__gte=today - timedelta(days=180)
    ).annotate(
        month=TruncMonth('date')
    ).values('month').annotate(count=Count('id')).order_by('month')

    # Top specializations by appointment count
    top_specializations = Appointment.objects.values(
        'doctor__specialization'
    ).annotate(
        count=Count('id')
    ).order_by('-count')[:10]

    # Review stats
    avg_platform_rating = Review.objects.aggregate(avg=Avg('rating'))['avg']

    # Active doctors (had appointment in last 30 days)
    active_doctors = Appointment.objects.filter(
        date__gte=today - timedelta(days=30)
    ).values('doctor').distinct().count()

    return Response({
        'generated_at': timezone.now().isoformat(),
        'users': {
            'total_patients': total_patients,
            'total_doctors': total_doctors,
            'new_patients_this_month': new_patients_this_month,
            'new_doctors_this_month': new_doctors_this_month,
            'active_doctors_last_30_days': active_doctors,
        },
        'appointments': {
            'total': total_appointments,
            'this_month': appointments_this_month,
            'completed': completed_appointments,
            'cancelled': cancelled_appointments,
            'completion_rate_percent': completion_rate,
            'by_status': list(appointment_status_breakdown),
        },
        'reviews': {
            'avg_platform_rating': round(avg_platform_rating, 2) if avg_platform_rating else None,
            'total_reviews': Review.objects.count(),
        },
        'growth': {
            'monthly_patient_signups': [
                {'month': str(m['month'])[:7], 'count': m['count']}
                for m in monthly_signups
            ],
            'monthly_appointments': [
                {'month': str(m['month'])[:7], 'count': m['count']}
                for m in monthly_appointments
            ],
        },
        'top_specializations': [
            {'specialization': s['doctor__specialization'], 'appointments': s['count']}
            for s in top_specializations if s['doctor__specialization']
        ],
    })


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def doctor_analytics(request, doctor_id=None):
    """Doctor performance analytics"""
    user = request.user

    if user.role == 'doctor':
        target_doctor = user
    elif user.role == 'admin':
        if not doctor_id:
            return Response({'error': 'doctor_id is required'}, status=400)
        try:
            target_doctor = User.objects.get(id=doctor_id, role='doctor')
        except User.DoesNotExist:
            return Response({'error': 'Doctor not found'}, status=404)
    else:
        return Response({'error': 'Permission denied'}, status=403)

    from .models import Appointment, Review
    today = date.today()
    this_month_start = today.replace(day=1)

    appointments = Appointment.objects.filter(doctor=target_doctor)
    reviews = Review.objects.filter(doctor=target_doctor)

    # Appointment stats
    total = appointments.count()
    completed = appointments.filter(status='completed').count()
    cancelled = appointments.filter(status='cancelled').count()
    this_month = appointments.filter(date__gte=this_month_start).count()
    completion_rate = round((completed / total * 100) if total > 0 else 0, 1)

    # Rating stats
    avg_rating = reviews.aggregate(avg=Avg('rating'))['avg']
    rating_breakdown = reviews.values('rating').annotate(
        count=Count('id')
    ).order_by('rating')

    # Weekly appointments for last 8 weeks
    weekly_appointments = appointments.filter(
        date__gte=today - timedelta(weeks=8)
    ).annotate(
        week=TruncWeek('date')
    ).values('week').annotate(count=Count('id')).order_by('week')

    # Busiest days of week
    from django.db.models.functions import ExtractWeekDay
    busiest_days = appointments.filter(
        status='completed'
    ).annotate(
        weekday=ExtractWeekDay('date')
    ).values('weekday').annotate(
        count=Count('id')
    ).order_by('-count')

    day_names = {1: 'Sunday', 2: 'Monday', 3: 'Tuesday', 4: 'Wednesday',
                 5: 'Thursday', 6: 'Friday', 7: 'Saturday'}

    # Patient retention — patients with 2+ appointments
    repeat_patients = appointments.values('patient').annotate(
        visits=Count('id')
    ).filter(visits__gte=2).count()

    total_unique_patients = appointments.values('patient').distinct().count()
    retention_rate = round(
        (repeat_patients / total_unique_patients * 100)
        if total_unique_patients > 0 else 0, 1
    )

    # Recent reviews
    recent_reviews = reviews.order_by('-created_at')[:5]

    return Response({
        'doctor': target_doctor.full_name,
        'specialization': target_doctor.specialization,
        'generated_at': timezone.now().isoformat(),
        'appointments': {
            'total': total,
            'completed': completed,
            'cancelled': cancelled,
            'this_month': this_month,
            'completion_rate_percent': completion_rate,
        },
        'patients': {
            'total_unique': total_unique_patients,
            'repeat_patients': repeat_patients,
            'retention_rate_percent': retention_rate,
        },
        'ratings': {
            'average': round(avg_rating, 2) if avg_rating else None,
            'total_reviews': reviews.count(),
            'breakdown': {str(r['rating']): r['count'] for r in rating_breakdown},
        },
        'trends': {
            'weekly_appointments': [
                {'week': str(w['week'])[:10], 'count': w['count']}
                for w in weekly_appointments
            ],
            'busiest_days': [
                {'day': day_names.get(d['weekday'], 'Unknown'), 'count': d['count']}
                for d in busiest_days
            ],
        },
        'recent_reviews': [{
            'rating': r.rating,
            'comment': r.comment,
            'patient': r.patient.full_name,
            'date': r.created_at.strftime('%Y-%m-%d'),
        } for r in recent_reviews],
    })


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def patient_analytics(request, patient_id=None):
    """Patient health analytics"""
    user = request.user

    if user.role == 'patient':
        target_patient = user
    elif user.role in ['doctor', 'admin']:
        if not patient_id:
            return Response({'error': 'patient_id is required'}, status=400)
        try:
            target_patient = User.objects.get(id=patient_id, role='patient')
        except User.DoesNotExist:
            return Response({'error': 'Patient not found'}, status=404)
    else:
        return Response({'error': 'Permission denied'}, status=403)

    from .models import (
        Appointment, MedicalRecord, VitalSign,
        BloodPressureLog, Medication, LabOrder
    )

    today = date.today()

    # Appointment history
    appointments = Appointment.objects.filter(patient=target_patient)
    total_appointments = appointments.count()
    completed_appointments = appointments.filter(status='completed').count()

    # Doctors visited
    doctors_visited = appointments.values('doctor').distinct().count()

    # Specializations visited
    specializations = appointments.filter(
        status='completed'
    ).values('doctor__specialization').distinct()

    # Vital signs trends (last 30 days)
    vitals = VitalSign.objects.filter(
        patient=target_patient,
        recorded_at__date__gte=today - timedelta(days=30)
    ).order_by('recorded_at')

    vitals_trend = [{
        'date': str(v.recorded_at.date()),
        'blood_pressure_systolic': v.blood_pressure_systolic,
        'blood_pressure_diastolic': v.blood_pressure_diastolic,
        'heart_rate': v.heart_rate,
        'temperature': v.temperature,
        'weight': v.weight,
    } for v in vitals]

    # BP trend
    bp_logs = BloodPressureLog.objects.filter(
        patient=target_patient
    ).order_by('-measured_at')[:30]

    bp_trend = [{
        'date': str(b.measured_at.date()),
        'systolic': b.systolic,
        'diastolic': b.diastolic,
        'category': b.category,
    } for b in bp_logs]

    # Active medications
    active_meds = Medication.objects.filter(
        patient=target_patient,
        is_active=True
    ).count() if hasattr(Medication, 'is_active') else 0

    # Lab orders
    lab_orders = LabOrder.objects.filter(patient=target_patient)
    abnormal_labs = 0
    for order in lab_orders:
        if order.tests.filter(is_abnormal=True).exists():
            abnormal_labs += 1

    # Monthly appointment frequency
    monthly_visits = appointments.filter(
        date__gte=today - timedelta(days=365)
    ).annotate(
        month=TruncMonth('date')
    ).values('month').annotate(count=Count('id')).order_by('month')

    return Response({
        'patient': target_patient.full_name,
        'generated_at': timezone.now().isoformat(),
        'appointments': {
            'total': total_appointments,
            'completed': completed_appointments,
            'doctors_visited': doctors_visited,
            'specializations_visited': [
                s['doctor__specialization']
                for s in specializations
                if s['doctor__specialization']
            ],
        },
        'health_metrics': {
            'vitals_logged': vitals.count(),
            'bp_readings': bp_logs.count(),
            'active_medications': active_meds,
            'lab_orders_total': lab_orders.count(),
            'lab_orders_with_abnormal': abnormal_labs,
        },
        'trends': {
            'vitals': vitals_trend,
            'blood_pressure': bp_trend,
            'monthly_visits': [
                {'month': str(m['month'])[:7], 'visits': m['count']}
                for m in monthly_visits
            ],
        },
    })


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def appointment_report(request):
    """Detailed appointment report with filters"""
    if request.user.role not in ['admin', 'doctor']:
        return Response({'error': 'Permission denied'}, status=403)

    from .models import Appointment
    today = date.today()

    date_from = request.query_params.get('date_from', str(today - timedelta(days=30)))
    date_to = request.query_params.get('date_to', str(today))
    doctor_id = request.query_params.get('doctor_id')
    status_filter = request.query_params.get('status')

    appointments = Appointment.objects.filter(
        date__range=[date_from, date_to]
    ).select_related('doctor', 'patient')

    if doctor_id:
        appointments = appointments.filter(doctor_id=doctor_id)
    elif request.user.role == 'doctor':
        appointments = appointments.filter(doctor=request.user)

    if status_filter:
        appointments = appointments.filter(status=status_filter)

    total = appointments.count()
    by_status = appointments.values('status').annotate(count=Count('id'))
    by_specialization = appointments.values(
        'doctor__specialization'
    ).annotate(count=Count('id')).order_by('-count')

    # Daily breakdown
    daily = appointments.annotate(
        day=TruncDate('date')
    ).values('day').annotate(count=Count('id')).order_by('day')

    return Response({
        'period': {'from': date_from, 'to': date_to},
        'total_appointments': total,
        'by_status': {s['status']: s['count'] for s in by_status},
        'by_specialization': [
            {'specialization': s['doctor__specialization'], 'count': s['count']}
            for s in by_specialization if s['doctor__specialization']
        ],
        'daily_breakdown': [
            {'date': str(d['day']), 'count': d['count']}
            for d in daily
        ],
        'appointments': [{
            'id': a.id,
            'date': str(a.date),
            'time': str(a.time),
            'patient': a.patient.full_name,
            'doctor': a.doctor.full_name,
            'specialization': a.doctor.specialization,
            'status': a.status,
        } for a in appointments[:100]],
    })


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def top_doctors_report(request):
    """Top performing doctors report — admin only"""
    if request.user.role != 'admin':
        return Response({'error': 'Admin access required'}, status=403)

    from .models import Appointment, Review
    today = date.today()
    date_from = request.query_params.get(
        'date_from', str(today - timedelta(days=30))
    )

    top_doctors = User.objects.filter(
        role='doctor', is_approved=True
    ).annotate(
        total_appointments=Count(
            'doctor_appointments',
            filter=Q(doctor_appointments__date__gte=date_from)
        ),
        completed_appointments=Count(
            'doctor_appointments',
            filter=Q(
                doctor_appointments__date__gte=date_from,
                doctor_appointments__status='completed'
            )
        ),
        avg_rating=Avg('received_reviews__rating'),
        total_reviews=Count('received_reviews'),
    ).order_by('-completed_appointments')[:20]

    return Response({
        'period_from': date_from,
        'generated_at': timezone.now().isoformat(),
        'top_doctors': [{
            'id': d.id,
            'name': d.full_name,
            'specialization': d.specialization,
            'total_appointments': d.total_appointments,
            'completed_appointments': d.completed_appointments,
            'avg_rating': round(d.avg_rating, 2) if d.avg_rating else None,
            'total_reviews': d.total_reviews,
        } for d in top_doctors],
    })

from .models import MedicalFacility, FacilityReview, MedCity, MedDistrict
from .serializers import (
    FacilityListSerializer, FacilityDetailSerializer,
    FacilityReviewSerializer, MedCitySerializer, MedDistrictSerializer
)


class MedCityListView(generics.ListAPIView):
    serializer_class = MedCitySerializer
    permission_classes = [AllowAny]

    def get_queryset(self):
        queryset = MedCity.objects.select_related('region').all()
        region_id = self.request.query_params.get('region')
        if region_id:
            queryset = queryset.filter(region_id=region_id)
        return queryset


class MedDistrictListView(generics.ListAPIView):
    serializer_class = MedDistrictSerializer
    permission_classes = [AllowAny]

    def get_queryset(self):
        queryset = MedDistrict.objects.select_related('city', 'region').all()
        city_id = self.request.query_params.get('city')
        if city_id:
            queryset = queryset.filter(city_id=city_id)
        return queryset


class FacilityListView(generics.ListAPIView):
    serializer_class = FacilityListSerializer
    permission_classes = [AllowAny]

    def get_queryset(self):
        queryset = MedicalFacility.objects.select_related(
            'city', 'district', 'city__region'
        ).filter(is_active=True)

        # Filters
        region = self.request.query_params.get('region')
        city = self.request.query_params.get('city')
        district = self.request.query_params.get('district')
        facility_type = self.request.query_params.get('type')
        ownership = self.request.query_params.get('ownership')
        search = self.request.query_params.get('search')
        is_24h = self.request.query_params.get('is_24h')
        has_ambulance = self.request.query_params.get('has_ambulance')
        verified = self.request.query_params.get('verified')

        if region:
            queryset = queryset.filter(city__region_id=region)
        if city:
            queryset = queryset.filter(city_id=city)
        if district:
            queryset = queryset.filter(district_id=district)
        if facility_type:
            queryset = queryset.filter(facility_type=facility_type)
        if ownership:
            queryset = queryset.filter(ownership_type=ownership)
        if search:
            queryset = queryset.filter(
                models.Q(name__icontains=search) |
                models.Q(name_ru__icontains=search) |
                models.Q(address__icontains=search)
            )
        if is_24h == 'true':
            queryset = queryset.filter(is_24_hours=True)
        if has_ambulance == 'true':
            queryset = queryset.filter(has_ambulance=True)
        if verified == 'true':
            queryset = queryset.filter(is_verified=True)

        specialization = self.request.query_params.get('specialization')
        has_lab = self.request.query_params.get('has_lab')
        has_pharmacy = self.request.query_params.get('has_pharmacy')
        accepts_insurance = self.request.query_params.get('accepts_insurance')

        if specialization:
            queryset = queryset.filter(specializations__icontains=specialization)
        if has_lab == 'true':
            queryset = queryset.filter(has_lab=True)
        if has_pharmacy == 'true':
            queryset = queryset.filter(has_pharmacy=True)
        if accepts_insurance == 'true':
            queryset = queryset.filter(accepts_insurance=True)

        ordering = self.request.query_params.get('ordering', '-is_featured')
        allowed_orderings = [
            '-avg_rating', 'avg_rating',
            '-total_reviews', 'total_reviews',
            '-is_featured', 'name'
        ]
        if ordering in allowed_orderings:
            queryset = queryset.order_by(ordering)

        return queryset



class FacilityDetailView(generics.RetrieveAPIView):
    serializer_class = FacilityDetailSerializer
    permission_classes = [AllowAny]
    queryset = MedicalFacility.objects.filter(is_active=True)

    def retrieve(self, request, *args, **kwargs):
        instance = self.get_object()
        instance.total_views += 1
        instance.save(update_fields=['total_views'])
        serializer = self.get_serializer(instance)
        return Response(serializer.data)


class FacilityReviewCreateView(generics.CreateAPIView):
    serializer_class = FacilityReviewSerializer
    permission_classes = [IsAuthenticated]

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context['request'] = self.request
        return context

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)


class FacilityReviewListView(generics.ListAPIView):
    serializer_class = FacilityReviewSerializer
    permission_classes = [AllowAny]

    def get_queryset(self):
        facility_id = self.kwargs['pk']
        return FacilityReview.objects.filter(
            facility_id=facility_id
        ).select_related('user', 'user__userprofile').order_by('-created_at')


class FacilityReviewDeleteView(generics.DestroyAPIView):
    serializer_class = FacilityReviewSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return FacilityReview.objects.filter(user=self.request.user)


class FacilityMarkHelpfulView(generics.GenericAPIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        try:
            review = FacilityReview.objects.get(pk=pk)
            review.helpful_count += 1
            review.save(update_fields=['helpful_count'])
            return Response({'helpful_count': review.helpful_count})
        except FacilityReview.DoesNotExist:
            return Response({'error': 'Review not found'}, status=404)

# Health Calculators
@api_view(['POST'])
@permission_classes([AllowAny])
def health_calculators(request):
    """BMI, BMR, ideal weight, calorie needs calculators"""
    calc_type = request.data.get('type')

    if calc_type == 'bmi':
        weight = float(request.data.get('weight_kg', 0))
        height = float(request.data.get('height_cm', 0))
        if not weight or not height:
            return Response({'error': 'weight_kg and height_cm required'}, status=400)
        height_m = height / 100
        bmi = round(weight / (height_m ** 2), 1)
        if bmi < 18.5:
            category = 'Underweight'
        elif bmi < 25:
            category = 'Normal weight'
        elif bmi < 30:
            category = 'Overweight'
        else:
            category = 'Obese'
        return Response({'bmi': bmi, 'category': category, 'healthy_range': '18.5 - 24.9'})

    elif calc_type == 'bmr':
        weight = float(request.data.get('weight_kg', 0))
        height = float(request.data.get('height_cm', 0))
        age = int(request.data.get('age', 0))
        gender = request.data.get('gender', 'male')
        if not all([weight, height, age]):
            return Response({'error': 'weight_kg, height_cm, age and gender required'}, status=400)
        if gender == 'male':
            bmr = round(10 * weight + 6.25 * height - 5 * age + 5)
        else:
            bmr = round(10 * weight + 6.25 * height - 5 * age - 161)
        return Response({
            'bmr': bmr,
            'calories_sedentary': round(bmr * 1.2),
            'calories_light': round(bmr * 1.375),
            'calories_moderate': round(bmr * 1.55),
            'calories_active': round(bmr * 1.725),
        })

    elif calc_type == 'ideal_weight':
        height_cm = float(request.data.get('height_cm', 0))
        gender = request.data.get('gender', 'male')
        if not height_cm:
            return Response({'error': 'height_cm required'}, status=400)
        height_in = height_cm / 2.54
        if gender == 'male':
            ideal = round(50 + 2.3 * (height_in - 60), 1)
        else:
            ideal = round(45.5 + 2.3 * (height_in - 60), 1)
        return Response({
            'ideal_weight_kg': max(ideal, 30),
            'healthy_range_kg': {
                'min': round(max(ideal, 30) - 5, 1),
                'max': round(max(ideal, 30) + 5, 1),
            }
        })

    elif calc_type == 'water':
        weight = float(request.data.get('weight_kg', 0))
        activity = request.data.get('activity', 'moderate')
        if not weight:
            return Response({'error': 'weight_kg required'}, status=400)
        base = weight * 35
        if activity == 'active':
            base += 500
        elif activity == 'very_active':
            base += 1000
        return Response({
            'water_ml': round(base),
            'water_glasses': round(base / 250),
        })

    elif calc_type == 'heart_rate_zones':
        age = int(request.data.get('age', 0))
        if not age:
            return Response({'error': 'age required'}, status=400)
        max_hr = 220 - age
        return Response({
            'max_heart_rate': max_hr,
            'zones': {
                'rest': '60-100 bpm',
                'warm_up': f'{round(max_hr * 0.5)}-{round(max_hr * 0.6)} bpm',
                'fat_burn': f'{round(max_hr * 0.6)}-{round(max_hr * 0.7)} bpm',
                'cardio': f'{round(max_hr * 0.7)}-{round(max_hr * 0.85)} bpm',
                'peak': f'{round(max_hr * 0.85)}-{max_hr} bpm',
            }
        })

    else:
        return Response({
            'available_calculators': ['bmi', 'bmr', 'ideal_weight', 'water', 'heart_rate_zones'],
            'usage': 'POST with type=bmi and required fields'
        })
    

# Health Tips & Daily Wellness
@api_view(['GET'])
@permission_classes([AllowAny])
def health_tips(request):
    """Daily health tips and wellness advice"""

    category = request.query_params.get('category', 'general')

    from django.core.cache import cache
    cache_key = f"health_tips_{category}"
    cached = cache.get(cache_key)
    if cached:
        return Response(cached)

    tips = {
        'general': [
            {'title': 'Stay Hydrated', 'tip': 'Drink at least 8 glasses of water daily. Start your morning with a glass of warm water.', 'icon': '💧'},
            {'title': 'Move Every Hour', 'tip': 'Stand up and walk for 2 minutes every hour to reduce risks of prolonged sitting.', 'icon': '🚶'},
            {'title': 'Sleep 7-9 Hours', 'tip': 'Quality sleep boosts immunity, improves mood and helps maintain healthy weight.', 'icon': '😴'},
            {'title': 'Eat the Rainbow', 'tip': 'Include colorful fruits and vegetables in every meal for diverse nutrients.', 'icon': '🌈'},
            {'title': 'Wash Your Hands', 'tip': 'Wash hands for at least 20 seconds to prevent spread of infections.', 'icon': '🧼'},
            {'title': 'Limit Screen Time', 'tip': 'Follow the 20-20-20 rule: every 20 min, look 20 feet away for 20 seconds.', 'icon': '👁️'},
            {'title': 'Deep Breathing', 'tip': 'Practice 5 minutes of deep breathing daily to reduce stress and improve focus.', 'icon': '🫁'},
            {'title': 'Regular Check-ups', 'tip': 'Schedule annual health check-ups even when you feel healthy.', 'icon': '🏥'},
        ],
        'nutrition': [
            {'title': 'Breakfast Matters', 'tip': 'Never skip breakfast — it kickstarts metabolism and improves concentration.', 'icon': '🍳'},
            {'title': 'Reduce Sugar', 'tip': 'Limit added sugar to less than 25g per day for women, 36g for men.', 'icon': '🍬'},
            {'title': 'Healthy Fats', 'tip': 'Include avocados, nuts and olive oil — healthy fats support brain function.', 'icon': '🥑'},
            {'title': 'Fiber is Key', 'tip': 'Aim for 25-35g of fiber daily from vegetables, fruits and whole grains.', 'icon': '🥦'},
            {'title': 'Protein with Every Meal', 'tip': 'Including protein in meals keeps you fuller longer and supports muscle health.', 'icon': '🥩'},
        ],
        'fitness': [
            {'title': '150 Min Per Week', 'tip': 'Aim for 150 minutes of moderate aerobic activity per week as recommended by WHO.', 'icon': '🏃'},
            {'title': 'Strength Training', 'tip': 'Include strength training 2x per week to maintain muscle mass and bone density.', 'icon': '💪'},
            {'title': 'Warm Up First', 'tip': 'Always warm up for 5-10 minutes before exercise to prevent injuries.', 'icon': '🔥'},
            {'title': 'Rest Days Matter', 'tip': 'Rest days are essential for muscle recovery and preventing overtraining.', 'icon': '🛌'},
            {'title': 'Walk More', 'tip': 'Aim for 10,000 steps daily. Park farther, take stairs, walk during calls.', 'icon': '👟'},
        ],
        'mental': [
            {'title': 'Practice Gratitude', 'tip': 'Write 3 things you are grateful for each morning to boost mental wellbeing.', 'icon': '🙏'},
            {'title': 'Limit News Intake', 'tip': 'Constant news consumption increases anxiety. Set specific times to check news.', 'icon': '📱'},
            {'title': 'Social Connections', 'tip': 'Strong social bonds are one of the biggest predictors of long-term health and happiness.', 'icon': '👥'},
            {'title': 'Mindfulness', 'tip': 'Even 5 minutes of mindfulness meditation daily reduces stress and improves focus.', 'icon': '🧘'},
            {'title': 'Nature Time', 'tip': 'Spending 20 minutes in nature significantly lowers cortisol (stress hormone) levels.', 'icon': '🌿'},
        ],
        'sleep': [
            {'title': 'Consistent Schedule', 'tip': 'Go to bed and wake up at the same time every day, even on weekends.', 'icon': '⏰'},
            {'title': 'Dark & Cool Room', 'tip': 'Keep bedroom temperature between 16-19°C and use blackout curtains for better sleep.', 'icon': '🌙'},
            {'title': 'No Screens Before Bed', 'tip': 'Avoid screens 1 hour before bed — blue light suppresses melatonin production.', 'icon': '📵'},
            {'title': 'Avoid Caffeine Late', 'tip': 'Stop caffeine intake after 2 PM as it has a half-life of 5-6 hours in your body.', 'icon': '☕'},
        ],
    }

    if category == 'all':
        all_tips = []
        for cat, cat_tips in tips.items():
            for t in cat_tips:
                t['category'] = cat
                all_tips.append(t)
        random.shuffle(all_tips)
        return Response({'category': 'all', 'tips': all_tips})

    if category not in tips:
        return Response({
            'available_categories': list(tips.keys()) + ['all'],
        }, status=400)

    # Daily tip — changes every day based on date
    import datetime
    day_index = datetime.date.today().toordinal() % len(tips[category])
    daily_tip = tips[category][day_index]

    result = {
        'category': category,
        'daily_tip': daily_tip,
        'all_tips': tips[category],
        'available_categories': list(tips.keys()),
    }
    cache.set(cache_key, result, timeout=3600)
    return Response(result)

# Symptom Checker (AI-powered)

@api_view(['POST'])
@permission_classes([AllowAny])
@csrf_exempt
def symptom_checker(request):
    """AI-powered symptom checker using Google Generative AI"""
    symptoms = request.data.get('symptoms', [])
    age = request.data.get('age')
    gender = request.data.get('gender', 'unknown')
    duration = request.data.get('duration', 'unknown')

    if not symptoms:
        return Response({'error': 'symptoms list is required'}, status=400)

    if isinstance(symptoms, list):
        symptoms_text = ', '.join(symptoms)
    else:
        symptoms_text = str(symptoms)

    import os
    api_key = os.getenv('ANTHROPIC_API_KEY')
    if not api_key:
        return Response({'error': 'AI service not configured'}, status=500)

    prompt = f"""You are a medical assistant. A patient reports the following:
- Symptoms: {symptoms_text}
- Age: {age or 'not specified'}
- Gender: {gender}
- Duration: {duration}

Respond ONLY in this exact JSON format with no extra text:
{{
  "possible_conditions": [
    {{"name": "Condition name", "likelihood": "High/Medium/Low", "description": "Brief description"}}
  ],
  "urgency": "Emergency/See doctor soon/Monitor at home",
  "urgency_reason": "Brief reason",
  "recommended_specialist": "Type of doctor to see",
  "home_care_tips": ["tip1", "tip2", "tip3"],
  "warning_signs": ["sign1", "sign2"],
  "disclaimer": "This is not a medical diagnosis. Please consult a doctor."
}}"""

    try:
        import anthropic
        client = anthropic.Anthropic(api_key=api_key)
        message = client.messages.create(
            model='claude-haiku-4-5',
            max_tokens=1000,
            messages=[{'role': 'user', 'content': prompt}])
        text = message.content[0].text.strip()
        import re
        json_match = re.search(r'\{.*\}', text, re.DOTALL)
        if json_match:
            text = json_match.group()
        else:
            text = text.replace('```json', '').replace('```', '').strip()
            result = json.loads(text)
            return Response(result)
    except Exception as e:
        return Response({'error': f'AI analysis failed: {str(e)}'}, status=502)
        
# Health News
@api_view(['GET'])
@permission_classes([AllowAny])
def health_news(request):
    """Fetch latest health & medical news via NewsAPI"""
    import requests as http_requests
    from django.core.cache import cache

    category = request.query_params.get('category', 'health')
    page = int(request.query_params.get('page', 1))
    page_size = min(int(request.query_params.get('page_size', 10)), 20)
    cache_key = f'health_news_{category}_{page}_{page_size}'

    # Return cached result if available (cache for 30 minutes)
    cached = cache.get(cache_key)
    if cached:
        return Response(cached)

    import os
    api_key = os.getenv('NEWSAPI_KEY')
    if not api_key:
        return Response({'error': 'News API not configured'}, status=500)

    # Category to query mapping
    queries = {
        'health': 'health OR medicine OR medical',
        'technology': 'medical technology OR health tech OR digital health',
        'surgery': 'surgery OR surgical innovation OR minimally invasive',
        'research': 'medical research OR clinical trial OR drug discovery',
        'ai': 'AI healthcare OR artificial intelligence medicine',
    }
    query = queries.get(category, queries['health'])

    try:
        response = http_requests.get(
            'https://newsapi.org/v2/everything',
            params={
                'q': query,
                'language': 'en',
                'sortBy': 'publishedAt',
                'page': page,
                'pageSize': page_size,
                'apiKey': api_key,
            },
            timeout=10
        )
        data = response.json()

        if data.get('status') != 'ok':
            return Response({'error': data.get('message', 'News API error')}, status=502)

        # Clean up articles
        articles = []
        for article in data.get('articles', []):
            if article.get('title') and article.get('title') != '[Removed]':
                articles.append({
                    'title': article.get('title'),
                    'description': article.get('description'),
                    'url': article.get('url'),
                    'image': article.get('urlToImage'),
                    'source': article.get('source', {}).get('name'),
                    'published_at': article.get('publishedAt'),
                    'author': article.get('author'),
                })

        result = {
            'total_results': data.get('totalResults', 0),
            'page': page,
            'page_size': page_size,
            'category': category,
            'articles': articles,
        }

        # Cache for 30 minutes
        cache.set(cache_key, result, 60 * 30)
        return Response(result)

    except Exception as e:
        return Response({'error': f'Failed to fetch news: {str(e)}'}, status=502)
    
# Nearby Hospitals
@api_view(['GET'])
@permission_classes([AllowAny])
def nearby_hospitals(request):
    """Find nearby hospitals and clinics using Google Places API"""
    from django.core.cache import cache
    cache_key = f"hospitals_{lat}_{lng}_{radius}_{facility_type}"
    cached = cache.get(cache_key)
    if cached:
        return Response(cached)

    lat = request.query_params.get('lat')
    lng = request.query_params.get('lng')
    radius = int(request.query_params.get('radius', 5000))
    facility_type = request.query_params.get('type', 'hospital')

    if not lat or not lng:
        return Response({'error': 'lat and lng parameters are required'}, status=400)

    import os
    api_key = os.getenv('GOOGLE_MAPS_API_KEY')
    if not api_key:
        return Response({'error': 'Maps API not configured'}, status=500)

    type_map = {
        'hospital': 'hospital',
        'clinic': 'doctor',
        'pharmacy': 'pharmacy',
        'dentist': 'dentist',
        'emergency': 'hospital',
    }
    place_type = type_map.get(facility_type, 'hospital')

    try:
        response = http_requests.get(
            'https://maps.googleapis.com/maps/api/place/nearbysearch/json',
            params={
                'location': f'{lat},{lng}',
                'radius': radius,
                'type': place_type,
                'key': api_key,
            },
            timeout=10
        )
        data = response.json()

        if data.get('status') not in ['OK', 'ZERO_RESULTS']:
            return Response({'error': data.get('status')}, status=502)

        places = []
        for place in data.get('results', []):
            places.append({
                'name': place.get('name'),
                'address': place.get('vicinity'),
                'rating': place.get('rating'),
                'total_ratings': place.get('user_ratings_total'),
                'open_now': place.get('opening_hours', {}).get('open_now'),
                'lat': place.get('geometry', {}).get('location', {}).get('lat'),
                'lng': place.get('geometry', {}).get('location', {}).get('lng'),
                'place_id': place.get('place_id'),
                'types': place.get('types', []),
            })

        places.sort(key=lambda x: x.get('rating') or 0, reverse=True)
        
        result = {
            'count': len(places),
            'radius_meters': radius,
            'facilities': places,
        }
        cache.set(cache_key, result, timeout=1800)  # cache 30 mins
        return Response(result)

    except Exception as e:
        return Response({'error': f'Failed to fetch nearby places: {str(e)}'}, status=502)

# Smart Doctor Matching
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def smart_doctor_match(request):
    """AI-powered doctor matching based on symptoms and patient needs"""
    import anthropic
    import os

    symptoms = request.data.get('symptoms', [])
    age = request.data.get('age')
    gender = request.data.get('gender', 'unknown')
    preferences = request.data.get('preferences', '')
    language = request.data.get('language', 'en')

    if not symptoms:
        return Response({'error': 'symptoms are required'}, status=400)

    if isinstance(symptoms, list):
        symptoms_text = ', '.join(symptoms)
    else:
        symptoms_text = str(symptoms)

    # Get all active doctors from DB
    from django.contrib.auth import get_user_model
    User = get_user_model()
    doctors = User.objects.filter(
        role='doctor',
        is_active=True,
        is_verified=True
    ).select_related('profile')[:50]

    doctor_list = []
    for doc in doctors:
        profile = getattr(doc, 'profile', None)
        avg_rating = 0
        doctor_list.append({
            'id': doc.id,
            'name': f"{doc.first_name} {doc.last_name}".strip() or doc.username,
            'specialization': getattr(profile, 'specialization', 'General'),
            'experience_years': getattr(profile, 'experience_years', 0),
            'rating': round(avg_rating, 1),
            'languages': getattr(profile, 'languages', 'Uzbek, Russian'),
        })

    if not doctor_list:
        return Response({'error': 'No doctors available'}, status=404)

    import json
    api_key = os.getenv('ANTHROPIC_API_KEY')
    client = anthropic.Anthropic(api_key=api_key)

    prompt = f"""You are a medical triage assistant. Match the best doctors for this patient.

Patient info:
- Symptoms: {symptoms_text}
- Age: {age or 'not specified'}
- Gender: {gender}
- Preferences: {preferences or 'none'}

Available doctors:
{json.dumps(doctor_list, indent=2)}

Return ONLY a JSON object in this exact format:
{{
  "top_matches": [
    {{
      "doctor_id": 1,
      "match_score": 95,
      "reason": "Brief reason why this doctor is a good match",
      "urgency": "routine/soon/urgent"
    }}
  ],
  "recommended_specialization": "Name of specialization needed",
  "explanation": "Brief explanation of why these doctors were chosen"
}}

Return top 3 matches maximum, ordered by match_score descending."""

    try:
        message = client.messages.create(
            model='claude-haiku-4-5',
            max_tokens=1000,
            messages=[{'role': 'user', 'content': prompt}]
        )
        text = message.content[0].text.strip()
        import re
        json_match = re.search(r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}', text, re.DOTALL)
        if json_match:
            text = json_match.group()
        else:
            text = text.replace('```json', '').replace('```', '').strip()
            result = json.loads(text)
            result = json.loads(text)

        # Enrich results with full doctor info
        doctor_map = {d['id']: d for d in doctor_list}
        for match in result.get('top_matches', []):
            doc_info = doctor_map.get(match['doctor_id'], {})
            match['doctor_name'] = doc_info.get('name')
            match['specialization'] = doc_info.get('specialization')
            match['rating'] = doc_info.get('rating')
            match['experience_years'] = doc_info.get('experience_years')

        return Response(result)
    except Exception as e:
        return Response({'error': f'Matching failed: {str(e)}'}, status=502)
    
# Medical PDF Summarizer
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def medical_pdf_summarizer(request):
    """Upload a medical PDF and get a plain-language AI explanation"""
    import anthropic
    import os
    import base64

    if 'file' not in request.FILES:
        return Response({'error': 'No file uploaded'}, status=400)

    pdf_file = request.FILES['file']
    if not pdf_file.name.endswith('.pdf'):
        return Response({'error': 'File must be a PDF'}, status=400)

    language = request.data.get('language', 'en')

    pdf_bytes = pdf_file.read()
    pdf_base64 = base64.standard_b64encode(pdf_bytes).decode('utf-8')

    lang_instruction = {
        'en': 'Respond in English.',
        'ru': 'Respond in Russian.',
        'uz': 'Respond in Uzbek.',
    }.get(language, 'Respond in English.')

    api_key = os.getenv('ANTHROPIC_API_KEY')
    client = anthropic.Anthropic(api_key=api_key)

    try:
        message = client.messages.create(
            model='claude-haiku-4-5',
            max_tokens=2000,
            messages=[{
                'role': 'user',
                'content': [
                    {
                        'type': 'document',
                        'source': {
                            'type': 'base64',
                            'media_type': 'application/pdf',
                            'data': pdf_base64,
                        }
                    },
                    {
                        'type': 'text',
                        'text': f"""You are a medical assistant helping patients understand their medical reports.
Analyze this medical document and provide:
1. A simple summary (2-3 sentences) in plain language
2. Key findings (list the most important results)
3. What these results mean for the patient
4. Any values that are abnormal or concerning
5. Recommended next steps

Use simple language a non-medical person can understand. Avoid jargon.
{lang_instruction}

Format your response as JSON:
{{
  "summary": "Simple 2-3 sentence overview",
  "key_findings": ["finding 1", "finding 2"],
  "what_it_means": "Plain language explanation",
  "abnormal_values": ["value 1 - why concerning"],
  "next_steps": ["step 1", "step 2"],
  "urgency": "routine/soon/urgent"
}}"""
                    }
                ]
            }]
        )
        text = message.content[0].text.strip()
        if not text:
            return Response({'error': 'AI returned empty response'}, status=502)
        import re
        json_match = re.search(r'\{.*\}', text, re.DOTALL)
        if json_match:
            result = json.loads(json_match.group())
        else:
            return Response({'raw_response': text}, status=200)
        return Response(result)
    except Exception as e:
        return Response({'error': f'Analysis failed: {str(e)}'}, status=502)

# SOAP Notes Generator
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def soap_notes_generator(request):
    """Generate structured SOAP notes from consultation chat history"""
    import anthropic
    import os
    import json

    consultation_id = request.data.get('consultation_id')
    chat_history = request.data.get('chat_history', [])
    patient_name = request.data.get('patient_name', 'Patient')
    doctor_name = request.data.get('doctor_name', 'Doctor')
    language = request.data.get('language', 'en')

    if not chat_history:
        return Response({'error': 'chat_history is required'}, status=400)

    chat_text = '\n'.join([
        f"{msg.get('sender', 'Unknown')}: {msg.get('message', '')}"
        for msg in chat_history
    ])

    lang_instruction = {
        'en': 'Respond in English.',
        'ru': 'Respond in Russian.',
        'uz': 'Respond in Uzbek.',
    }.get(language, 'Respond in English.')

    api_key = os.getenv('ANTHROPIC_API_KEY')
    client = anthropic.Anthropic(api_key=api_key)

    prompt = f"""You are a medical assistant helping doctors create SOAP notes.
Based on this consultation chat between {doctor_name} and {patient_name}, generate structured SOAP notes.

Consultation chat:
{chat_text}

{lang_instruction}

Return ONLY a JSON object in this exact format:
{{
  "subjective": {{
    "chief_complaint": "Main reason for visit",
    "history": "Patient's description of symptoms, onset, duration",
    "symptoms": ["symptom 1", "symptom 2"]
  }},
  "objective": {{
    "observations": "Doctor's observations from the chat",
    "vitals_mentioned": "Any vitals mentioned",
    "findings": ["finding 1", "finding 2"]
  }},
  "assessment": {{
    "diagnosis": "Likely diagnosis or differential",
    "severity": "mild/moderate/severe",
    "notes": "Clinical assessment notes"
  }},
  "plan": {{
    "treatment": ["treatment 1", "treatment 2"],
    "medications": ["medication 1"],
    "follow_up": "Follow up instructions",
    "referrals": "Any referrals needed"
  }},
  "summary": "One paragraph summary of the consultation"
}}"""

    try:
        message = client.messages.create(
            model='claude-haiku-4-5',
            max_tokens=2000,
            messages=[{'role': 'user', 'content': prompt}]
        )
        text = message.content[0].text.strip()
        if not text:
            return Response({'error': 'AI returned empty response'}, status=502)
        import re
        json_match = re.search(r'\{.*\}', text, re.DOTALL)
        if json_match:
            result = json.loads(json_match.group())
        else:
            return Response({'raw_response': text}, status=200)
        return Response(result)
    except Exception as e:
        return Response({'error': f'SOAP generation failed: {str(e)}'}, status=502)
    

# AI Consultation Summary
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def consultation_ai_summary(request, consultation_id):
    """Get or generate AI summary for a completed consultation"""
    import anthropic
    import os

    try:
        consultation = Consultation.objects.get(id=consultation_id)
    except Consultation.DoesNotExist:
        return Response({'error': 'Consultation not found'}, status=404)

    if request.user not in [consultation.patient, consultation.doctor]:
        return Response({'error': 'Permission denied'}, status=403)

    # Return cached summary if exists
    if consultation.ai_summary:
        return Response({
            'consultation_id': consultation_id,
            'ai_summary': consultation.ai_summary,
            'cached': True,
        })

    # Get all messages
    messages = Message.objects.filter(
        consultation=consultation
    ).select_related('sender').order_by('created_at')

    if not messages.exists():
        return Response({'error': 'No messages in this consultation'}, status=400)

    chat_text = '\n'.join([
        f"{msg.sender.full_name} ({'Doctor' if msg.sender.role == 'doctor' else 'Patient'}): {msg.content}"
        for msg in messages
    ])

    api_key = os.getenv('ANTHROPIC_API_KEY')
    client = anthropic.Anthropic(api_key=api_key)

    prompt = f"""You are a medical assistant. Summarize this doctor-patient consultation concisely.

Consultation between:
- Patient: {consultation.patient.full_name}
- Doctor: {consultation.doctor.full_name}
- Date: {consultation.created_at.strftime('%Y-%m-%d')}
- Duration: {int((consultation.completed_at - consultation.started_at).total_seconds() / 60) if consultation.completed_at and consultation.started_at else 'Unknown'} minutes

Chat transcript:
{chat_text}

Return ONLY a JSON object:
{{
  "chief_complaint": "Main reason for consultation",
  "symptoms_discussed": ["symptom 1", "symptom 2"],
  "doctor_assessment": "Doctor's assessment in plain language",
  "treatment_plan": ["treatment 1", "treatment 2"],
  "medications_prescribed": ["med 1"],
  "follow_up": "Follow up instructions",
  "summary": "2-3 sentence plain language summary",
  "urgency_flags": ["any urgent concerns raised"]
}}"""

    try:
        message = client.messages.create(
            model='claude-haiku-4-5',
            max_tokens=1500,
            messages=[{'role': 'user', 'content': prompt}]
        )
        text = message.content[0].text.strip()
        import re
        json_match = re.search(r'\{.*\}', text, re.DOTALL)
        if json_match:
            result = json.loads(json_match.group())
        else:
            return Response({'raw_response': text}, status=200)

        # Cache the summary on the consultation
        consultation.ai_summary = json.dumps(result)
        consultation.save(update_fields=['ai_summary'])

        return Response({
            'consultation_id': consultation_id,
            'ai_summary': result,
            'cached': False,
        })
    except Exception as e:
        return Response({'error': f'Summary generation failed: {str(e)}'}, status=502)

# AI Prescription Analyzer
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def prescription_analyzer(request):
    """Upload a prescription image and get AI analysis of medications"""
    import anthropic
    import os
    import base64

    if 'file' not in request.FILES:
        return Response({'error': 'No file uploaded'}, status=400)

    uploaded_file = request.FILES['file']
    allowed_types = ['image/jpeg', 'image/png', 'image/webp', 'image/gif', 'application/pdf']
    if uploaded_file.content_type not in allowed_types:
        return Response({'error': 'File must be an image (JPEG, PNG, WebP) or PDF'}, status=400)

    language = request.data.get('language', 'en')
    lang_instruction = {
        'en': 'Respond in English.',
        'ru': 'Respond in Russian.',
        'uz': 'Respond in Uzbek.',
    }.get(language, 'Respond in English.')

    file_bytes = uploaded_file.read()
    file_base64 = base64.standard_b64encode(file_bytes).decode('utf-8')

    api_key = os.getenv('ANTHROPIC_API_KEY')
    client = anthropic.Anthropic(api_key=api_key)

    # Build content based on file type
    if uploaded_file.content_type == 'application/pdf':
        file_content = {
            'type': 'document',
            'source': {
                'type': 'base64',
                'media_type': 'application/pdf',
                'data': file_base64,
            }
        }
    else:
        file_content = {
            'type': 'image',
            'source': {
                'type': 'base64',
                'media_type': uploaded_file.content_type,
                'data': file_base64,
            }
        }

    prompt = f"""You are a clinical pharmacist. Analyze the uploaded image or document.
If it is a prescription or contains medication information, extract all details.
If it does NOT appear to be a prescription, still return the JSON with best-effort analysis and note it in the summary field.
NEVER ask questions. ALWAYS return only the JSON object, no matter what the image shows.

{lang_instruction}

Return ONLY a JSON object:
{{
  "medications": [
    {{
      "name": "Medication name",
      "generic_name": "Generic/chemical name",
      "dosage": "Dose and frequency",
      "duration": "How long to take it",
      "purpose": "What this medication treats",
      "instructions": "How to take it (with food, time of day, etc)",
      "side_effects": ["common side effect 1", "common side effect 2"],
      "warnings": ["important warning 1"]
    }}
  ],
  "interactions": ["Any interactions between the prescribed medications"],
  "general_instructions": "Overall instructions from the prescription",
  "doctor_name": "Doctor name if visible",
  "patient_name": "Patient name if visible",
  "prescription_date": "Date if visible",
  "summary": "2-3 sentence plain language summary of this prescription",
  "urgency": "routine/important/urgent"
}}"""

    try:
        message = client.messages.create(
            model='claude-haiku-4-5',
            max_tokens=2000,
            messages=[{
                'role': 'user',
                'content': [
                    file_content,
                    {'type': 'text', 'text': prompt}
                ]
            }]
        )
        text = message.content[0].text.strip()
        if not text:
            return Response({'error': 'AI returned empty response'}, status=502)
        import re
        json_match = re.search(r'\{.*\}', text, re.DOTALL)
        if json_match:
            result = json.loads(json_match.group())
        else:
            return Response({'raw_response': text}, status=200)
        return Response(result)
    except Exception as e:
        return Response({'error': f'Analysis failed: {str(e)}'}, status=502)

# Diet & Nutrition Planner
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def diet_nutrition_planner(request):
    """Generate personalized diet and nutrition plan based on health conditions"""
    import anthropic
    import os

    # Patient info
    age = request.data.get('age')
    gender = request.data.get('gender', '')
    weight_kg = request.data.get('weight_kg')
    height_cm = request.data.get('height_cm')
    conditions = request.data.get('conditions', [])       # e.g. ['diabetes', 'hypertension']
    medications = request.data.get('medications', [])     # e.g. ['metformin', 'lisinopril']
    allergies = request.data.get('allergies', [])         # e.g. ['nuts', 'dairy']
    goal = request.data.get('goal', 'general health')     # e.g. 'weight loss', 'muscle gain'
    diet_type = request.data.get('diet_type', 'omnivore') # e.g. 'vegetarian', 'vegan'
    language = request.data.get('language', 'en')

    if not age:
        return Response({'error': 'age is required'}, status=400)

    lang_instruction = {
        'en': 'Respond in English.',
        'ru': 'Respond in Russian.',
        'uz': 'Respond in Uzbek.',
    }.get(language, 'Respond in English.')

    # Calculate BMI if height and weight provided
    bmi_info = ''
    if weight_kg and height_cm:
        bmi = round(float(weight_kg) / ((float(height_cm) / 100) ** 2), 1)
        bmi_info = f'BMI: {bmi}'

    api_key = os.getenv('ANTHROPIC_API_KEY')
    client = anthropic.Anthropic(api_key=api_key)

    prompt = f"""You are a clinical dietitian creating a personalized nutrition plan.

Patient Profile:
- Age: {age}, Gender: {gender}
- Weight: {weight_kg}kg, Height: {height_cm}cm {bmi_info}
- Medical conditions: {', '.join(conditions) if conditions else 'None'}
- Current medications: {', '.join(medications) if medications else 'None'}
- Allergies/intolerances: {', '.join(allergies) if allergies else 'None'}
- Diet type: {diet_type}
- Goal: {goal}

{lang_instruction}

Create a practical, medically-appropriate nutrition plan. Return ONLY a JSON object:
{{
  "daily_calories": 2000,
  "macros": {{
    "protein_g": 120,
    "carbs_g": 200,
    "fat_g": 65,
    "fiber_g": 30
  }},
  "meal_plan": {{
    "breakfast": {{
      "description": "meal description",
      "foods": ["food 1", "food 2"],
      "calories": 450
    }},
    "morning_snack": {{
      "description": "snack description",
      "foods": ["food 1"],
      "calories": 150
    }},
    "lunch": {{
      "description": "meal description",
      "foods": ["food 1", "food 2", "food 3"],
      "calories": 550
    }},
    "afternoon_snack": {{
      "description": "snack description",
      "foods": ["food 1"],
      "calories": 150
    }},
    "dinner": {{
      "description": "meal description",
      "foods": ["food 1", "food 2", "food 3"],
      "calories": 600
    }}
  }},
  "foods_to_avoid": ["food 1 - reason", "food 2 - reason"],
  "foods_to_prioritize": ["food 1 - benefit", "food 2 - benefit"],
  "hydration": "Daily water intake recommendation",
  "supplements": ["supplement 1 - why", "supplement 2 - why"],
  "medical_notes": "Important dietary notes based on conditions and medications",
  "weekly_tips": ["tip 1", "tip 2", "tip 3"],
  "summary": "2-3 sentence personalized summary"
}}"""

    try:
        message = client.messages.create(
            model='claude-haiku-4-5',
            max_tokens=2500,
            messages=[{'role': 'user', 'content': prompt}]
        )
        text = message.content[0].text.strip()
        if not text:
            return Response({'error': 'AI returned empty response'}, status=502)
        import re
        json_match = re.search(r'\{.*\}', text, re.DOTALL)
        if json_match:
            result = json.loads(json_match.group())
        else:
            return Response({'raw_response': text}, status=200)
        return Response(result)
    except Exception as e:
        return Response({'error': f'Plan generation failed: {str(e)}'}, status=502)

# Multilingual Translation
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def translate_consultation(request):
    """Translate consultation messages between English, Russian and Uzbek"""
    import anthropic
    import os
    import json

    text = request.data.get('text', '')
    source_language = request.data.get('source_language', 'auto')
    target_language = request.data.get('target_language', 'en')
    context = request.data.get('context', 'medical')

    if not text:
        return Response({'error': 'text is required'}, status=400)

    language_names = {
        'en': 'English',
        'ru': 'Russian',
        'uz': 'Uzbek',
    }

    target_name = language_names.get(target_language, 'English')
    source_instruction = (
        'Auto-detect the source language.' if source_language == 'auto'
        else f'Source language is {language_names.get(source_language, source_language)}.'
    )

    api_key = os.getenv('ANTHROPIC_API_KEY')
    client = anthropic.Anthropic(api_key=api_key)

    prompt = f"""You are a medical translator. {source_instruction}
Translate the following {context} text to {target_name}.
Keep all medical terms accurate. Keep the tone professional.

Text to translate:
{text}

Return ONLY a JSON object:
{{
  "translated_text": "The translated text here",
  "source_language": "detected or provided source language",
  "target_language": "{target_language}",
  "medical_terms": ["any important medical terms identified"]
}}"""

    try:
        message = client.messages.create(
            model='claude-haiku-4-5',
            max_tokens=2000,
            messages=[{'role': 'user', 'content': prompt}]
        )
        text_response = message.content[0].text.strip()
        if not text_response:
            return Response({'error': 'AI returned empty response'}, status=502)
        import re
        json_match = re.search(r'\{.*\}', text_response, re.DOTALL)
        if json_match:
            result = json.loads(json_match.group())
        else:
            return Response({'raw_response': text_response}, status=200)
        return Response(result)
    except Exception as e:
        return Response({'error': f'Translation failed: {str(e)}'}, status=502)


        # Patient Health Timeline
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def patient_health_timeline(request, patient_id=None):
    """Chronological feed of all patient health events in one view"""
    from .models import (
        Appointment, Message, Consultation, VitalSigns,
        BloodPressureLog, LabOrder, Notification
    )

    user = request.user

    if user.role == 'patient':
        target_patient = user
    elif user.role in ['doctor', 'admin']:
        if not patient_id:
            return Response({'error': 'patient_id is required'}, status=400)
        try:
            target_patient = User.objects.get(id=patient_id, role='patient')
        except User.DoesNotExist:
            return Response({'error': 'Patient not found'}, status=404)
    else:
        return Response({'error': 'Permission denied'}, status=403)

    days = int(request.query_params.get('days', 90))
    since = timezone.now() - timedelta(days=days)

    timeline = []

    # Appointments
    appointments = Appointment.objects.filter(
        patient=target_patient,
        appointment_date__gte=since.date()
    ).select_related('doctor')
    for a in appointments:
        timeline.append({
            'type': 'appointment',
            'date': a.appointment_date.isoformat(),
            'title': f'Appointment with Dr. {a.doctor.full_name}',
            'detail': f'{a.doctor.specialization} — {a.status}',
            'status': a.status,
            'icon': 'calendar',
        })

    # Consultations
    consultations = Consultation.objects.filter(
        patient=target_patient,
        created_at__gte=since
    ).select_related('doctor')
    for c in consultations:
        timeline.append({
            'type': 'consultation',
            'date': c.created_at.isoformat(),
            'title': f'Consultation with Dr. {c.doctor.full_name}',
            'detail': c.title or c.status,
            'status': c.status,
            'icon': 'chat',
        })

    # Vital signs
    vitals = VitalSigns.objects.filter(
        patient=target_patient,
        recorded_at__gte=since
    )
    for v in vitals:
        timeline.append({
            'type': 'vital_sign',
            'date': v.recorded_at.isoformat(),
            'title': 'Vital Signs Recorded',
            'detail': f'HR: {v.heart_rate} bpm, Temp: {v.temperature}°C, Weight: {v.weight} kg',
            'icon': 'heart',
        })

    # Blood pressure logs
    bp_logs = BloodPressureLog.objects.filter(
        patient=target_patient,
        measured_at__gte=since
    )
    for b in bp_logs:
        timeline.append({
            'type': 'blood_pressure',
            'date': b.measured_at.isoformat(),
            'title': 'Blood Pressure Reading',
            'detail': f'{b.systolic}/{b.diastolic} mmHg — {b.category}',
            'icon': 'activity',
        })

    # Lab orders
    lab_orders = LabOrder.objects.filter(
        patient=target_patient,
        created_at__gte=since
    ).select_related('doctor')
    for l in lab_orders:
        timeline.append({
            'type': 'lab_order',
            'date': l.created_at.isoformat(),
            'title': f'Lab Order — {l.status}',
            'detail': f'Ordered by Dr. {l.doctor.full_name}',
            'status': l.status,
            'icon': 'flask',
        })

    # Sort all events by date descending
    timeline.sort(key=lambda x: x['date'], reverse=True)

    return Response({
        'patient': target_patient.full_name,
        'days': days,
        'total_events': len(timeline),
        'generated_at': timezone.now().isoformat(),
        'timeline': timeline,
    })