import time
import requests
from django.core.management.base import BaseCommand
from authentication.models import MedicalFacility
import os


class Command(BaseCommand):
    help = 'Geocode facilities using Google Maps API'

    def add_arguments(self, parser):
        parser.add_argument('--all', action='store_true', help='Re-geocode all facilities, not just missing ones')

    def handle(self, *args, **options):
        api_key = os.getenv('GOOGLE_MAPS_API_KEY')
        if not api_key:
            self.stdout.write('ERROR: GOOGLE_MAPS_API_KEY not found in .env')
            return

        if options['all']:
            facilities = MedicalFacility.objects.filter(is_active=True)
        else:
            facilities = MedicalFacility.objects.filter(
                is_active=True, latitude__isnull=True
            )

        self.stdout.write(f'Geocoding {facilities.count()} facilities...')
        success = 0
        failed = 0

        for facility in facilities:
            query = f"{facility.address}, {facility.city.name if facility.city else ''}, Uzbekistan"

            try:
                response = requests.get(
                    'https://maps.googleapis.com/maps/api/geocode/json',
                    params={'address': query, 'key': api_key},
                    timeout=10
                )
                data = response.json()

                if data['status'] == 'OK':
                    loc = data['results'][0]['geometry']['location']
                    facility.latitude = loc['lat']
                    facility.longitude = loc['lng']
                    facility.save(update_fields=['latitude', 'longitude'])
                    success += 1
                    self.stdout.write(f'  ✓ {facility.name}: {facility.latitude}, {facility.longitude}')
                else:
                    failed += 1
                    self.stdout.write(f'  ✗ {facility.name}: {data["status"]}')

                time.sleep(0.1)

            except Exception as e:
                failed += 1
                self.stdout.write(f'  ✗ {facility.name}: {e}')

        self.stdout.write(f'\nDone! ✓ {success} geocoded, ✗ {failed} failed')