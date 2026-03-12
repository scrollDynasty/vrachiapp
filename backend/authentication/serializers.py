from rest_framework import serializers
from django.contrib.auth import authenticate
from django.contrib.auth.password_validation import validate_password
from .models import (
    User, UserProfile, Region, MedCity, MedDistrict,
    DoctorApplication, Consultation, Message,
    MedCity, MedDistrict, MedicalFacility, FacilityReview,
)
import json
from django.utils import timezone


class UserSerializer(serializers.ModelSerializer):
    full_name = serializers.CharField(read_only=True)
    initials = serializers.CharField(read_only=True)
    
    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'first_name', 'last_name', 'full_name', 'initials', 'is_staff', 'is_superuser', 'role']
        read_only_fields = ['id', 'is_staff', 'is_superuser', 'role']


class RegionSerializer(serializers.ModelSerializer):
    """Сериализатор для регионов"""
    class Meta:
        model = Region
        fields = ['id', 'name', 'name_uz']


class CitySerializer(serializers.ModelSerializer):
    """Сериализатор для городов"""
    region = RegionSerializer(read_only=True)
    
    class Meta:
        model = MedCity
        fields = ['id', 'name', 'name_uz', 'region']


class DistrictSerializer(serializers.ModelSerializer):
    """Сериализатор для районов"""
    region = RegionSerializer(read_only=True)
    city = CitySerializer(read_only=True)
    
    class Meta:
        model = MedDistrict
        fields = ['id', 'name', 'name_uz', 'region', 'city']


class UserProfileReadSerializer(serializers.ModelSerializer):
    """Сериализатор для чтения профиля пользователя"""
    region = RegionSerializer(read_only=True)
    city = CitySerializer(read_only=True)
    district = DistrictSerializer(read_only=True)
    first_name = serializers.CharField(source='user.first_name', read_only=True)
    last_name = serializers.CharField(source='user.last_name', read_only=True)
    email = serializers.CharField(source='user.email', read_only=True)
    
    class Meta:
        model = UserProfile
        fields = [
            'first_name', 'last_name', 'email', 'date_of_birth', 'gender', 'phone', 
            'region', 'city', 'district', 'address', 'medical_info', 'emergency_contact',
            # Поля врача
            'specialization', 'experience', 'education', 'license_number', 'languages', 'additional_info'
        ]
        read_only_fields = ['created_at', 'updated_at']


class UserProfileSerializer(serializers.ModelSerializer):
    user = UserSerializer(read_only=True)
    region_name = serializers.CharField(source='region.name', read_only=True)
    city_name = serializers.CharField(source='city.name', read_only=True)
    district_name = serializers.CharField(source='district.name', read_only=True)
    
    # Добавляем поля пользователя для редактирования
    first_name = serializers.CharField(source='user.first_name', required=False)
    last_name = serializers.CharField(source='user.last_name', required=False)
    role = serializers.CharField(source='user.role', required=False)
    
    class Meta:
        model = UserProfile
        fields = [
            'id', 'user', 'first_name', 'last_name', 'role',
            'date_of_birth', 'gender', 'phone', 
            'region', 'region_name', 'city', 'city_name', 'district', 'district_name', 'address',
            'medical_info', 'emergency_contact',
            'specialization', 'experience', 'education', 'license_number', 'languages', 'additional_info',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'user', 'created_at', 'updated_at']
        extra_kwargs = {
            'date_of_birth': {'required': False, 'allow_null': True},
            'gender': {'required': False, 'allow_null': True, 'allow_blank': True},
            'phone': {'required': False, 'allow_null': True, 'allow_blank': True},
            'region': {'required': False, 'allow_null': True},
            'city': {'required': False, 'allow_null': True},
            'district': {'required': False, 'allow_null': True},
            'address': {'required': False, 'allow_null': True, 'allow_blank': True},
            'medical_info': {'required': False, 'allow_null': True, 'allow_blank': True},
            'emergency_contact': {'required': False, 'allow_null': True, 'allow_blank': True},
            'specialization': {'required': False, 'allow_null': True, 'allow_blank': True},
            'experience': {'required': False, 'allow_null': True, 'allow_blank': True},
            'education': {'required': False, 'allow_null': True, 'allow_blank': True},
            'license_number': {'required': False, 'allow_null': True, 'allow_blank': True},
            'languages': {'required': False, 'allow_null': True},
            'additional_info': {'required': False, 'allow_null': True, 'allow_blank': True},
        }
    
    def validate(self, attrs):
        # Проверяем, является ли пользователь врачом
        request = self.context.get('request')
        if request and request.user:
            # Если пользователь врач, блокируем редактирование полей врача
            if request.user.role == 'doctor':
                doctor_fields = ['specialization', 'experience', 'education', 'license_number', 'languages', 'additional_info']
                for field in doctor_fields:
                    if field in attrs and attrs[field] is not None:
                        # Только блокируем если пытаются изменить существующее значение
                        current_value = getattr(self.instance, field, None)
                        if current_value != attrs[field]:
                            raise serializers.ValidationError({field: f"Поле '{field}' не может быть изменено врачом. Обратитесь к администратору."})
        
        # Очищаем пустые строки и пустые FK поля
        for field, value in list(attrs.items()):
            if isinstance(value, str) and value.strip() == '':
                attrs[field] = None
            elif field in ['region', 'city', 'district'] and (value == '' or value == 'null' or value == 0):
                attrs[field] = None
        
        return attrs
    
    def update(self, instance, validated_data):
        # Обновляем поля пользователя
        user_data = {}
        if 'user' in validated_data:
            user_data = validated_data.pop('user')
        
        # Обновляем поля профиля
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        
        # Обновляем поля пользователя
        if user_data:
            user = instance.user
            for attr, value in user_data.items():
                setattr(user, attr, value)
            user.save()
        
        return instance


class RegisterSerializer(serializers.ModelSerializer):
    """Сериализатор для регистрации"""
    password = serializers.CharField(write_only=True, validators=[validate_password])
    password_confirm = serializers.CharField(write_only=True)
    
    class Meta:
        model = User
        fields = ['email', 'username', 'first_name', 'last_name', 'password', 'password_confirm']
    
    def validate(self, attrs):
        if attrs['password'] != attrs['password_confirm']:
            raise serializers.ValidationError("Пароли не совпадают")
        return attrs
    
    def create(self, validated_data):
        validated_data.pop('password_confirm')
        user = User.objects.create_user(**validated_data)
        return user


class LoginSerializer(serializers.Serializer):
    """Сериализатор для входа"""
    email = serializers.EmailField()
    password = serializers.CharField()
    
    def validate(self, attrs):
        email = attrs.get('email')
        password = attrs.get('password')
        
        if email and password:
            user = authenticate(username=email, password=password)
            if not user:
                raise serializers.ValidationError('Неверные учетные данные')
            if not user.is_active:
                raise serializers.ValidationError('Аккаунт не активирован')
            attrs['user'] = user
        else:
            raise serializers.ValidationError('Необходимо указать email и пароль')
        
        return attrs


class PasswordResetSerializer(serializers.Serializer):
    """Сериализатор для сброса пароля"""
    email = serializers.EmailField()


class GoogleAuthSerializer(serializers.Serializer):
    """Сериализатор для Google OAuth"""
    access_token = serializers.CharField()
    
    def validate_access_token(self, value):
        # Здесь будет валидация Google токена
        return value


class PasswordResetConfirmSerializer(serializers.Serializer):
    """Сериализатор для подтверждения сброса пароля"""
    token = serializers.CharField()
    password = serializers.CharField(validators=[validate_password])
    password_confirm = serializers.CharField()
    
    def validate(self, attrs):
        if attrs['password'] != attrs['password_confirm']:
            raise serializers.ValidationError("Пароли не совпадают")
        return attrs


class DoctorApplicationSerializer(serializers.ModelSerializer):
    user = UserSerializer(read_only=True)
    reviewed_by = UserSerializer(read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    full_name = serializers.SerializerMethodField()
    region_name = serializers.CharField(source='region.name', read_only=True)
    city_name = serializers.CharField(source='city.name', read_only=True)
    district_name = serializers.CharField(source='district.name', read_only=True)
    
    class Meta:
        model = DoctorApplication
        fields = [
            'id', 'user', 'first_name', 'last_name', 'full_name', 'specialization', 
            'region', 'region_name', 'city', 'city_name', 'district', 'district_name',
            'languages', 'experience', 'education', 'license_number', 'additional_info',
            'date_of_birth', 'gender', 'phone', 'address', 'medical_info', 'emergency_contact',
            'photo', 'diploma', 'license', 'status', 'status_display', 'rejection_reason', 
            'created_at', 'updated_at', 'reviewed_by', 'reviewed_at'
        ]
        read_only_fields = ['id', 'user', 'created_at', 'updated_at', 'reviewed_by', 'reviewed_at']
    
    def get_full_name(self, obj):
        return f"{obj.first_name} {obj.last_name}".strip()


class DoctorApplicationCreateSerializer(serializers.ModelSerializer):
    first_name = serializers.CharField(max_length=100, required=True)
    last_name = serializers.CharField(max_length=100, required=True)
    region = serializers.IntegerField(required=False, allow_null=True)
    city = serializers.IntegerField(required=False, allow_null=True)
    district = serializers.IntegerField(required=False, allow_null=True)
    
    class Meta:
        model = DoctorApplication
        fields = [
            'first_name', 'last_name', 'specialization', 'region', 'city', 'district',
            'languages', 'experience', 'education', 'license_number', 'additional_info',
            'date_of_birth', 'gender', 'phone', 'address', 'medical_info', 'emergency_contact',
            'photo', 'diploma', 'license'
        ]
    
    def validate_languages(self, value):
        if isinstance(value, str):
            try:
                return json.loads(value)
            except json.JSONDecodeError:
                raise serializers.ValidationError("Неверный формат JSON для языков")
        return value
    
    def create(self, validated_data):
        # Обрабатываем ID для связей
        region_id = validated_data.pop('region', None)
        city_id = validated_data.pop('city', None)
        district_id = validated_data.pop('district', None)
        
        # Создаем заявку
        application = DoctorApplication.objects.create(**validated_data)
        
        # Устанавливаем связи
        if region_id:
            try:
                application.region = Region.objects.get(id=region_id)
            except Region.DoesNotExist:
                pass
        
        if city_id:
            try:
                application.city = MedCity.objects.get(id=city_id)
            except MedCity.DoesNotExist:
                pass
        
        if district_id:
            try:
                application.district = MedDistrict.objects.get(id=district_id)
            except MedDistrict.DoesNotExist:
                pass
        
        application.save()
        return application


class DoctorApplicationUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = DoctorApplication
        fields = ['status', 'rejection_reason']


class MessageSerializer(serializers.ModelSerializer):
    """Сериализатор для сообщений"""
    sender = UserSerializer(read_only=True)
    sender_name = serializers.CharField(source='sender.full_name', read_only=True)
    sender_initials = serializers.CharField(source='sender.initials', read_only=True)
    
    class Meta:
        model = Message
        fields = ['id', 'consultation', 'sender', 'sender_name', 'sender_initials', 'content', 'created_at', 'is_read']
        read_only_fields = ['id', 'sender', 'created_at', 'is_read']


class ConsultationSerializer(serializers.ModelSerializer):
    """Сериализатор для консультаций"""
    patient = UserSerializer(read_only=True)
    doctor = UserSerializer(read_only=True)
    patient_name = serializers.CharField(source='patient.full_name', read_only=True)
    doctor_name = serializers.CharField(source='doctor.full_name', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    messages_count = serializers.SerializerMethodField()
    last_message = serializers.SerializerMethodField()
    can_patient_write = serializers.BooleanField(read_only=True)
    can_doctor_write = serializers.BooleanField(read_only=True)
    
    class Meta:
        model = Consultation
        fields = [
            'id', 'patient', 'doctor', 'patient_name', 'doctor_name', 'status', 'status_display',
            'title', 'description', 'created_at', 'updated_at', 'started_at', 'completed_at',
            'messages_count', 'last_message', 'can_patient_write', 'can_doctor_write'
        ]
        read_only_fields = ['id', 'patient', 'doctor', 'created_at', 'updated_at', 'started_at', 'completed_at']
    
    def get_messages_count(self, obj):
        return obj.messages.count()
    
    def get_last_message(self, obj):
        last_message = obj.messages.last()
        if last_message:
            return {
                'id': last_message.id,
                'content': last_message.content[:100] + '...' if len(last_message.content) > 100 else last_message.content,
                'created_at': last_message.created_at,
                'sender_name': last_message.sender.full_name
            }
        return None


class ConsultationCreateSerializer(serializers.ModelSerializer):
    """Сериализатор для создания консультации"""
    doctor_id = serializers.IntegerField(write_only=True)
    
    class Meta:
        model = Consultation
        fields = ['doctor_id', 'title', 'description']
    
    def validate_doctor_id(self, value):
        try:
            doctor = User.objects.get(id=value, role='doctor')
            return value
        except User.DoesNotExist:
            raise serializers.ValidationError("Врач не найден")
    
    def create(self, validated_data):
        doctor_id = validated_data.pop('doctor_id')
        doctor = User.objects.get(id=doctor_id)
        patient = self.context['request'].user
        
        # Проверяем, что пользователь является пациентом
        if patient.role != 'patient':
            raise serializers.ValidationError("Только пациенты могут создавать консультации")
        
        # Проверяем, что нет активной консультации с этим врачом
        existing_consultation = Consultation.objects.filter(
            patient=patient,
            doctor=doctor,
            status__in=['pending', 'active']
        ).first()
        
        if existing_consultation:
            raise serializers.ValidationError("У вас уже есть активная консультация с этим врачом")
        
        consultation = Consultation.objects.create(
            patient=patient,
            doctor=doctor,
            **validated_data
        )
        return consultation


class ConsultationUpdateSerializer(serializers.ModelSerializer):
    """Сериализатор для обновления консультации"""
    
    class Meta:
        model = Consultation
        fields = ['status', 'title', 'description']
    
    def validate(self, attrs):
        request = self.context.get('request')
        if request and request.user:
            # Только врач может изменять статус консультации
            if 'status' in attrs and request.user.role != 'doctor':
                raise serializers.ValidationError("Только врач может изменять статус консультации")
            
            # При активации консультации устанавливаем started_at
            if attrs.get('status') == 'active' and self.instance.status != 'active':
                attrs['started_at'] = timezone.now()
            
            # При завершении консультации устанавливаем completed_at
            if attrs.get('status') == 'completed' and self.instance.status != 'completed':
                attrs['completed_at'] = timezone.now()
        
        return attrs 

class MedCitySerializer(serializers.ModelSerializer):
    region_name = serializers.CharField(source='region.name', read_only=True)

    class Meta:
        model = MedCity
        fields = ('id', 'name', 'region', 'region_name')


class MedDistrictSerializer(serializers.ModelSerializer):
    city_name = serializers.CharField(source='city.name', read_only=True)

    class Meta:
        model = MedDistrict
        fields = ('id', 'name', 'city', 'city_name')


class FacilityListSerializer(serializers.ModelSerializer):
    city_name = serializers.CharField(source='city.name', read_only=True)
    district_name = serializers.CharField(source='district.name', read_only=True)
    region_name = serializers.CharField(source='city.region.name', read_only=True)
    facility_type_display = serializers.CharField(source='get_facility_type_display', read_only=True)

    class Meta:
        model = MedicalFacility
        fields = (
            'id', 'name', 'name_ru', 'facility_type', 'facility_type_display',
            'ownership_type', 'city', 'city_name', 'district', 'district_name',
            'region_name', 'address', 'phone', 'website', 'working_hours',
            'is_24_hours', 'avg_rating', 'total_reviews', 'total_views',
            'is_verified', 'is_featured', 'specializations', 'has_ambulance',
            'has_pharmacy', 'has_lab', 'accepts_insurance', 'latitude', 'longitude',
        )


class FacilityDetailSerializer(serializers.ModelSerializer):
    city_name = serializers.CharField(source='city.name', read_only=True)
    district_name = serializers.CharField(source='district.name', read_only=True)
    region_name = serializers.CharField(source='city.region.name', read_only=True)
    facility_type_display = serializers.CharField(source='get_facility_type_display', read_only=True)
    photos = serializers.SerializerMethodField()

    class Meta:
        model = MedicalFacility
        fields = '__all__'

    def get_photos(self, obj):
        photos = obj.photos.filter(is_approved=True)
        return [{'id': p.id, 'photo': p.photo.url if p.photo else None, 'caption': p.caption} for p in photos]


class FacilityReviewSerializer(serializers.ModelSerializer):
    user_name = serializers.SerializerMethodField()
    user_avatar = serializers.SerializerMethodField()

    class Meta:
        model = FacilityReview
        fields = (
            'id', 'facility', 'user', 'user_name', 'user_avatar',
            'rating', 'title', 'comment',
            'rating_service', 'rating_cleanliness',
            'rating_equipment', 'rating_price',
            'helpful_count', 'created_at',
        )
        read_only_fields = ('user', 'helpful_count', 'created_at')

    def get_user_name(self, obj):
        return obj.user.get_full_name() or obj.user.email

    def get_user_avatar(self, obj):
        try:
            profile = obj.user.userprofile
            return profile.avatar.url if profile.avatar else None
        except Exception:
            return None

    def validate_rating(self, value):
        if not 1 <= value <= 5:
            raise serializers.ValidationError('Rating must be between 1 and 5.')
        return value

    def validate(self, data):
        request = self.context.get('request')
        if request and FacilityReview.objects.filter(
            user=request.user,
            facility=data['facility']
        ).exists():
            raise serializers.ValidationError(
                'You have already reviewed this facility.'
            )
        return data