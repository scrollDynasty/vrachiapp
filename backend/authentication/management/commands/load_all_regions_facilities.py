from django.core.management.base import BaseCommand
from authentication.models import MedicalFacility, MedCity


class Command(BaseCommand):
    help = 'Load sample medical facilities for all Uzbekistan regions'

    def handle(self, *args, **kwargs):
        facilities_data = [
            # --- SAMARKAND ---
            {
                'city': 'Samarkand',
                'facilities': [
                    {'name': 'Samarkand Regional Multidisciplinary Medical Center', 'name_ru': 'Самаркандский областной многопрофильный медицинский центр', 'facility_type': 'hospital', 'ownership_type': 'public', 'address': 'Central district, Samarkand', 'phone': '+998 66 233-00-00', 'is_24_hours': True, 'has_ambulance': True, 'has_lab': True, 'is_verified': True, 'is_featured': True, 'specializations': ['surgery', 'therapy', 'cardiology']},
                    {'name': 'Samarkand City Hospital No.1', 'name_ru': 'Самаркандская городская больница №1', 'facility_type': 'hospital', 'ownership_type': 'public', 'address': 'Samarkand city center', 'phone': '+998 66 235-00-01', 'is_24_hours': True, 'has_ambulance': True, 'is_verified': True, 'specializations': ['therapy', 'neurology']},
                    {'name': 'Avicenna Clinic Samarkand', 'name_ru': 'Клиника Авиценна Самарканд', 'facility_type': 'clinic', 'ownership_type': 'private', 'address': 'Registan area, Samarkand', 'phone': '+998 66 230-11-11', 'has_lab': True, 'accepts_insurance': True, 'is_verified': True, 'specializations': ['pediatrics', 'gynecology', 'dentistry']},
                    {'name': 'Samarkand Dental Clinic', 'name_ru': 'Самаркандская стоматологическая клиника', 'facility_type': 'dental', 'ownership_type': 'private', 'address': 'Samarkand', 'phone': '+998 66 231-22-22', 'is_verified': True, 'specializations': ['dentistry']},
                ]
            },
            # --- FERGANA ---
            {
                'city': 'Fergana',
                'facilities': [
                    {'name': 'Fergana Regional Medical Center', 'name_ru': 'Ферганский областной медицинский центр', 'facility_type': 'hospital', 'ownership_type': 'public', 'address': 'Central Fergana', 'phone': '+998 73 244-00-00', 'is_24_hours': True, 'has_ambulance': True, 'has_lab': True, 'is_verified': True, 'is_featured': True, 'specializations': ['surgery', 'cardiology', 'neurology']},
                    {'name': 'Fergana City Polyclinic No.1', 'name_ru': 'Ферганская городская поликлиника №1', 'facility_type': 'polyclinic', 'ownership_type': 'public', 'address': 'Fergana city', 'phone': '+998 73 241-00-01', 'is_verified': True, 'specializations': ['therapy', 'pediatrics']},
                    {'name': 'Medplus Fergana', 'name_ru': 'Медплюс Фергана', 'facility_type': 'clinic', 'ownership_type': 'private', 'address': 'Fergana', 'phone': '+998 73 245-33-33', 'has_lab': True, 'accepts_insurance': True, 'is_verified': True, 'specializations': ['gynecology', 'urology', 'dentistry']},
                    {'name': 'Fergana Diagnostic Center', 'name_ru': 'Ферганский диагностический центр', 'facility_type': 'diagnostic', 'ownership_type': 'private', 'address': 'Fergana', 'phone': '+998 73 242-44-44', 'has_lab': True, 'is_verified': True, 'specializations': ['radiology', 'laboratory', 'ultrasound']},
                ]
            },
            # --- ANDIJAN ---
            {
                'city': 'Andijan',
                'facilities': [
                    {'name': 'Andijan Regional Hospital', 'name_ru': 'Андижанская областная больница', 'facility_type': 'hospital', 'ownership_type': 'public', 'address': 'Central Andijan', 'phone': '+998 74 223-00-00', 'is_24_hours': True, 'has_ambulance': True, 'has_lab': True, 'is_verified': True, 'is_featured': True, 'specializations': ['surgery', 'therapy', 'gynecology']},
                    {'name': 'Andijan Medical Center', 'name_ru': 'Андижанский медицинский центр', 'facility_type': 'clinic', 'ownership_type': 'private', 'address': 'Andijan', 'phone': '+998 74 225-11-11', 'has_lab': True, 'is_verified': True, 'specializations': ['cardiology', 'neurology', 'pediatrics']},
                    {'name': 'Andijan Perinatal Center', 'name_ru': 'Андижанский перинатальный центр', 'facility_type': 'maternity', 'ownership_type': 'public', 'address': 'Andijan', 'phone': '+998 74 224-00-05', 'is_24_hours': True, 'is_verified': True, 'specializations': ['gynecology', 'obstetrics']},
                    {'name': 'Smile Dental Andijan', 'name_ru': 'Смайл Дентал Андижан', 'facility_type': 'dental', 'ownership_type': 'private', 'address': 'Andijan', 'phone': '+998 74 226-55-55', 'is_verified': True, 'specializations': ['dentistry']},
                ]
            },
            # --- NAMANGAN ---
            {
                'city': 'Namangan',
                'facilities': [
                    {'name': 'Namangan Regional Hospital', 'name_ru': 'Наманганская областная больница', 'facility_type': 'hospital', 'ownership_type': 'public', 'address': 'Central Namangan', 'phone': '+998 69 234-00-00', 'is_24_hours': True, 'has_ambulance': True, 'has_lab': True, 'is_verified': True, 'is_featured': True, 'specializations': ['surgery', 'therapy', 'cardiology']},
                    {'name': 'Namangan City Polyclinic', 'name_ru': 'Наманганская городская поликлиника', 'facility_type': 'polyclinic', 'ownership_type': 'public', 'address': 'Namangan', 'phone': '+998 69 235-00-01', 'is_verified': True, 'specializations': ['therapy', 'pediatrics']},
                    {'name': 'Shifa Medical Namangan', 'name_ru': 'Медицинский центр Шифа Наманган', 'facility_type': 'clinic', 'ownership_type': 'private', 'address': 'Namangan', 'phone': '+998 69 236-22-22', 'has_lab': True, 'accepts_insurance': True, 'is_verified': True, 'specializations': ['gynecology', 'dentistry', 'urology']},
                ]
            },
            # --- BUKHARA ---
            {
                'city': 'Bukhara',
                'facilities': [
                    {'name': 'Bukhara Regional Multidisciplinary Medical Center', 'name_ru': 'Бухарский областной многопрофильный медицинский центр', 'facility_type': 'hospital', 'ownership_type': 'public', 'address': 'Central Bukhara', 'phone': '+998 65 221-00-00', 'is_24_hours': True, 'has_ambulance': True, 'has_lab': True, 'is_verified': True, 'is_featured': True, 'specializations': ['surgery', 'neurology', 'cardiology']},
                    {'name': 'Bukhara City Hospital', 'name_ru': 'Бухарская городская больница', 'facility_type': 'hospital', 'ownership_type': 'public', 'address': 'Bukhara', 'phone': '+998 65 223-00-01', 'is_24_hours': True, 'has_ambulance': True, 'is_verified': True, 'specializations': ['therapy', 'gynecology']},
                    {'name': 'Bukhara Medical Clinic', 'name_ru': 'Бухарская медицинская клиника', 'facility_type': 'clinic', 'ownership_type': 'private', 'address': 'Bukhara', 'phone': '+998 65 224-33-33', 'has_lab': True, 'is_verified': True, 'specializations': ['pediatrics', 'dentistry']},
                    {'name': 'Bukhara Diagnostic Center', 'name_ru': 'Бухарский диагностический центр', 'facility_type': 'diagnostic', 'ownership_type': 'private', 'address': 'Bukhara', 'phone': '+998 65 225-44-44', 'has_lab': True, 'is_verified': True, 'specializations': ['radiology', 'ultrasound', 'laboratory']},
                ]
            },
            # --- QARSHI (Kashkadarya) ---
            {
                'city': 'Qarshi',
                'facilities': [
                    {'name': 'Kashkadarya Regional Hospital', 'name_ru': 'Кашкадарьинская областная больница', 'facility_type': 'hospital', 'ownership_type': 'public', 'address': 'Central Qarshi', 'phone': '+998 75 221-00-00', 'is_24_hours': True, 'has_ambulance': True, 'has_lab': True, 'is_verified': True, 'is_featured': True, 'specializations': ['surgery', 'therapy', 'cardiology']},
                    {'name': 'Qarshi Medical Center', 'name_ru': 'Каршинский медицинский центр', 'facility_type': 'clinic', 'ownership_type': 'private', 'address': 'Qarshi', 'phone': '+998 75 224-11-11', 'has_lab': True, 'is_verified': True, 'specializations': ['gynecology', 'pediatrics', 'dentistry']},
                ]
            },
            # --- TERMEZ (Surkhandarya) ---
            {
                'city': 'Termez',
                'facilities': [
                    {'name': 'Surkhandarya Regional Hospital', 'name_ru': 'Сурхандарьинская областная больница', 'facility_type': 'hospital', 'ownership_type': 'public', 'address': 'Central Termez', 'phone': '+998 76 223-00-00', 'is_24_hours': True, 'has_ambulance': True, 'has_lab': True, 'is_verified': True, 'is_featured': True, 'specializations': ['surgery', 'therapy', 'neurology']},
                    {'name': 'Termez City Polyclinic', 'name_ru': 'Термезская городская поликлиника', 'facility_type': 'polyclinic', 'ownership_type': 'public', 'address': 'Termez', 'phone': '+998 76 225-00-01', 'is_verified': True, 'specializations': ['therapy', 'pediatrics']},
                    {'name': 'Termez Private Clinic', 'name_ru': 'Частная клиника Термез', 'facility_type': 'clinic', 'ownership_type': 'private', 'address': 'Termez', 'phone': '+998 76 226-22-22', 'has_lab': True, 'is_verified': True, 'specializations': ['dentistry', 'gynecology']},
                ]
            },
            # --- URGANCH (Khorezm) ---
            {
                'city': 'Urganch',
                'facilities': [
                    {'name': 'Khorezm Regional Hospital', 'name_ru': 'Хорезмская областная больница', 'facility_type': 'hospital', 'ownership_type': 'public', 'address': 'Central Urganch', 'phone': '+998 62 224-00-00', 'is_24_hours': True, 'has_ambulance': True, 'has_lab': True, 'is_verified': True, 'is_featured': True, 'specializations': ['surgery', 'cardiology', 'therapy']},
                    {'name': 'Urganch Medical Clinic', 'name_ru': 'Ургенчская медицинская клиника', 'facility_type': 'clinic', 'ownership_type': 'private', 'address': 'Urganch', 'phone': '+998 62 226-11-11', 'has_lab': True, 'is_verified': True, 'specializations': ['gynecology', 'pediatrics', 'dentistry']},
                ]
            },
            # --- NAVOI ---
            {
                'city': 'Navoi',
                'facilities': [
                    {'name': 'Navoi Regional Hospital', 'name_ru': 'Навоийская областная больница', 'facility_type': 'hospital', 'ownership_type': 'public', 'address': 'Central Navoi', 'phone': '+998 79 223-00-00', 'is_24_hours': True, 'has_ambulance': True, 'has_lab': True, 'is_verified': True, 'is_featured': True, 'specializations': ['surgery', 'therapy', 'cardiology']},
                    {'name': 'Navoi Mining Medical Center', 'name_ru': 'Навоийский горнодобывающий медицинский центр', 'facility_type': 'clinic', 'ownership_type': 'private', 'address': 'Navoi', 'phone': '+998 79 224-55-55', 'has_lab': True, 'accepts_insurance': True, 'is_verified': True, 'specializations': ['occupational medicine', 'therapy', 'surgery']},
                ]
            },
            # --- JIZZAKH ---
            {
                'city': 'Jizzakh',
                'facilities': [
                    {'name': 'Jizzakh Regional Hospital', 'name_ru': 'Джизакская областная больница', 'facility_type': 'hospital', 'ownership_type': 'public', 'address': 'Central Jizzakh', 'phone': '+998 72 226-00-00', 'is_24_hours': True, 'has_ambulance': True, 'has_lab': True, 'is_verified': True, 'is_featured': True, 'specializations': ['surgery', 'therapy', 'gynecology']},
                    {'name': 'Jizzakh City Polyclinic', 'name_ru': 'Джизакская городская поликлиника', 'facility_type': 'polyclinic', 'ownership_type': 'public', 'address': 'Jizzakh', 'phone': '+998 72 227-00-01', 'is_verified': True, 'specializations': ['therapy', 'pediatrics']},
                ]
            },
            # --- GULISTON (Syrdarya) ---
            {
                'city': 'Guliston',
                'facilities': [
                    {'name': 'Syrdarya Regional Hospital', 'name_ru': 'Сырдарьинская областная больница', 'facility_type': 'hospital', 'ownership_type': 'public', 'address': 'Central Guliston', 'phone': '+998 67 225-00-00', 'is_24_hours': True, 'has_ambulance': True, 'has_lab': True, 'is_verified': True, 'is_featured': True, 'specializations': ['surgery', 'therapy', 'neurology']},
                    {'name': 'Guliston Medical Clinic', 'name_ru': 'Гулистанская медицинская клиника', 'facility_type': 'clinic', 'ownership_type': 'private', 'address': 'Guliston', 'phone': '+998 67 226-11-11', 'has_lab': True, 'is_verified': True, 'specializations': ['dentistry', 'pediatrics']},
                ]
            },
            # --- NUKUS (Karakalpakstan) ---
            {
                'city': 'Nukus',
                'facilities': [
                    {'name': 'Karakalpakstan Republican Hospital', 'name_ru': 'Республиканская больница Каракалпакстана', 'facility_type': 'hospital', 'ownership_type': 'public', 'address': 'Central Nukus', 'phone': '+998 61 222-00-00', 'is_24_hours': True, 'has_ambulance': True, 'has_lab': True, 'is_verified': True, 'is_featured': True, 'specializations': ['surgery', 'cardiology', 'therapy', 'neurology']},
                    {'name': 'Nukus City Hospital', 'name_ru': 'Нукусская городская больница', 'facility_type': 'hospital', 'ownership_type': 'public', 'address': 'Nukus', 'phone': '+998 61 224-00-01', 'is_24_hours': True, 'has_ambulance': True, 'is_verified': True, 'specializations': ['therapy', 'gynecology']},
                    {'name': 'Nukus Medical Center', 'name_ru': 'Нукусский медицинский центр', 'facility_type': 'clinic', 'ownership_type': 'private', 'address': 'Nukus', 'phone': '+998 61 225-33-33', 'has_lab': True, 'is_verified': True, 'specializations': ['pediatrics', 'dentistry']},
                ]
            },
        ]

        total_created = 0

        for region_data in facilities_data:
            city_name = region_data['city']
            try:
                city = MedCity.objects.get(name=city_name)
            except MedCity.DoesNotExist:
                self.stdout.write(self.style.WARNING(f'  ⚠ City not found: {city_name} — skipping'))
                continue

            for f in region_data['facilities']:
                f['city'] = city
                _, created = MedicalFacility.objects.get_or_create(
                    name=f['name'],
                    defaults=f
                )
                if created:
                    total_created += 1
                    self.stdout.write(f'  ✓ [{city_name}] {f["name"]}')

        self.stdout.write(self.style.SUCCESS(f'\n✅ Done! Created {total_created} facilities across all regions'))
