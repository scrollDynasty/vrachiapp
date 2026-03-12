import json
import logging
import os
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from django.contrib.auth import get_user_model
from django.utils import timezone
from .models import Consultation, Message

logger = logging.getLogger(__name__)
User = get_user_model()

try:
    import redis.asyncio as aioredis
except Exception:
    aioredis = None

RATE_LIMIT_MSGS_PER_MINUTE = int(os.getenv("CHAT_RATE_LIMIT_PER_MIN", "60"))
ONLINE_TTL = 60  # seconds before presence expires


class ChatConsumer(AsyncWebsocketConsumer):

    async def connect(self):
        print("WEBSOCKET CONNECT ATTEMPT")
        try:
            self.consultation_id = self.scope["url_route"]["kwargs"]["room_id"]
            self.room_group_name = f"chat_{self.consultation_id}"

            logger.info(f"WebSocket connect attempt for consultation {self.consultation_id}")

            if not self.scope["user"].is_authenticated:
                logger.warning("Unauthenticated websocket attempt")
                await self.close(code=4001)
                return

            access = await self.can_access_consultation()
            if not access:
                logger.warning(f"User {self.scope['user'].id} denied access")
                await self.close(code=4003)
                return

            await self.channel_layer.group_add(self.room_group_name, self.channel_name)
            await self.accept()

            # Mark online + broadcast presence
            await self.set_online(True)
            await self.channel_layer.group_send(self.room_group_name, {
                "type": "presence_update",
                "user_id": self.scope["user"].id,
                "user_name": self.scope["user"].full_name,
                "is_online": True,
            })

            await self.send(text_data=json.dumps({
                "type": "connection_established",
                "consultation_id": self.consultation_id
            }))

        except Exception as e:
            logger.error(f"Connect error: {e}")
            await self.close()

    async def disconnect(self, close_code):
        try:
            await self.set_online(False)
            await self.channel_layer.group_send(self.room_group_name, {
                "type": "presence_update",
                "user_id": self.scope["user"].id,
                "user_name": self.scope["user"].full_name,
                "is_online": False,
            })
        except Exception:
            pass

        await self.channel_layer.group_discard(self.room_group_name, self.channel_name)

    async def receive(self, text_data):
        try:
            data = json.loads(text_data)
            message_type = data.get("type", "chat_message")

            # ── Ping ──────────────────────────────────────────────
            if message_type == "ping":
                await self.set_online(True)  # refresh TTL
                await self.send(json.dumps({
                    "type": "pong",
                    "timestamp": timezone.now().isoformat()
                }))
                return

            # ── Typing indicator ──────────────────────────────────
            if message_type == "typing":
                await self.channel_layer.group_send(self.room_group_name, {
                    "type": "typing_indicator",
                    "user_id": self.scope["user"].id,
                    "user_name": self.scope["user"].full_name,
                    "is_typing": data.get("is_typing", False),
                })
                return

            # ── Read receipt ──────────────────────────────────────
            if message_type == "read":
                message_id = data.get("message_id")
                if message_id:
                    success = await self.mark_message_read(message_id)
                    if success:
                        await self.channel_layer.group_send(self.room_group_name, {
                            "type": "message_read",
                            "message_id": message_id,
                            "read_by": self.scope["user"].id,
                            "read_by_name": self.scope["user"].full_name,
                            "read_at": timezone.now().isoformat(),
                        })
                return

            # ── Chat message ──────────────────────────────────────
            if message_type == "chat_message":
                message_content = data.get("message", "").strip()

                if not message_content:
                    await self.send(json.dumps({"type": "error", "message": "Empty message"}))
                    return

                sender_id = self.scope["user"].id

                # Redis rate limit
                if aioredis:
                    try:
                        redis = aioredis.from_url(
                            f"redis://{os.getenv('REDIS_HOST','127.0.0.1')}:{os.getenv('REDIS_PORT','6379')}"
                        )
                        key = f"chat_rate:{self.consultation_id}:{sender_id}"
                        count = await redis.incr(key)
                        if count == 1:
                            await redis.expire(key, 60)
                        if count > RATE_LIMIT_MSGS_PER_MINUTE:
                            await self.send(json.dumps({"type": "error", "message": "Too many messages"}))
                            return
                    except Exception as e:
                        logger.warning(f"Redis rate limit error: {e}")

                saved_message = await self.save_message(message_content, sender_id)

                if not saved_message:
                    await self.send(json.dumps({"type": "error", "message": "Cannot send message"}))
                    return

                await self.channel_layer.group_send(self.room_group_name, {
                    "type": "chat_message",
                    "message": message_content,
                    "sender_id": sender_id,
                    "sender_name": self.scope["user"].full_name,
                    "sender_initials": self.scope["user"].initials,
                    "timestamp": saved_message.created_at.isoformat(),
                    "message_id": saved_message.id,
                    "status": "delivered",
                })

        except Exception as e:
            logger.error(f"Receive error: {e}")

    # ── Group event handlers ───────────────────────────────────────

    async def chat_message(self, event):
        await self.send(text_data=json.dumps({
            "type": "chat_message",
            "message": event["message"],
            "sender_id": event["sender_id"],
            "sender_name": event["sender_name"],
            "sender_initials": event["sender_initials"],
            "timestamp": event["timestamp"],
            "message_id": event["message_id"],
            "status": event.get("status", "delivered"),
        }))

    async def typing_indicator(self, event):
        if event["user_id"] != self.scope["user"].id:
            await self.send(json.dumps({
                "type": "typing",
                "user_id": event["user_id"],
                "user_name": event["user_name"],
                "is_typing": event["is_typing"],
            }))

    async def message_read(self, event):
        await self.send(json.dumps({
            "type": "read",
            "message_id": event["message_id"],
            "read_by": event["read_by"],
            "read_by_name": event["read_by_name"],
            "read_at": event["read_at"],
        }))

    async def presence_update(self, event):
        if event["user_id"] != self.scope["user"].id:
            await self.send(json.dumps({
                "type": "presence",
                "user_id": event["user_id"],
                "user_name": event["user_name"],
                "is_online": event["is_online"],
            }))

    # ── Helpers ────────────────────────────────────────────────────

    async def set_online(self, is_online: bool):
        if not aioredis:
            return
        try:
            redis = aioredis.from_url(
                f"redis://{os.getenv('REDIS_HOST','127.0.0.1')}:{os.getenv('REDIS_PORT','6379')}"
            )
            key = f"online:{self.scope['user'].id}"
            if is_online:
                await redis.setex(key, ONLINE_TTL, "1")
            else:
                await redis.delete(key)
        except Exception as e:
            logger.warning(f"Redis presence error: {e}")

    # ── Database methods ───────────────────────────────────────────

    @database_sync_to_async
    def can_access_consultation(self):
        try:
            consultation = Consultation.objects.get(id=self.consultation_id)
            user = self.scope["user"]
            return user == consultation.patient or user == consultation.doctor
        except Consultation.DoesNotExist:
            return False

    @database_sync_to_async
    def save_message(self, content, sender_id):
        try:
            consultation = Consultation.objects.get(id=self.consultation_id)
            sender = User.objects.get(id=sender_id)
            if sender == consultation.patient and not consultation.can_patient_write:
                return None
            if sender == consultation.doctor and not consultation.can_doctor_write:
                return None
            return Message.objects.create(
                consultation=consultation,
                sender=sender,
                content=content
            )
        except Exception as e:
            logger.error(f"Save message error: {e}")
            return None

    @database_sync_to_async
    def mark_message_read(self, message_id):
        try:
            message = Message.objects.get(id=message_id, consultation_id=self.consultation_id)
            if message.sender_id == self.scope["user"].id:
                return False  # can't read your own message
            if not message.is_read:
                message.is_read = True
                message.read_at = timezone.now()
                message.save(update_fields=["is_read", "read_at"])
            return True
        except Message.DoesNotExist:
            return False
        except Exception as e:
            logger.error(f"Mark read error: {e}")
            return False


class NotificationConsumer(AsyncWebsocketConsumer):

    async def connect(self):
        if not self.scope["user"].is_authenticated:
            await self.close()
            return

        self.user_id = self.scope["user"].id
        self.user_group_name = f"user_{self.user_id}"

        await self.channel_layer.group_add(self.user_group_name, self.channel_name)
        await self.accept()

        await self.send(json.dumps({"type": "connection_established"}))

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(self.user_group_name, self.channel_name)

    async def notification_message(self, event):
        await self.send(json.dumps({
            "type": "notification",
            "message": event["message"],
            "notification_type": event.get("notification_type", "info"),
            "data": event.get("data", {})
        }))