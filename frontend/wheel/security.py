"""Shared Redis limits and revocable, opaque browser sessions."""
from functools import lru_cache
import hashlib
import hmac
import ipaddress
import json
import logging
import re
import secrets
from django.conf import settings
from django.http import JsonResponse, HttpResponse
from django.shortcuts import redirect
import redis

logger = logging.getLogger('wheel.security')
COOKIE = 'wheel_session'
SESSION_RE = re.compile(r'^[A-Za-z0-9_-]{43}$')
# Increment and expiry are atomic. Blocked requests never extend the window.
LIMIT_SCRIPT = '''
local n = redis.call('INCR', KEYS[1])
if n == 1 then redis.call('EXPIRE', KEYS[1], ARGV[1]) end
return {n, redis.call('TTL', KEYS[1])}
'''

@lru_cache(maxsize=8)
def connection(url):
    return redis.Redis.from_url(url, socket_connect_timeout=1, socket_timeout=1,
                                decode_responses=True, max_connections=32)

def store():
    return connection(settings.REDIS_URL)

def digest(value):
    return hmac.new(settings.SECRET_KEY.encode(), value.encode(), hashlib.sha256).hexdigest()

def token_version(token_id):
    token = settings.WHEEL_ACCESS_TOKENS.get(token_id)
    return digest('access-token:' + token_id + ':' + token) if token is not None else None

def match_token(supplied):
    # Scan all entries and compare equal-length digests. Never log the token.
    supplied_digest = hashlib.sha256(supplied.encode()).digest()
    matched = None
    for token_id, configured in settings.WHEEL_ACCESS_TOKENS.items():
        if hmac.compare_digest(supplied_digest, hashlib.sha256(configured.encode()).digest()):
            matched = token_id
    return matched

def client_ip(request):
    remote = request.META.get('REMOTE_ADDR', '')
    try:
        address = ipaddress.ip_address(remote)
    except ValueError:
        return 'unknown'
    # Only a specifically trusted immediate proxy may supply X-Real-IP.
    if any(address in ipaddress.ip_network(cidr) for cidr in settings.TRUSTED_PROXY_CIDRS):
        forwarded = request.META.get('HTTP_X_REAL_IP', '')
        try:
            return str(ipaddress.ip_address(forwarded))
        except ValueError:
            pass
    return str(address)

def consume(scope, subject, limit, seconds):
    key = settings.REDIS_PREFIX + ':rate:' + scope + ':' + digest(subject)
    count, ttl = store().eval(LIMIT_SCRIPT, 1, key, seconds)
    return int(count) <= limit, max(1, int(ttl))

def session_key(session_id):
    return settings.REDIS_PREFIX + ':session:' + digest(session_id)

def authenticated(request):
    session_id = request.COOKIES.get(COOKIE, '')
    if not SESSION_RE.fullmatch(session_id):
        return False
    value = store().get(session_key(session_id))
    if not value:
        return False
    try:
        record = json.loads(value)
    except (ValueError, TypeError):
        return False  # Pre-upgrade session format: sign in once again.
    if not isinstance(record, dict):
        return False
    token_id, version = record.get('token_id'), record.get('version')
    if not isinstance(token_id, str) or not isinstance(version, str) or not version.isascii():
        return False
    expected = token_version(token_id)
    if expected is None or not hmac.compare_digest(version, expected):
        return False
    request.wheel_session_id = session_id
    request.wheel_token_id = token_id
    return True

def new_session(request, response, token_id):
    version = token_version(token_id)
    if version is None:
        raise ValueError('Unknown access token ID')
    previous = request.COOKIES.get(COOKIE, '')
    if SESSION_RE.fullmatch(previous):
        store().delete(session_key(previous))
    session_id = secrets.token_urlsafe(32)
    record = json.dumps({'token_id': token_id, 'version': version})
    store().set(session_key(session_id), record, ex=settings.AUTH_SESSION_SECONDS)
    response.set_cookie(COOKIE, session_id, max_age=settings.AUTH_SESSION_SECONDS,
                        secure=settings.CSRF_COOKIE_SECURE, httponly=True,
                        samesite='Strict', path='/')

def revoke_session(request, response):
    session_id = request.COOKIES.get(COOKIE, '')
    if SESSION_RE.fullmatch(session_id):
        store().delete(session_key(session_id))
    response.delete_cookie(COOKIE, path='/', samesite='Strict')

def denied(request, message, status, retry=None):
    if request.path.startswith('/api/'):
        response = JsonResponse({'error': message, 'login_url': '/login/'}, status=status)
    else:
        response = HttpResponse(message, status=status, content_type='text/plain; charset=utf-8')
    if retry is not None:
        response['Retry-After'] = str(retry)
    return response

class SecurityMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        public = request.path == '/healthz' or request.path.startswith('/static/')
        try:
            if public:
                response = self.get_response(request)
            else:
                ip = client_ip(request)
                policies = [('requests', ip, settings.REQUESTS_PER_MINUTE, 60)]
                if request.path == '/login/' and request.method == 'POST':
                    policies += [('login', ip, settings.LOGIN_ATTEMPTS, settings.LOGIN_WINDOW_SECONDS),
                                 ('login-global', 'all', settings.LOGIN_GLOBAL_PER_MINUTE, 60)]
                for scope, subject, limit, window in policies:
                    allowed, retry = consume(scope, subject, limit, window)
                    if not allowed:
                        logger.warning('rate_limited scope=%s client=%s', scope, digest(ip)[:12])
                        return self.headers(denied(request, 'Слишком много запросов. Повторите позже.', 429, retry))
                if request.path == '/login/':
                    response = self.get_response(request)
                elif not authenticated(request):
                    response = (denied(request, 'Требуется вход по токену.', 401)
                                if request.path.startswith('/api/') else redirect('/login/'))
                else:
                    if request.path == '/api/spin' and request.method == 'POST':
                        for scope, subject, limit, window in [
                            ('spin', ip, settings.SPINS_PER_MINUTE, 60),
                            ('spin-burst', ip, settings.SPIN_BURST_PER_SECOND, 1),
                            ('spin-global', 'all', settings.SPINS_GLOBAL_PER_MINUTE, 60),
                        ]:
                            allowed, retry = consume(scope, subject, limit, window)
                            if not allowed:
                                return self.headers(denied(request, 'Лимит розыгрышей исчерпан. Повторите позже.', 429, retry))
                    response = self.get_response(request)
        except redis.RedisError:
            # No local-memory fallback: all workers must enforce the same policy.
            logger.error('security_store_unavailable')
            response = denied(request, 'Сервис авторизации временно недоступен.', 503)
        return self.headers(response)

    @staticmethod
    def headers(response):
        response['Cache-Control'] = 'no-store'
        response['X-Frame-Options'] = 'DENY'
        response['Referrer-Policy'] = 'same-origin'
        response['X-Content-Type-Options'] = 'nosniff'
        response['Content-Security-Policy'] = (
            "default-src 'self'; script-src 'self'; "
            "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
            "font-src 'self' https://fonts.gstatic.com; img-src 'self' data:; "
            "connect-src 'self'; object-src 'none'; base-uri 'none'; "
            "frame-ancestors 'none'; form-action 'self'"
        )
        return response
