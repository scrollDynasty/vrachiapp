from django.core.management.base import BaseCommand
from authentication.models import Region, MedCity, MedDistrict


class Command(BaseCommand):
    help = 'Load Uzbekistan regions, cities and districts'

    def handle(self, *args, **kwargs):
        self.stdout.write('Loading Uzbekistan data...')

        data = {
            'Tashkent City': {
                'Tashkent': ['Yunusabad', 'Mirzo Ulugbek', 'Chilanzar', 'Yakkasaray', 'Shaykhantahur', 'Almazar', 'Bektemir', 'Hamza', 'Mirobod', 'Uchtepa', 'Sergeli', 'Yashnabad'],
            },
            'Tashkent Region': {
                'Chirchiq': ['Bostanliq', 'Zangiota', 'Kibray'],
                'Angren': ['Akhangaran', 'Parkent'],
                'Almaliq': ['Ugam', 'Pskent'],
                'Bekabad': ['Quyichirchiq', 'Yuqorichirchiq'],
                'Nurafshon': ['Oqqorgon', 'Bostanliq district'],
            },
            'Samarkand Region': {
                'Samarkand': ['Urgut', 'Bulungur', 'Jomboy', 'Ishtixon', 'Narpay', 'Nurobod', 'Oqdaryo', 'Pastdargom', 'Payariq', 'Qoshrabot', 'Toyloq'],
                'Kattaqorgon': ['Sardoba', 'Shohruhiya'],
            },
            'Fergana Region': {
                'Fergana': ['Bagdod', 'Beshariq', 'Buvayda', 'Dangara', 'Furqat', 'Oltiariq', 'Rishton', 'Sox', 'Toshloq', 'Uchkoprik', 'Yozyovon'],
                'Margilan': ['Koson', 'Kuva'],
                'Qoqon': ['Qoqon district'],
                'Quvasoy': ['Quva'],
            },
            'Andijan Region': {
                'Andijan': ['Altinkol', 'Baliqchi', 'Buloqboshi', 'Jalaquduq', 'Izboskan', 'Kongil', 'Xojaobod', 'Marhamat', 'Paxtaobod', 'Qorgontepa', 'Shahrixon', 'Ulugnor'],
                'Asaka': ['Asaka district'],
            },
            'Namangan Region': {
                'Namangan': ['Chortoq', 'Chust', 'Kosonsoy', 'Mingbuloq', 'Namangan district', 'Norin', 'Pop', 'Toraqorgon', 'Uchqorgon', 'Yangiqorgon'],
                'Chortoq': ['Chortoq city district'],
                'Chust': ['Chust city district'],
            },
            'Bukhara Region': {
                'Bukhara': ['Alat', 'Gijduvon', 'Jondor', 'Kogon', 'Qorovulbozor', 'Romitan', 'Shofirkon', 'Vobkent', 'Peshku', 'Olot'],
                'Kagan': ['Kagan district'],
            },
            'Kashkadarya Region': {
                'Qarshi': ['Chiroqchi', 'Dehqonobod', 'Guzor', 'Kasbi', 'Kitob', 'Koson district', 'Mirishkor', 'Muborak', 'Nishon', 'Qamashi', 'Qarshi district'],
                'Shahrisabz': ['Shahrisabz district', 'Yakkabog', 'Kitob district'],
            },
            'Surkhandarya Region': {
                'Termez': ['Angor', 'Bandixon', 'Boysun', 'Jarqorgon', 'Muzrabot', 'Oltinsoy', 'Qiziriq', 'Qomqorgon', 'Sariosiyo', 'Sherobod', 'Shorchi', 'Termez district', 'Uzun'],
                'Denov': ['Denov district'],
            },
            'Khorezm Region': {
                'Urganch': ['Bogot', 'Gurlan', 'Xonqa', 'Qoshkopir', 'Shovot', 'Tuproqqala', 'Urganch district', 'Yangiariq', 'Yangibozor'],
                'Xiva': ['Xiva district'],
            },
            'Navoi Region': {
                'Navoi': ['Karmana', 'Konimex', 'Navbahor', 'Nurota', 'Qiziltepa', 'Tomdi', 'Xatirchi'],
                'Zarafshon': ['Zarafshon district'],
                'Uchquduq': ['Uchquduq district'],
            },
            'Jizzakh Region': {
                'Jizzakh': ['Arnasoy', 'Baxmal', 'Dostlik', 'Forish', 'Gallaorol', 'Jizzakh district', 'Mirzachol', 'Paxtakor', 'Sharof Rashidov', 'Yangiobod', 'Zafarobod', 'Zomin'],
                'Gagarin': ['Gagarin district'],
            },
            'Syrdarya Region': {
                'Guliston': ['Boyovut', 'Guliston district', 'Havast', 'Mirzaobod', 'Oqoltin', 'Sardoba district', 'Sayxunobod', 'Shirin', 'Sirdaryo'],
                'Yangiyer': ['Yangiyer district'],
            },
            'Karakalpakstan': {
                'Nukus': ['Amudaryo', 'Beruniy', 'Chimboy', 'Ellikqala', 'Kegeyli', 'Qanlikol', 'Qongrot', 'Moynoq', 'Nukus district', 'Shumanay', 'Taxtakopir', 'Tortkol', 'Xojayli'],
                'Moynoq': ['Moynoq district'],
            },
        }

        total_regions = 0
        total_cities = 0
        total_districts = 0

        for region_name, cities in data.items():
            region, created = Region.objects.get_or_create(name=region_name)
            if created:
                total_regions += 1
                self.stdout.write(f'  ✓ Region: {region_name}')

            for city_name, districts in cities.items():
                city, created = MedCity.objects.get_or_create(
                    name=city_name,
                    region=region
                )
                if created:
                    total_cities += 1

                for district_name in districts:
                    _, created = MedDistrict.objects.get_or_create(
                        name=district_name,
                        city=city,
                        defaults={'region': region}
                    )
                    if created:
                        total_districts += 1

        self.stdout.write(self.style.SUCCESS(
            f'\n✅ Done! Created: {total_regions} regions, {total_cities} cities, {total_districts} districts'
        ))