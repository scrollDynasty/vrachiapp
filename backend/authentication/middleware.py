from django.utils.deprecation import MiddlewareMixin
import os
from channels.middleware import BaseMiddleware
from channels.db import database_sync_to_async
from urllib.parse import parse_qs
import logging

logger = logging.getLogger(__name__)

class DisableCSRFMiddleware(MiddlewareMixin):
    def process_request(self, request):
        # В продакшене лучше не отключать CSRF. Оставляем флаг через env.
        if os.getenv('DISABLE_CSRF', 'false').lower() == 'true':
            if request.path.startswith('/api/'):
                setattr(request, '_dont_enforce_csrf_checks', True)

class WebSocketAuthMiddleware(BaseMiddleware):
    async def __call__(self, scope, receive, send):
        # Получаем пользователя из сессии
        user = await self.get_user(scope)
        scope['user'] = user
        logger.info(f"WebSocket user: {user}, authenticated: {user.is_authenticated}")
        return await super().__call__(scope, receive, send)

    @database_sync_to_async
    def get_user(self, scope):
        from django.contrib.auth.models import AnonymousUser
        from django.contrib.auth import get_user_model
        from django.contrib.sessions.models import Session
        User = get_user_model()
        try:
            # --- 1. Try Django session from scope ---
            if 'session' in scope and scope['session']:
                session_key = scope['session'].get('_auth_user_id')
                if session_key:
                    try:
                        user = User.objects.get(id=session_key)
                        logger.info(f"User found in session: {user}")
                        return user
                    except User.DoesNotExist:
                        pass

            # --- 2. Try sessionid from cookies ---
            headers = dict(scope.get('headers', []))
            cookie_header = headers.get(b'cookie', b'').decode()

            if cookie_header:
                cookies = {}
                for cookie in cookie_header.split(';'):
                    if '=' in cookie:
                        key, value = cookie.strip().split('=', 1)
                        cookies[key.strip()] = value.strip()

                sessionid = cookies.get('sessionid')
                if sessionid:
                    try:
                        session = Session.objects.get(session_key=sessionid)
                        session_data = session.get_decoded()
                        user_id = session_data.get('_auth_user_id')
                        if user_id:
                            user = User.objects.get(id=user_id)
                            logger.info(f"User found via cookie session: {user}")
                            return user
                    except (Session.DoesNotExist, User.DoesNotExist) as e:
                        logger.warning(f"Session/User not found via cookie: {e}")

            # --- 3. Try token from query string (?token=xxx) ---
            query_string = scope.get('query_string', b'').decode()
            params = parse_qs(query_string)
            token_key = params.get('token', [None])[0]

            if token_key:
                try:
                    from rest_framework.authtoken.models import Token
                    token_obj = Token.objects.select_related('user').get(key=token_key)
                    logger.info(f"User found via token: {token_obj.user}")
                    return token_obj.user
                except Exception as e:
                    logger.warning(f"Token auth failed: {e}")

            # --- 4. Try token from Authorization header ---
            auth_header = headers.get(b'authorization', b'').decode()
            if auth_header.startswith('Token '):
                token_key = auth_header.split(' ', 1)[1].strip()
                try:
                    from rest_framework.authtoken.models import Token
                    token_obj = Token.objects.select_related('user').get(key=token_key)
                    logger.info(f"User found via Authorization header: {token_obj.user}")
                    return token_obj.user
                except Exception as e:
                    logger.warning(f"Header token auth failed: {e}")

            logger.warning("No authenticated user found, returning AnonymousUser")
            return AnonymousUser()

        except Exception as e:
            logger.error(f"Error in WebSocket auth middleware: {e}")
            return AnonymousUser()