from django.core.management.base import BaseCommand
from authentication.models import MedicalFacility, MedCity


class Command(BaseCommand):
    help = 'Load sample medical facilities for Tashkent'

    def handle(self, *args, **kwargs):
        try:
            tashkent = MedCity.objects.get(name='Tashkent')
        except MedCity.DoesNotExist:
            self.stdout.write(self.style.ERROR('Tashkent city not found. Run load_uzbekistan_data first.'))
            return

        facilities = [
            {
                'name': 'Republican Specialized Scientific Practical Medical Center',
                'name_ru': 'Республиканский специализированный научно-практический медицинский центр',
                'facility_type': 'hospital',
                'ownership_type': 'public',
                'city': tashkent,
                'address': 'Mirzo Ulugbek district, Tashkent',
                'phone': '+998 71 264-00-00',
                'is_24_hours': True,
                'has_ambulance': True,
                'has_lab': True,
                'is_verified': True,
                'is_featured': True,
                'specializations': ['cardiology', 'neurology', 'surgery'],
            },
            {
                'name': 'Tashkent City Clinical Hospital No.1',
                'name_ru': 'Ташкентская городская клиническая больница №1',
                'facility_type': 'hospital',
                'ownership_type': 'public',
                'city': tashkent,
                'address': 'Chilanzar district, Tashkent',
                'phone': '+998 71 277-00-01',
                'is_24_hours': True,
                'has_ambulance': True,
                'has_lab': True,
                'is_verified': True,
                'specializations': ['surgery', 'therapy', 'gynecology'],
            },
            {
                'name': 'AKFA Medline Clinic',
                'name_ru': 'Клиника АКФА Медлайн',
                'facility_type': 'clinic',
                'ownership_type': 'private',
                'city': tashkent,
                'address': 'Yunusabad district, Tashkent',
                'phone': '+998 71 209-00-09',
                'website': 'https://akfamedline.com',
                'is_24_hours': False,
                'has_lab': True,
                'accepts_insurance': True,
                'is_verified': True,
                'is_featured': True,
                'specializations': ['cardiology', 'dentistry', 'pediatrics'],
            },
            {
                'name': 'Tashkent Dental Center',
                'name_ru': 'Ташкентский стоматологический центр',
                'facility_type': 'dental',
                'ownership_type': 'private',
                'city': tashkent,
                'address': 'Yakkasaray district, Tashkent',
                'phone': '+998 71 150-00-10',
                'is_24_hours': False,
                'is_verified': True,
                'specializations': ['dentistry'],
            },
            {
                'name': 'Central Diagnostic Center Tashkent',
                'name_ru': 'Центральный диагностический центр Ташкент',
                'facility_type': 'diagnostic',
                'ownership_type': 'private',
                'city': tashkent,
                'address': 'Mirabad district, Tashkent',
                'phone': '+998 71 120-44-44',
                'has_lab': True,
                'is_verified': True,
                'specializations': ['radiology', 'laboratory', 'ultrasound'],
            },
            {
                'name': 'Republican Perinatal Center',
                'name_ru': 'Республиканский перинатальный центр',
                'facility_type': 'maternity',
                'ownership_type': 'public',
                'city': tashkent,
                'address': 'Sergeli district, Tashkent',
                'phone': '+998 71 267-00-00',
                'is_24_hours': True,
                'has_ambulance': True,
                'is_verified': True,
                'specializations': ['gynecology', 'obstetrics', 'neonatology'],
            },
            {
                'name': 'Tashkent Children Hospital No.3',
                'name_ru': 'Ташкентская детская больница №3',
                'facility_type': 'children',
                'ownership_type': 'public',
                'city': tashkent,
                'address': 'Shaykhantahur district, Tashkent',
                'phone': '+998 71 241-00-00',
                'is_24_hours': True,
                'has_ambulance': True,
                'is_verified': True,
                'specializations': ['pediatrics', 'surgery'],
            },
            {
                'name': 'Ideal Optika Eye Clinic',
                'name_ru': 'Глазная клиника Идеал Оптика',
                'facility_type': 'eye_clinic',
                'ownership_type': 'private',
                'city': tashkent,
                'address': 'Almazar district, Tashkent',
                'phone': '+998 71 246-00-00',
                'is_verified': True,
                'specializations': ['ophthalmology'],
            },
        ]

        created = 0
        for data in facilities:
            _, was_created = MedicalFacility.objects.get_or_create(
                name=data['name'],
                defaults=data
            )
            if was_created:
                created += 1
                self.stdout.write(f'  ✓ {data["name"]}')

        self.stdout.write(self.style.SUCCESS(f'\n✅ Done! Created {created} facilities in Tashkent'))