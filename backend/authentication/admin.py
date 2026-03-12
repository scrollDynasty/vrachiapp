from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import (
    User, UserProfile, Region,
    DoctorApplication, Consultation, Message,
    AIDialogue, AIMessage,
    MedCity, MedDistrict,
    MedicalFacility, FacilityReview, FacilityPhoto,
)


@admin.register(User)
class CustomUserAdmin(UserAdmin):
    list_display = ['email', 'username', 'first_name', 'last_name', 'is_staff', 'is_verified', 'google_id']
    list_filter = ['is_staff', 'is_superuser', 'is_active', 'is_verified', 'date_joined']
    search_fields = ['email', 'username', 'first_name', 'last_name']
    ordering = ['-date_joined']
    
    fieldsets = UserAdmin.fieldsets + (
        ('Дополнительная информация', {
            'fields': ('phone', 'avatar', 'google_id', 'is_verified')
        }),
    )
    
    add_fieldsets = UserAdmin.add_fieldsets + (
        ('Дополнительная информация', {
            'fields': ('phone', 'avatar', 'google_id', 'is_verified')
        }),
    )


@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ['user', 'gender', 'date_of_birth', 'emergency_contact']
    list_filter = ['gender', 'date_of_birth']
    search_fields = ['user__email', 'user__first_name', 'user__last_name']
    raw_id_fields = ['user']


@admin.register(Region)
class RegionAdmin(admin.ModelAdmin):
    list_display = ['name', 'type']
    list_filter = ['type']
    search_fields = ['name']


@admin.register(MedCity)
class MedCityAdmin(admin.ModelAdmin):
    list_display = ("name", "region")
    search_fields = ("name",)
    list_filter = ("region",)


@admin.register(MedDistrict)
class MedDistrictAdmin(admin.ModelAdmin):
    list_display = ("name", "city", "region")
    search_fields = ("name",)
    list_filter = ("region", "city")


@admin.register(DoctorApplication)
class DoctorApplicationAdmin(admin.ModelAdmin):
    list_display = ['user', 'specialization', 'status', 'created_at']
    list_filter = ['status', 'specialization', 'created_at']
    search_fields = ['user__email', 'user__first_name', 'user__last_name', 'specialization']
    raw_id_fields = ['user']


@admin.register(Consultation)
class ConsultationAdmin(admin.ModelAdmin):
    list_display = ['id', 'patient', 'doctor', 'status', 'created_at']
    list_filter = ['status', 'created_at']
    search_fields = ['patient__email', 'doctor__email']
    raw_id_fields = ['patient', 'doctor']


@admin.register(Message)
class MessageAdmin(admin.ModelAdmin):
    list_display = ('consultation', 'sender', 'content_preview', 'created_at', 'is_read')
    list_filter = ('created_at', 'is_read')
    search_fields = ('content', 'sender__email')
    raw_id_fields = ('consultation', 'sender')
    readonly_fields = ('created_at', 'read_at')
    
    def content_preview(self, obj):
        return obj.content[:50] + '...' if len(obj.content) > 50 else obj.content
    content_preview.short_description = 'Содержание'


@admin.register(AIDialogue)
class AIDialogueAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'title', 'created_at', 'updated_at', 'is_active')
    list_filter = ('created_at', 'updated_at', 'is_active')
    search_fields = ('title', 'user__email', 'user__first_name', 'user__last_name')
    raw_id_fields = ('user',)
    readonly_fields = ('created_at', 'updated_at')


@admin.register(AIMessage)
class AIMessageAdmin(admin.ModelAdmin):
    list_display = ('id', 'dialogue', 'sender_type', 'message_type', 'content_preview', 'timestamp')
    list_filter = ('sender_type', 'message_type', 'timestamp')
    search_fields = ('content', 'dialogue__title')
    raw_id_fields = ('dialogue',)
    readonly_fields = ('timestamp',)
    
    def content_preview(self, obj):
        return obj.content[:50] + '...' if len(obj.content) > 50 else obj.content
    content_preview.short_description = 'Содержание' 

@admin.register(MedicalFacility)
class MedicalFacilityAdmin(admin.ModelAdmin):
    list_display = ('name', 'facility_type', 'ownership_type', 'city', 'avg_rating', 'total_reviews', 'is_verified', 'is_active', 'is_featured')
    list_filter = ('facility_type', 'ownership_type', 'city__region', 'city', 'is_verified', 'is_active', 'is_featured', 'is_24_hours')
    search_fields = ('name', 'name_ru', 'address', 'phone')
    readonly_fields = ('avg_rating', 'total_reviews', 'total_views', 'created_at', 'updated_at')
    list_editable = ('is_verified', 'is_active', 'is_featured')
    raw_id_fields = ('city', 'district', 'added_by')


@admin.register(FacilityReview)
class FacilityReviewAdmin(admin.ModelAdmin):
    list_display = ('facility', 'user', 'rating', 'created_at')
    list_filter = ('rating', 'created_at')
    search_fields = ('facility__name', 'user__email')
    readonly_fields = ('created_at',)


@admin.register(FacilityPhoto)
class FacilityPhotoAdmin(admin.ModelAdmin):
    list_display = ('facility', 'uploaded_by', 'is_approved', 'created_at')
    list_filter = ('is_approved',)
    list_editable = ('is_approved',)