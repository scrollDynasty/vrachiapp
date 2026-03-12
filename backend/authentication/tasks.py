from celery import shared_task
from django.utils import timezone
from datetime import timedelta


@shared_task
def send_appointment_reminders():
    """Send reminders for appointments in the next 24 hours and 1 hour"""
    from django.contrib.auth import get_user_model
    from .models import Appointment, Notification

    now = timezone.now()
    reminders_sent = 0

    # 24 hour reminders
    window_24h_start = now + timedelta(hours=23, minutes=30)
    window_24h_end = now + timedelta(hours=24, minutes=30)

    # 1 hour reminders
    window_1h_start = now + timedelta(minutes=45)
    window_1h_end = now + timedelta(hours=1, minutes=15)

    upcoming_24h = Appointment.objects.filter(
        appointment_date__range=(window_24h_start, window_24h_end),
        status='confirmed'
    ).select_related('patient', 'doctor')

    upcoming_1h = Appointment.objects.filter(
        appointment_date__range=(window_1h_start, window_1h_end),
        status='confirmed'
    ).select_related('patient', 'doctor')

    for appointment in upcoming_24h:
        already_sent = Notification.objects.filter(
            user=appointment.patient,
            notification_type='appointment_reminder',
            related_id=appointment.id,
            message__icontains='24'
        ).exists()

        if not already_sent:
            Notification.objects.create(
                user=appointment.patient,
                title='Appointment Reminder - 24 Hours',
                message=f'You have an appointment with Dr. {appointment.doctor.get_full_name()} tomorrow at {appointment.appointment_date.strftime("%H:%M")}.',
                notification_type='appointment_reminder',
                related_id=appointment.id,
            )
            reminders_sent += 1

    for appointment in upcoming_1h:
        already_sent = Notification.objects.filter(
            user=appointment.patient,
            notification_type='appointment_reminder',
            related_id=appointment.id,
            message__icontains='1 hour'
        ).exists()

        if not already_sent:
            Notification.objects.create(
                user=appointment.patient,
                title='Appointment Reminder - 1 Hour',
                message=f'Your appointment with Dr. {appointment.doctor.get_full_name()} starts in 1 hour at {appointment.appointment_date.strftime("%H:%M")}.',
                notification_type='appointment_reminder',
                related_id=appointment.id,
            )
            reminders_sent += 1

    return f'Sent {reminders_sent} reminders'


@shared_task
def cleanup_old_notifications():
    """Delete notifications older than 30 days"""
    from .models import Notification
    cutoff = timezone.now() - timedelta(days=30)
    deleted, _ = Notification.objects.filter(
        created_at__lt=cutoff,
        is_read=True
    ).delete()
    return f'Deleted {deleted} old notifications'

@shared_task
def generate_consultation_summary(consultation_id):
    """Auto-generate AI summary when consultation is completed"""
    import anthropic
    import os
    import json
    import re

    try:
        from .models import Consultation, Message
        consultation = Consultation.objects.get(id=consultation_id)

        messages = Message.objects.filter(
            consultation=consultation
        ).select_related('sender').order_by('created_at')

        if not messages.exists():
            return 'No messages — skipped'

        chat_text = '\n'.join([
            f"{msg.sender.full_name} ({'Doctor' if msg.sender.role == 'doctor' else 'Patient'}): {msg.content}"
            for msg in messages
        ])

        api_key = os.getenv('ANTHROPIC_API_KEY')
        client = anthropic.Anthropic(api_key=api_key)

        prompt = f"""Summarize this doctor-patient consultation.

Patient: {consultation.patient.full_name}
Doctor: {consultation.doctor.full_name}
Date: {consultation.created_at.strftime('%Y-%m-%d')}

Transcript:
{chat_text}

Return ONLY a JSON object:
{{
  "chief_complaint": "Main reason for consultation",
  "symptoms_discussed": ["symptom 1", "symptom 2"],
  "doctor_assessment": "Doctor's assessment",
  "treatment_plan": ["treatment 1"],
  "medications_prescribed": ["med 1"],
  "follow_up": "Follow up instructions",
  "summary": "2-3 sentence summary",
  "urgency_flags": ["any urgent concerns"]
}}"""

        message = client.messages.create(
            model='claude-haiku-4-5',
            max_tokens=1500,
            messages=[{'role': 'user', 'content': prompt}]
        )

        text = message.content[0].text.strip()
        json_match = re.search(r'\{.*\}', text, re.DOTALL)
        if json_match:
            consultation.ai_summary = json_match.group()
            consultation.save(update_fields=['ai_summary'])
            return f'Summary generated for consultation {consultation_id}'
        return 'Could not parse AI response'

    except Exception as e:
        return f'Error: {str(e)}'