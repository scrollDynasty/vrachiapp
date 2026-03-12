import os
import logging
import tempfile
import requests
import base64
from typing import Optional, Dict, Any, List

import anthropic
from django.core.files.storage import default_storage
from django.core.files.base import ContentFile
from django.conf import settings as django_settings
from .models import AIDialogue, AIMessage, User

logger = logging.getLogger(__name__)

import os
client = anthropic.Anthropic(api_key=django_settings.ANTHROPIC_API_KEY)
MODEL = "claude-haiku-4-5-20251001"


class HealzyAIService:
    """Healzy AI — медицинская помощница на базе Claude Sonnet 4"""

    def __init__(self):
        self.max_history_messages = 10

        self.system_prompt = """Ты — Healzy AI, опытная женщина-врач и медицинская помощница.

ТВОЯ ЛИЧНОСТЬ:
- Тёплая, внимательная, профессиональная
- Говоришь на русском языке, о себе — в женском роде
- Не начинаешь ответ с приветствия — сразу по делу
- Никогда не говоришь "как ИИ я не могу..." — ты врач

СПЕЦИАЛИЗАЦИИ:
🫀 Кардиология — сердце, давление, сосуды
🧠 Неврология — головная боль, головокружение, сон
🫁 Пульмонология — кашель, дыхание, бронхи
🦷 Стоматология — зубы, дёсны, полость рта
🍽️ Гастроэнтерология — желудок, кишечник, печень
🦴 Ортопедия — суставы, позвоночник, мышцы
🧴 Дерматология — кожа, сыпь, аллергия
👁️ Офтальмология — глаза, зрение
👂 ЛОР — уши, нос, горло
🤰 Гинекология — женское здоровье
👶 Педиатрия — здоровье детей
🧪 Общая терапия — симптомы, ОРВИ, грипп

КАК ОТВЕЧАТЬ:
✅ Анализируй симптомы внимательно и детально
✅ Объясняй возможные причины
✅ Давай конкретные практические советы
✅ Используй контекст предыдущих сообщений
✅ Задавай уточняющие вопросы если нужно

УРОВНИ СРОЧНОСТИ:
🟢 Не срочно — можно лечить дома
🟡 Умеренно — записаться к врачу в ближайшие дни
🔴 Срочно — нужен врач сегодня или скорая

ЗАПРЕЩЕНО:
❌ Ставить точный диагноз
❌ Назначать конкретные дозы лекарств
❌ Отвечать на немедицинские вопросы
❌ Говорить о себе в мужском роде"""

    # ==========================================
    # CONVERSATION HISTORY
    # ==========================================

    def _get_conversation_history(self, user: User) -> List[Dict]:
        """Получает историю последних сообщений диалога"""
        try:
            dialogue = AIDialogue.objects.filter(
                user=user, is_active=True
            ).first()
            if not dialogue:
                return []
            messages = AIMessage.objects.filter(
                dialogue=dialogue
            ).order_by('-timestamp')[:self.max_history_messages]
            history = []
            for msg in reversed(messages):
                role = 'user' if msg.sender_type == 'user' else 'assistant'
                content = msg.transcription or msg.content
                if content:
                    history.append({'role': role, 'content': content})
            return history
        except Exception as e:
            logger.error(f"Ошибка получения истории: {e}")
            return []

    # ==========================================
    # HELPERS
    # ==========================================

    def _detect_urgency(self, message: str) -> Optional[str]:
        message_lower = message.lower()
        emergency_keywords = [
            'боль в груди', 'не могу дышать', 'потеря сознания', 'упал в обморок',
            'инсульт', 'инфаркт', 'судороги', 'рвота с кровью', 'кровотечение',
            'отёк горла', 'парализовало'
        ]
        urgent_keywords = [
            'высокая температура', 'сильная боль', 'не проходит', 'ухудшается',
            'кровь в моче', 'желтуха', 'сильное головокружение'
        ]
        for kw in emergency_keywords:
            if kw in message_lower:
                return 'emergency'
        for kw in urgent_keywords:
            if kw in message_lower:
                return 'urgent'
        return None

    def _suggest_specialist(self, message: str) -> Optional[str]:
        message_lower = message.lower()
        specialists = {
            'кардиолог': ['сердце', 'давление', 'пульс', 'аритмия', 'боль в груди'],
            'невролог': ['голова болит', 'головная боль', 'мигрень', 'головокружение', 'онемение'],
            'гастроэнтеролог': ['желудок', 'живот болит', 'тошнота', 'изжога', 'понос', 'запор'],
            'дерматолог': ['сыпь', 'зуд', 'кожа', 'прыщи', 'покраснение'],
            'ортопед': ['сустав', 'колено', 'спина болит', 'позвоночник', 'перелом'],
            'пульмонолог': ['кашель', 'дыхание', 'астма', 'бронхит', 'одышка'],
            'лор': ['горло', 'нос', 'уши', 'насморк', 'ухо болит', 'гайморит'],
            'офтальмолог': ['глаза', 'зрение', 'глаз болит'],
            'эндокринолог': ['щитовидка', 'диабет', 'сахар', 'гормоны'],
            'уролог': ['почки', 'мочевой', 'боль при мочеиспускании'],
        }
        for specialist, keywords in specialists.items():
            for kw in keywords:
                if kw in message_lower:
                    return specialist
        return None

    def _is_greeting(self, text: str) -> bool:
        text_lower = text.strip().lower()
        if len(text_lower) > 40:
            return False
        greeting_keywords = [
            'привет', 'здравствуй', 'здравствуйте', 'добрый день',
            'добрый вечер', 'доброе утро', 'как дела', 'hi', 'hello'
        ]
        return any(kw in text_lower for kw in greeting_keywords)

    def _is_medical_question(self, text: str) -> bool:
        non_medical_keywords = [
            'политика', 'экономика', 'бизнес', 'финансы', 'акции', 'криптовалюта',
            'спорт', 'футбол', 'кино', 'музыка', 'игры', 'программирование',
            'история', 'география', 'математика', 'физика',
            'кулинария', 'рецепт', 'путешествия',
        ]
        text_lower = text.lower()
        for kw in non_medical_keywords:
            if kw in text_lower:
                return False
        return True

    def _add_urgency_note(self, message: str, ai_response: str) -> str:
        urgency = self._detect_urgency(message)
        if urgency == 'emergency':
            if '🔴' not in ai_response and 'скорую' not in ai_response.lower():
                return ai_response + "\n\n🔴 **Срочно вызовите скорую помощь (103)!**"
        return ai_response

    def _call_claude(self, messages: List[Dict], max_tokens: int = 1024) -> Optional[str]:
        """Вызывает Claude API"""
        try:
            response = client.messages.create(
                model=MODEL,
                max_tokens=max_tokens,
                system=self.system_prompt,
                messages=messages,
            )
            return response.content[0].text
        except Exception as e:
            logger.error(f"Ошибка Claude API: {e}")
            return None

    # ==========================================
    # SPEECH TO TEXT (STT)
    # ==========================================

    async def _transcribe_audio(self, audio_file) -> Optional[str]:
        """Транскрибирует аудио в текст используя OpenAI Whisper API"""
        try:
            # Try OpenAI Whisper if key is configured
            openai_key = getattr(django_settings, 'OPENAI_API_KEY', None)
            if openai_key:
                import openai
                openai_client = openai.OpenAI(api_key=openai_key)

                # Save audio to temp file
                with tempfile.NamedTemporaryFile(suffix='.webm', delete=False) as tmp:
                    tmp_path = tmp.name
                    if hasattr(audio_file, 'read'):
                        tmp.write(audio_file.read())
                        audio_file.seek(0)
                    else:
                        tmp.write(audio_file)

                try:
                    with open(tmp_path, 'rb') as f:
                        transcript = openai_client.audio.transcriptions.create(
                            model="whisper-1",
                            file=f,
                            language="ru"
                        )
                    os.unlink(tmp_path)
                    if transcript.text:
                        logger.info(f"Whisper STT: '{transcript.text[:50]}'")
                        return transcript.text
                except Exception as e:
                    logger.error(f"Whisper error: {e}")
                    os.unlink(tmp_path)

            # Fallback: Google Speech Recognition
            try:
                import speech_recognition as sr
                recognizer = sr.Recognizer()

                with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as tmp:
                    tmp_path = tmp.name
                    if hasattr(audio_file, 'read'):
                        tmp.write(audio_file.read())
                        audio_file.seek(0)
                    else:
                        tmp.write(audio_file)

                with sr.AudioFile(tmp_path) as source:
                    audio_data = recognizer.record(source)

                text = recognizer.recognize_google(audio_data, language='ru-RU')
                os.unlink(tmp_path)
                logger.info(f"Google STT: '{text[:50]}'")
                return text

            except Exception as e:
                logger.error(f"Google STT error: {e}")

            return None

        except Exception as e:
            logger.error(f"STT error: {e}")
            return None

    # ==========================================
    # TEXT TO SPEECH (TTS)
    # ==========================================

    async def _generate_speech_with_edge_tts(self, text: str) -> Optional[bytes]:
        try:
            import edge_tts
            clean_text = text.strip()[:1000]
            # Remove markdown bold/italic for cleaner speech
            import re
            clean_text = re.sub(r'\*+', '', clean_text)
            clean_text = re.sub(r'#{1,6}\s', '', clean_text)
            clean_text = re.sub(r'[🟢🟡🔴💡⚠️✅❌🫀🧠🫁🦷🍽️🦴🧴👁️👂🤰👶🧪]', '', clean_text)

            female_voices = [
                "ru-RU-SvetlanaNeural",
                "ru-RU-DariyaNeural",
                "ru-RU-PolarisNeural"
            ]
            for voice in female_voices:
                try:
                    with tempfile.NamedTemporaryFile(suffix='.mp3', delete=False) as tmp:
                        tmp_path = tmp.name
                    communicate = edge_tts.Communicate(clean_text, voice)
                    await communicate.save(tmp_path)
                    with open(tmp_path, 'rb') as f:
                        audio_content = f.read()
                    os.unlink(tmp_path)
                    if len(audio_content) > 1000:
                        return audio_content
                except Exception:
                    continue
            return None
        except ImportError:
            return None
        except Exception as e:
            logger.error(f"Edge TTS error: {e}")
            return None

    async def _generate_speech_with_google_tts(self, text: str) -> Optional[bytes]:
        try:
            import urllib.parse
            import re
            clean_text = re.sub(r'\*+', '', text.strip()[:500])
            clean_text = re.sub(r'[🟢🟡🔴💡⚠️✅❌]', '', clean_text)
            encoded = urllib.parse.quote(clean_text)
            url = f"https://translate.google.com/translate_tts?ie=UTF-8&tl=ru&client=tw-ob&q={encoded}"
            headers = {"User-Agent": "Mozilla/5.0"}
            response = requests.get(url, headers=headers, timeout=15)
            if response.status_code == 200 and len(response.content) > 1000:
                return response.content
            return None
        except Exception as e:
            logger.error(f"Google TTS error: {e}")
            return None

    async def _generate_speech_best_quality(self, text: str) -> Optional[bytes]:
        audio = await self._generate_speech_with_edge_tts(text)
        if audio:
            return audio
        audio = await self._generate_speech_with_google_tts(text)
        if audio:
            return audio
        return None

    # ==========================================
    # PDF EXTRACTION
    # ==========================================

    def _extract_pdf_text(self, file_data: bytes) -> str:
        """Извлекает текст из PDF файла"""
        try:
            import fitz  # PyMuPDF
            doc = fitz.open(stream=file_data, filetype="pdf")
            text_parts = []
            for page_num in range(min(doc.page_count, 10)):  # Max 10 pages
                page = doc[page_num]
                text_parts.append(f"[Страница {page_num + 1}]\n{page.get_text()}")
            doc.close()
            full_text = "\n\n".join(text_parts)
            # Limit to 8000 chars to stay within token limits
            return full_text[:8000] if len(full_text) > 8000 else full_text
        except ImportError:
            logger.error("PyMuPDF не установлен")
            return ""
        except Exception as e:
            logger.error(f"PDF extraction error: {e}")
            return ""

    # ==========================================
    # MAIN PROCESSING METHODS
    # ==========================================

    async def process_text_message(self, user: User, message: str) -> Dict[str, Any]:
        """Обрабатывает текстовое сообщение через Claude"""
        try:
            if self._is_greeting(message):
                history = self._get_conversation_history(user)
                if history:
                    response_text = 'Снова привет! Чем могу помочь со здоровьем?'
                else:
                    response_text = 'Привет! Я Healzy — ваша медицинская помощница. Расскажите, что вас беспокоит?'
                audio = await self._generate_speech_best_quality(response_text)
                return {
                    'success': True, 'response': response_text,
                    'type': 'text', 'audio_content': audio,
                    'has_voice': audio is not None
                }

            if not self._is_medical_question(message):
                response_text = (
                    "Я специализируюсь только на медицинских вопросах. "
                    "Расскажите о ваших симптомах или задайте вопрос о здоровье."
                )
                audio = await self._generate_speech_best_quality(response_text)
                return {
                    'success': True, 'response': response_text,
                    'type': 'text', 'audio_content': audio,
                    'has_voice': audio is not None
                }

            # Build messages with history
            history = self._get_conversation_history(user)
            messages = [{'role': h['role'], 'content': h['content']} for h in history]
            messages.append({'role': 'user', 'content': message})

            ai_response = self._call_claude(messages)

            if ai_response:
                ai_response = self._add_urgency_note(message, ai_response)
                specialist = self._suggest_specialist(message)
                if specialist and specialist not in ai_response.lower():
                    ai_response += f"\n\n💡 По этим симптомам рекомендую обратиться к **{specialist}у**."

                audio = await self._generate_speech_best_quality(ai_response)
                return {
                    'success': True, 'response': ai_response,
                    'type': 'text', 'audio_content': audio,
                    'has_voice': audio is not None,
                    'specialist_suggestion': specialist,
                }
            return {'success': False, 'error': 'Не удалось получить ответ от AI'}

        except Exception as e:
            logger.error(f"Ошибка обработки текста: {e}")
            return {'success': False, 'error': 'Ошибка при обработке сообщения'}

    async def process_image_message(self, user: User, image_file) -> Dict[str, Any]:
        """Обрабатывает изображение через Claude Vision"""
        try:
            file_path = default_storage.save(f'temp/ai_images/{image_file.name}', image_file)
            with default_storage.open(file_path, 'rb') as f:
                image_data = base64.standard_b64encode(f.read()).decode('utf-8')
            default_storage.delete(file_path)

            history = self._get_conversation_history(user)
            messages = []
            for h in history[-4:]:
                messages.append({'role': h['role'], 'content': h['content']})

            messages.append({
                'role': 'user',
                'content': [
                    {
                        'type': 'image',
                        'source': {
                            'type': 'base64',
                            'media_type': image_file.content_type,
                            'data': image_data,
                        }
                    },
                    {
                        'type': 'text',
                        'text': (
                            'Пациент прислал медицинское изображение. '
                            'Проанализируй его: опиши что видишь, дай медицинскую оценку, '
                            'укажи возможные причины, дай рекомендации и '
                            'укажи уровень срочности (🟢/🟡/🔴).'
                        )
                    }
                ]
            })

            ai_response = self._call_claude(messages, max_tokens=1500)
            if ai_response:
                audio = await self._generate_speech_best_quality(ai_response[:500])
                return {
                    'success': True, 'response': ai_response,
                    'type': 'image', 'audio_content': audio,
                    'has_voice': audio is not None,
                }
            return {'success': False, 'error': 'Не удалось проанализировать изображение'}

        except Exception as e:
            logger.error(f"Ошибка обработки изображения: {e}")
            return {'success': False, 'error': 'Ошибка при анализе изображения'}

    async def process_pdf_message(self, user: User, pdf_file) -> Dict[str, Any]:
        """Обрабатывает PDF файл — извлекает текст и анализирует через Claude"""
        try:
            file_data = pdf_file.read()
            pdf_file.seek(0)

            pdf_text = self._extract_pdf_text(file_data)

            if not pdf_text.strip():
                return {
                    'success': False,
                    'error': 'Не удалось извлечь текст из PDF. Возможно, файл содержит только изображения.'
                }

            history = self._get_conversation_history(user)
            messages = []
            for h in history[-4:]:
                messages.append({'role': h['role'], 'content': h['content']})

            messages.append({
                'role': 'user',
                'content': (
                    f"Пациент загрузил медицинский документ (PDF). Проанализируй его содержимое:\n\n"
                    f"{pdf_text}\n\n"
                    f"Пожалуйста:\n"
                    f"1. Определи тип документа (анализы, рецепт, выписка, снимок и т.д.)\n"
                    f"2. Выдели ключевые медицинские показатели\n"
                    f"3. Объясни что означают результаты простым языком\n"
                    f"4. Укажи если что-то выходит за пределы нормы\n"
                    f"5. Дай рекомендации и укажи уровень срочности (🟢/🟡/🔴)"
                )
            })

            ai_response = self._call_claude(messages, max_tokens=2000)
            if ai_response:
                audio = await self._generate_speech_best_quality(ai_response[:500])
                return {
                    'success': True, 'response': ai_response,
                    'type': 'pdf', 'audio_content': audio,
                    'has_voice': audio is not None,
                    'pages_analyzed': pdf_text.count('[Страница'),
                }
            return {'success': False, 'error': 'Не удалось проанализировать документ'}

        except Exception as e:
            logger.error(f"Ошибка обработки PDF: {e}")
            return {'success': False, 'error': 'Ошибка при анализе PDF документа'}

    async def process_audio_message(self, user: User, audio_file) -> Dict[str, Any]:
        """Обрабатывает аудио — STT → Claude → TTS (полный голосовой цикл)"""
        try:
            logger.info(f"Обработка аудио от {user.email}")

            # Step 1: Speech to Text
            transcription = await self._transcribe_audio(audio_file)

            if not transcription:
                response_text = (
                    "Получила ваше голосовое сообщение, но не смогла распознать речь. "
                    "Пожалуйста, говорите чётче или используйте текстовый ввод."
                )
                audio = await self._generate_speech_best_quality(response_text)
                return {
                    'success': True, 'response': response_text,
                    'type': 'voice_response', 'transcription': None,
                    'audio_content': audio, 'has_voice': audio is not None
                }

            logger.info(f"Распознано: '{transcription}'")

            # Step 2: Process text through Claude
            text_result = await self.process_text_message(user, transcription)

            if text_result['success']:
                return {
                    'success': True,
                    'response': text_result['response'],
                    'type': 'voice_response',
                    'transcription': transcription,
                    'audio_content': text_result.get('audio_content'),
                    'has_voice': text_result.get('has_voice', False),
                    'specialist_suggestion': text_result.get('specialist_suggestion'),
                }
            return text_result

        except Exception as e:
            logger.error(f"Ошибка обработки аудио: {e}")
            return {'success': False, 'error': 'Ошибка при обработке аудио'}

    # ==========================================
    # DIALOGUE MANAGEMENT
    # ==========================================

    def save_dialogue_message(self, user: User, content: str, sender_type: str,
                              message_type: str = 'text', audio_file=None,
                              transcription: str = None,
                              audio_duration: float = None) -> AIMessage:
        try:
            dialogue, created = AIDialogue.objects.get_or_create(
                user=user, is_active=True,
                defaults={'title': f'Диалог с AI — {user.first_name or user.email}'}
            )
            message = AIMessage.objects.create(
                dialogue=dialogue,
                sender_type=sender_type,
                message_type=message_type,
                content=content,
                transcription=transcription,
                audio_duration=audio_duration
            )
            if audio_file:
                message.audio_file.save(
                    f'ai_message_{message.id}.mp3',
                    ContentFile(audio_file),
                    save=True
                )
            dialogue.save()
            return message
        except Exception as e:
            logger.error(f"Ошибка сохранения сообщения: {e}")
            raise

    def start_new_dialogue(self, user: User, title: Optional[str] = None) -> AIDialogue:
        AIDialogue.objects.filter(user=user, is_active=True).update(is_active=False)
        return AIDialogue.objects.create(
            user=user,
            title=title or 'Новый диалог с AI',
            is_active=True,
        )

    def close_dialogue(self, user: User, dialogue_id: int) -> bool:
        try:
            dialogue = AIDialogue.objects.get(id=dialogue_id, user=user)
            dialogue.is_active = False
            dialogue.save()
            return True
        except AIDialogue.DoesNotExist:
            return False
        except Exception as e:
            logger.error(f"Ошибка закрытия диалога: {e}")
            return False


ai_service = HealzyAIService()