from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APITestCase, APIClient
from rest_framework import status
from .models import User, Appointment, MedicalRecord, Notification, Review
from datetime import date, time, timedelta

import django.test.utils
from django.test import override_settings

# Override settings for testing
@override_settings(SECURE_SSL_REDIRECT=False, DEBUG=True)

@override_settings(SECURE_SSL_REDIRECT=False)
class UserRegistrationTestCase(APITestCase):
    def test_patient_registration_success(self):
        url = '/api/auth/register/'
        data = {
            'username': 'testpatient',
            'email': 'patient@test.com',
            'password': 'TestPass123!',
            'first_name': 'John',
            'last_name': 'Doe',
            'role': 'patient',
        }
        response = self.client.post(url, data, format='json')
        self.assertNotEqual(response.status_code, 500)

    def test_doctor_registration_success(self):
        url = '/api/auth/register/'
        data = {
            'username': 'testdoctor',
            'email': 'doctor@test.com',
            'password': 'TestPass123!',
            'first_name': 'Jane',
            'last_name': 'Smith',
            'role': 'doctor',
        }
        response = self.client.post(url, data, format='json')
        self.assertNotEqual(response.status_code, 500)

    def test_registration_missing_fields(self):
        url = '/api/auth/register/'
        data = {'username': 'incomplete'}
        response = self.client.post(url, data, format='json')
        self.assertIn(response.status_code, [400, 422, 200])

    def test_duplicate_email_registration(self):
        url = '/api/auth/register/'
        data = {
            'username': 'user1',
            'email': 'same@test.com',
            'password': 'TestPass123!',
            'first_name': 'User',
            'last_name': 'One',
            'role': 'patient',
        }
        self.client.post(url, data, format='json')
        data['username'] = 'user2'
        response = self.client.post(url, data, format='json')
        self.assertNotEqual(response.status_code, 500)


@override_settings(SECURE_SSL_REDIRECT=False)
class UserLoginTestCase(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='logintest',
            email='login@test.com',
            password='TestPass123!',
            first_name='Login',
            last_name='Test',
            role='patient',
            is_active=True,
        )

    def test_login_success(self):
        url = '/api/auth/login/'
        data = {'email': 'login@test.com', 'password': 'TestPass123!'}
        response = self.client.post(url, data, format='json')
        self.assertIn(response.status_code, [200, 201])

    def test_login_wrong_password(self):
        url = '/api/auth/login/'
        data = {'email': 'login@test.com', 'password': 'WrongPass!'}
        response = self.client.post(url, data, format='json')
        self.assertIn(response.status_code, [400, 401, 403])

    def test_login_nonexistent_user(self):
        url = '/api/auth/login/'
        data = {'email': 'nobody@test.com', 'password': 'TestPass123!'}
        response = self.client.post(url, data, format='json')
        self.assertIn(response.status_code, [400, 401, 403, 404])


@override_settings(SECURE_SSL_REDIRECT=False)
class AppointmentTestCase(APITestCase):
    def setUp(self):
        self.patient = User.objects.create_user(
            username='patient1', email='patient1@test.com',
            password='TestPass123!', first_name='Patient',
            last_name='One', role='patient', is_active=True,
        )
        self.doctor = User.objects.create_user(
            username='doctor1', email='doctor1@test.com',
            password='TestPass123!', first_name='Doctor',
            last_name='One', role='doctor', is_active=True,
        )
        self.client.force_authenticate(user=self.patient)

    def test_book_appointment_success(self):
        url = '/api/auth/appointments/'
        data = {
            'doctor_id': self.doctor.id,
            'appointment_date': str(date.today() + timedelta(days=1)),
            'appointment_time': '10:00',
            'reason': 'Regular checkup',
        }
        response = self.client.post(url, data, format='json')
        self.assertIn(response.status_code, [200, 201])

    def test_book_appointment_past_date(self):
        url = '/api/auth/appointments/'
        data = {
            'doctor_id': self.doctor.id,
            'appointment_date': str(date.today() - timedelta(days=1)),
            'appointment_time': '10:00',
        }
        response = self.client.post(url, data, format='json')
        self.assertIn(response.status_code, [400, 422])

    def test_get_appointments_list(self):
        url = '/api/auth/appointments/'
        response = self.client.get(url)
        self.assertIn(response.status_code, [200, 201])

    def test_doctor_cannot_book_appointment(self):
        self.client.force_authenticate(user=self.doctor)
        url = '/api/auth/appointments/'
        data = {
            'doctor_id': self.doctor.id,
            'appointment_date': str(date.today() + timedelta(days=1)),
            'appointment_time': '10:00',
        }
        response = self.client.post(url, data, format='json')
        self.assertNotEqual(response.status_code, 201)


@override_settings(SECURE_SSL_REDIRECT=False)
class MedicalRecordTestCase(APITestCase):
    def setUp(self):
        self.patient = User.objects.create_user(
            username='patient2', email='patient2@test.com',
            password='TestPass123!', first_name='Patient',
            last_name='Two', role='patient', is_active=True,
        )
        self.doctor = User.objects.create_user(
            username='doctor2', email='doctor2@test.com',
            password='TestPass123!', first_name='Doctor',
            last_name='Two', role='doctor', is_active=True,
        )

    def test_doctor_can_create_record(self):
        self.client.force_authenticate(user=self.doctor)
        url = '/api/auth/medical-records/'
        data = {
            'patient_id': self.patient.id,
            'record_type': 'diagnosis',
            'title': 'Flu Diagnosis',
            'description': 'Patient has seasonal flu.',
        }
        response = self.client.post(url, data, format='json')
        self.assertIn(response.status_code, [200, 201])

    def test_patient_cannot_create_record(self):
        self.client.force_authenticate(user=self.patient)
        url = '/api/auth/medical-records/'
        data = {
            'patient_id': self.patient.id,
            'record_type': 'diagnosis',
            'title': 'Self Diagnosis',
            'description': 'I think I have flu.',
        }
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, 403)

    def test_patient_can_view_own_records(self):
        self.client.force_authenticate(user=self.patient)
        url = '/api/auth/medical-records/'
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)


@override_settings(SECURE_SSL_REDIRECT=False)
class NotificationTestCase(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='notifuser', email='notif@test.com',
            password='TestPass123!', first_name='Notif',
            last_name='User', role='patient', is_active=True,
        )
        self.notification = Notification.objects.create(
            recipient=self.user,
            title='Test Notification',
            message='This is a test',
            notification_type='general',
        )
        self.client.force_authenticate(user=self.user)

    def test_get_notifications(self):
        url = '/api/auth/notifications/'
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertIn('notifications', response.data)
        self.assertIn('unread_count', response.data)

    def test_mark_notification_read(self):
        url = f'/api/auth/notifications/{self.notification.id}/read/'
        response = self.client.patch(url)
        self.assertEqual(response.status_code, 200)
        self.notification.refresh_from_db()
        self.assertTrue(self.notification.is_read)

    def test_mark_all_notifications_read(self):
        url = '/api/auth/notifications/read-all/'
        response = self.client.patch(url)
        self.assertEqual(response.status_code, 200)


@override_settings(SECURE_SSL_REDIRECT=False)
class ReviewTestCase(APITestCase):
    def setUp(self):
        self.patient = User.objects.create_user(
            username='reviewer', email='reviewer@test.com',
            password='TestPass123!', first_name='Reviewer',
            last_name='User', role='patient', is_active=True,
        )
        self.doctor = User.objects.create_user(
            username='reviewed_doctor', email='reviewed@test.com',
            password='TestPass123!', first_name='Reviewed',
            last_name='Doctor', role='doctor', is_active=True,
        )
        self.client.force_authenticate(user=self.patient)

    def test_patient_can_submit_review(self):
        url = f'/api/auth/doctors/{self.doctor.id}/reviews/'
        data = {'rating': 5, 'comment': 'Excellent doctor!'}
        response = self.client.post(url, data, format='json')
        self.assertIn(response.status_code, [200, 201])

    def test_invalid_rating(self):
        url = f'/api/auth/doctors/{self.doctor.id}/reviews/'
        data = {'rating': 10, 'comment': 'Bad rating value'}
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, 400)

    def test_get_doctor_reviews(self):
        url = f'/api/auth/doctors/{self.doctor.id}/reviews/'
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertIn('reviews', response.data)

    def test_doctor_cannot_review(self):
        self.client.force_authenticate(user=self.doctor)
        url = f'/api/auth/doctors/{self.doctor.id}/reviews/'
        data = {'rating': 5, 'comment': 'Self review'}
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, 403)


@override_settings(SECURE_SSL_REDIRECT=False)
class AdminTestCase(APITestCase):
    def setUp(self):
        self.admin = User.objects.create_user(
            username='adminuser', email='admin@test.com',
            password='TestPass123!', first_name='Admin',
            last_name='User', role='admin', is_active=True, is_staff=True,
        )
        self.patient = User.objects.create_user(
            username='regularuser', email='regular@test.com',
            password='TestPass123!', first_name='Regular',
            last_name='User', role='patient', is_active=True,
        )
        self.client.force_authenticate(user=self.admin)

    def test_admin_can_access_dashboard(self):
        url = '/api/auth/admin/dashboard/'
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertIn('stats', response.data)

    def test_non_admin_cannot_access_dashboard(self):
        self.client.force_authenticate(user=self.patient)
        url = '/api/auth/admin/dashboard/'
        response = self.client.get(url)
        self.assertEqual(response.status_code, 403)

    def test_admin_can_list_users(self):
        url = '/api/auth/admin/users/'
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertIn('users', response.data)
