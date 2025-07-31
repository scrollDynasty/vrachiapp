from rest_framework import serializers
from django.contrib.auth import authenticate
from django.contrib.auth.password_validation import validate_password
from .models import User, UserProfile, Region, City, District


class UserSerializer(serializers.ModelSerializer):
    """Сериализатор для пользователя"""
    full_name = serializers.ReadOnlyField()
    initials = serializers.ReadOnlyField()
    
    class Meta:
        model = User
        fields = ['id', 'email', 'username', 'first_name', 'last_name', 
                 'full_name', 'initials', 'avatar', 'phone', 'is_verified', 
                 'date_joined', 'last_login']
        read_only_fields = ['id', 'is_verified', 'date_joined', 'last_login']


class RegionSerializer(serializers.ModelSerializer):
    """Сериализатор для регионов"""
    class Meta:
        model = Region
        fields = ['id', 'name', 'name_uz']


class CitySerializer(serializers.ModelSerializer):
    """Сериализатор для городов"""
    region = RegionSerializer(read_only=True)
    
    class Meta:
        model = City
        fields = ['id', 'name', 'name_uz', 'region']


class DistrictSerializer(serializers.ModelSerializer):
    """Сериализатор для районов"""
    region = RegionSerializer(read_only=True)
    
    class Meta:
        model = District
        fields = ['id', 'name', 'name_uz', 'region']


class UserProfileSerializer(serializers.ModelSerializer):
    """Сериализатор для профиля пользователя"""
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
            'region', 'city', 'district', 'address', 'medical_info', 
            'emergency_contact', 'created_at', 'updated_at'
        ]


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
                raise serializers.ValidationError('Аккаунт заблокирован')
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