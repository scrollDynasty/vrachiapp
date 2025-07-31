from rest_framework import status, generics
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from django.contrib.auth import login, logout
from django.conf import settings
import requests
import json
from django.db import models

from .models import User, UserProfile, Region, City, District
from .serializers import (
    UserSerializer, RegisterSerializer, LoginSerializer, 
    GoogleAuthSerializer, PasswordResetSerializer, UserProfileSerializer, UserProfileReadSerializer,
    RegionSerializer, CitySerializer, DistrictSerializer
)


class RegisterView(generics.CreateAPIView):
    """Регистрация пользователя"""
    queryset = User.objects.all()
    permission_classes = (AllowAny,)
    serializer_class = RegisterSerializer

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        
        # Создаем профиль пользователя
        UserProfile.objects.create(user=user)
        
        # Входим в систему
        login(request, user)
        
        return Response({
            'user': UserSerializer(user).data,
            'message': 'Пользователь успешно зарегистрирован'
        }, status=status.HTTP_201_CREATED)


class LoginView(generics.GenericAPIView):
    """Вход пользователя"""
    permission_classes = (AllowAny,)
    serializer_class = LoginSerializer

    def post(self, request):
        print(f"DEBUG: LoginView.post вызван")
        print(f"DEBUG: Данные входа: {request.data}")
        
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.validated_data['user']
        
        print(f"DEBUG: Пользователь найден: {user}")
        
        # Входим в систему
        login(request, user)
        
        print(f"DEBUG: Пользователь вошел в систему")
        print(f"DEBUG: Сессия: {request.session.session_key}")
        print(f"DEBUG: Пользователь в сессии: {request.session.get('_auth_user_id')}")
        
        return Response({
            'user': UserSerializer(user).data,
            'message': 'Успешный вход'
        })


class LogoutView(generics.GenericAPIView):
    """Выход пользователя"""
    permission_classes = (IsAuthenticated,)

    def post(self, request):
        logout(request)
        return Response({'message': 'Успешный выход'})





class UserProfileView(generics.RetrieveUpdateAPIView):
    """Профиль пользователя"""
    permission_classes = (IsAuthenticated,)
    serializer_class = UserSerializer

    def get_object(self):
        return self.request.user


from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator

@method_decorator(csrf_exempt, name='dispatch')
class GoogleAuthView(generics.GenericAPIView):
    """Google OAuth аутентификация"""
    permission_classes = (AllowAny,)
    serializer_class = GoogleAuthSerializer

    def post(self, request):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        access_token = serializer.validated_data['access_token']
        
        # Получаем информацию о пользователе от Google
        google_user_info = self.get_google_user_info(access_token)
        
        if not google_user_info:
            return Response(
                {'error': 'Не удалось получить информацию от Google'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Создаем или получаем пользователя
        user = self.get_or_create_google_user(google_user_info)
        
        # Входим в систему
        login(request, user)
        
        return Response({
            'user': UserSerializer(user).data,
            'message': 'Успешная аутентификация через Google'
        })

    def get_google_user_info(self, access_token):
        """Получает информацию о пользователе от Google"""
        try:
            response = requests.get(
                'https://www.googleapis.com/oauth2/v2/userinfo',
                headers={'Authorization': f'Bearer {access_token}'}
            )
            if response.status_code == 200:
                return response.json()
        except Exception as e:
            print(f"Ошибка при получении данных от Google: {e}")
        return None

    def get_or_create_google_user(self, google_user_info):
        """Создает или получает пользователя по Google ID"""
        google_id = google_user_info.get('id')
        email = google_user_info.get('email')
        
        # Ищем пользователя по Google ID или email
        user = User.objects.filter(
            models.Q(google_id=google_id) | models.Q(email=email)
        ).first()
        
        if user:
            # Обновляем Google ID если его не было
            if not user.google_id:
                user.google_id = google_id
                user.save()
            return user
        
        # Создаем нового пользователя
        user = User.objects.create_user(
            username=email,
            email=email,
            first_name=google_user_info.get('given_name', ''),
            last_name=google_user_info.get('family_name', ''),
            google_id=google_id,
            is_verified=True,
            avatar=google_user_info.get('picture', '')
        )
        
        # Создаем профиль
        UserProfile.objects.create(user=user)
        
        return user


class PasswordResetView(generics.GenericAPIView):
    """Сброс пароля"""
    permission_classes = (AllowAny,)
    serializer_class = PasswordResetSerializer

    def post(self, request):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        email = serializer.validated_data['email']
        
        try:
            user = User.objects.get(email=email)
            # Здесь будет отправка email для сброса пароля
            return Response({
                'message': 'Инструкции по сбросу пароля отправлены на email'
            })
        except User.DoesNotExist:
            return Response({
                'message': 'Инструкции по сбросу пароля отправлены на email'
            })


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def check_auth(request):
    """Проверка аутентификации"""
    return Response({
        'user': UserSerializer(request.user).data,
        'is_authenticated': True
    })


@api_view(['GET'])
@permission_classes([AllowAny])
def get_csrf_token(request):
    """Получение CSRF токена"""
    from django.middleware.csrf import get_token
    return Response({'csrfToken': get_token(request)})


@api_view(['GET'])
@permission_classes([AllowAny])
def list_users(request):
    """Список всех пользователей (только для разработки)"""
    users = User.objects.all()
    return Response({
        'users': UserSerializer(users, many=True).data,
        'count': users.count()
    })


@api_view(['GET'])
@permission_classes([AllowAny])
def get_regions(request):
    """Получение списка регионов"""
    regions = Region.objects.all()
    return Response(RegionSerializer(regions, many=True).data)


@api_view(['GET'])
@permission_classes([AllowAny])
def get_cities(request):
    """Получение списка городов по региону"""
    region_id = request.GET.get('region_id')
    if region_id:
        cities = City.objects.filter(region_id=region_id)
    else:
        cities = City.objects.all()
    return Response(CitySerializer(cities, many=True).data)


@api_view(['GET'])
@permission_classes([AllowAny])
def get_districts(request):
    """Получение списка районов по региону"""
    region_id = request.GET.get('region_id')
    if region_id:
        districts = District.objects.filter(region_id=region_id)
    else:
        districts = District.objects.all()
    return Response(DistrictSerializer(districts, many=True).data)

@api_view(['POST'])
@permission_classes([AllowAny])
def detect_location(request):
    """Определение местоположения по координатам"""
    
    import requests
    
    try:
        lat = float(request.data.get('latitude'))
        lng = float(request.data.get('longitude'))
        
        # Отладочная информация
        print(f"DEBUG: Получены координаты lat={lat}, lng={lng}")
        print(f"DEBUG: Все данные запроса: {request.data}")
        
        # Функции для извлечения адресов из разных API
        def extract_nominatim_address(data):
            """Извлекает детальный адрес из Nominatim API"""
            address = data.get('address', {})
            display_name = data.get('display_name', '')
            
            # Пытаемся собрать детальный адрес
            parts = []
            
            # Улица
            if address.get('road'):
                parts.append(f"ул. {address['road']}")
            
            # Номер дома
            if address.get('house_number'):
                parts.append(address['house_number'])
            
            # Район/микрорайон
            if address.get('suburb'):
                parts.append(address['suburb'])
            
            # Город
            if address.get('city'):
                parts.append(address['city'])
            elif address.get('town'):
                parts.append(address['town'])
            
            # Если собрали детальный адрес
            if parts:
                return ", ".join(parts)
            
            # Если нет деталей, используем display_name но убираем дублирование
            if display_name:
                # Убираем дублирование "Ташкент, Ташкент"
                parts = display_name.split(', ')
                unique_parts = []
                for part in parts:
                    if part not in unique_parts:
                        unique_parts.append(part)
                return ', '.join(unique_parts)
            
            return display_name
        
        def extract_bigdatacloud_address(data):
            """Извлекает детальный адрес из BigDataCloud API"""
            parts = []
            
            # Улица
            if data.get('street'):
                parts.append(f"ул. {data['street']}")
            
            # Номер дома
            if data.get('houseNumber'):
                parts.append(data['houseNumber'])
            
            # Район
            if data.get('locality'):
                parts.append(data['locality'])
            
            # Город
            if data.get('city'):
                parts.append(data['city'])
            
            # Область
            if data.get('principalSubdivision'):
                parts.append(data['principalSubdivision'])
            
            if parts:
                return ", ".join(parts)
            
            # Fallback
            return f"{data.get('locality', '')}, {data.get('city', '')}, {data.get('countryName', '')}".strip(', ')
        
        def extract_locationiq_address(data):
            """Извлекает детальный адрес из LocationIQ API"""
            address = data.get('address', {})
            display_name = data.get('display_name', '')
            
            parts = []
            
            # Улица
            if address.get('road'):
                parts.append(f"ул. {address['road']}")
            
            # Номер дома
            if address.get('house_number'):
                parts.append(address['house_number'])
            
            # Район
            if address.get('suburb'):
                parts.append(address['suburb'])
            
            # Город
            if address.get('city'):
                parts.append(address['city'])
            
            if parts:
                return ", ".join(parts)
            
            return display_name
        
        # Пытаемся получить реальный адрес через геокодирование
        real_address = None
        try:
            # Используем несколько надежных API для геокодирования
            apis_to_try = [
                # OpenStreetMap Nominatim с более точными параметрами
                {
                    'url': f"https://nominatim.openstreetmap.org/reverse?format=json&lat={lat}&lon={lng}&zoom=16&addressdetails=1&accept-language=ru",
                    'extract': lambda data: extract_nominatim_address(data)
                },
                # BigDataCloud API с дополнительными параметрами
                {
                    'url': f"https://api.bigdatacloud.net/data/reverse-geocode-client?latitude={lat}&longitude={lng}&localityLanguage=ru",
                    'extract': lambda data: extract_bigdatacloud_address(data)
                }
            ]
            
            for api_config in apis_to_try:
                try:
                    response = requests.get(api_config['url'], timeout=5)
                    if response.status_code == 200:
                        data = response.json()
                        real_address = api_config['extract'](data)
                        
                        if real_address and len(real_address) > 10:  # Проверяем что адрес достаточно детальный
                            print(f"DEBUG: Получен детальный адрес: {real_address}")
                            break
                except Exception as e:
                    print(f"DEBUG: Ошибка API {api_config['url']}: {str(e)}")
                    continue
            
            # Если ни один API не сработал, используем координаты
            if not real_address or len(real_address) <= 10:
                real_address = f"Координаты: {lat:.6f}, {lng:.6f}"
                print(f"DEBUG: Используем координаты как fallback: {real_address}")
                
        except Exception as e:
            print(f"DEBUG: Ошибка при получении адреса: {str(e)}")
            real_address = f"Координаты: {lat:.6f}, {lng:.6f}"
        
        # Проверяем что координаты в пределах Узбекистана
        if not (37.0 <= lat <= 45.0 and 56.0 <= lng <= 73.0):
            print(f"DEBUG: Координаты за пределами Узбекистана: lat={lat}, lng={lng}")
            return Response({
                'success': False,
                'message': 'Координаты находятся за пределами Узбекистана'
            }, status=400)
        
        # Определяем регион по координатам через геокодирование
        region_name = None
        
        # Пытаемся определить регион из полученного адреса
        if real_address and "Ташкент" in real_address:
            region_name = "Город Ташкент"
        elif real_address and "Самарканд" in real_address:
            region_name = "Город Самарканд"
        elif real_address and "Бухара" in real_address:
            region_name = "Город Бухара"
        elif real_address and "Андижан" in real_address:
            region_name = "Город Андижан"
        elif real_address and "Наманган" in real_address:
            region_name = "Город Наманган"
        elif real_address and "Фергана" in real_address:
            region_name = "Город Фергана"
        elif real_address and "Карши" in real_address:
            region_name = "Город Карши"
        elif real_address and "Нукус" in real_address:
            region_name = "Город Нукус"
        elif real_address and "Термез" in real_address:
            region_name = "Город Термез"
        elif real_address and "Ургенч" in real_address:
            region_name = "Город Ургенч"
        elif real_address and "Навои" in real_address:
            region_name = "Город Навои"
        elif real_address and "Джизак" in real_address:
            region_name = "Город Джизак"
        elif real_address and "Гулистан" in real_address:
            region_name = "Город Гулистан"
        else:
            # Если не удалось определить по адресу, используем координаты
            if 41.0 <= lat <= 42.0 and 69.0 <= lng <= 70.0:
                region_name = "Ташкентская область"
            elif 39.0 <= lat <= 40.0 and 66.0 <= lng <= 68.0:
                region_name = "Самаркандская область"
            elif 39.0 <= lat <= 40.0 and 64.0 <= lng <= 66.0:
                region_name = "Бухарская область"
            elif 40.0 <= lat <= 41.0 and 71.0 <= lng <= 73.0:
                region_name = "Ферганская область"
            elif 40.5 <= lat <= 41.5 and 71.0 <= lng <= 72.5:
                region_name = "Андижанская область"
            elif 40.5 <= lat <= 41.5 and 71.0 <= lng <= 72.0:
                region_name = "Наманганская область"
            elif 38.0 <= lat <= 39.0 and 65.0 <= lng <= 67.0:
                region_name = "Кашкадарьинская область"
            elif 37.0 <= lat <= 38.0 and 67.0 <= lng <= 68.0:
                region_name = "Сурхандарьинская область"
            elif 40.0 <= lat <= 41.0 and 68.0 <= lng <= 69.0:
                region_name = "Сырдарьинская область"
            elif 40.0 <= lat <= 41.0 and 67.0 <= lng <= 69.0:
                region_name = "Джизакская область"
            elif 40.0 <= lat <= 41.0 and 65.0 <= lng <= 66.0:
                region_name = "Навоийская область"
            elif 41.0 <= lat <= 42.0 and 60.0 <= lng <= 62.0:
                region_name = "Хорезмская область"
            elif 42.0 <= lat <= 44.0 and 58.0 <= lng <= 61.0:
                region_name = "Республика Каракалпакстан"
            else:
                region_name = "Ташкентская область"  # По умолчанию
        
        print(f"DEBUG: Определен регион: {region_name}")
        
        region = Region.objects.filter(name=region_name).first()
        
        if region:
            # Определяем только регион, остальные поля пользователь заполнит вручную
            print(f"DEBUG: Определен регион: {region.name}")
            
            # Формируем сообщение
            message = f'Определен регион: {region.name}'
            

            
            return Response({
                'success': True,
                'region': RegionSerializer(region).data,
                'message': message
            })
        else:
            print(f"DEBUG: Регион не найден в базе данных: {region_name}")
            return Response({
                'success': False,
                'message': 'Регион не найден в базе данных'
            }, status=400)
    except Exception as e:
        print(f"DEBUG: Ошибка: {str(e)}")
        return Response({
            'success': False,
            'message': f'Ошибка при определении местоположения: {str(e)}'
        }, status=500)


@api_view(['GET', 'PUT'])
@permission_classes([IsAuthenticated])
def user_profile(request):
    """Профиль пользователя"""
    print(f"DEBUG: user_profile вызван, метод: {request.method}")
    print(f"DEBUG: Пользователь аутентифицирован: {request.user.is_authenticated}")
    print(f"DEBUG: Пользователь: {request.user}")
    
    profile, created = UserProfile.objects.get_or_create(user=request.user)
    
    if request.method == 'GET':
        return Response(UserProfileReadSerializer(profile).data)
    
    elif request.method == 'PUT':
        print(f"DEBUG: ===== НАЧАЛО ОБРАБОТКИ PUT ЗАПРОСА =====")
        print(f"DEBUG: Получены данные профиля: {request.data}")
        print(f"DEBUG: Тип данных: {type(request.data)}")
        print(f"DEBUG: Ключи: {list(request.data.keys())}")
        print(f"DEBUG: Content-Type: {request.content_type}")
        print(f"DEBUG: Пользователь: {request.user}")
        print(f"DEBUG: Аутентифицирован: {request.user.is_authenticated}")
        
        # Обновляем данные пользователя
        user_data = {}
        if 'first_name' in request.data:
            user_data['first_name'] = request.data['first_name']
        if 'last_name' in request.data:
            user_data['last_name'] = request.data['last_name']
        
        if user_data:
            for field, value in user_data.items():
                setattr(request.user, field, value)
            request.user.save()
            print(f"DEBUG: Данные пользователя обновлены")
        
        # Обновляем данные профиля
        profile_data = {k: v for k, v in request.data.items() 
                       if k not in ['first_name', 'last_name', 'email', 'username']}
        
        # Преобразуем названия полей для сериализатора
        if 'region' in profile_data:
            profile_data['region_id'] = profile_data.pop('region')
        if 'city' in profile_data:
            profile_data['city_id'] = profile_data.pop('city')
        if 'district' in profile_data:
            profile_data['district_id'] = profile_data.pop('district')
        
        print(f"DEBUG: Обработанные данные профиля: {profile_data}")
        
        serializer = UserProfileSerializer(profile, data=profile_data, partial=True)
        print(f"DEBUG: Сериализатор создан")
        print(f"DEBUG: Данные для сериализатора: {profile_data}")
        
        is_valid = serializer.is_valid()
        print(f"DEBUG: Результат валидации: {is_valid}")
        
        if is_valid:
            print(f"DEBUG: Данные валидны, сохраняем...")
            serializer.save()
            return Response(UserProfileReadSerializer(profile).data)
        else:
            print(f"DEBUG: ===== ОШИБКИ ВАЛИДАЦИИ =====")
            print(f"DEBUG: Ошибки валидации: {serializer.errors}")
            print(f"DEBUG: Полные ошибки: {serializer.errors}")
            print(f"DEBUG: Тип ошибок: {type(serializer.errors)}")
            return Response(serializer.errors, status=400) 