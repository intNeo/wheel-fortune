import logging
import redis
from django.conf import settings
from django.http import HttpResponseRedirect
from django.middleware.csrf import rotate_token
from django.shortcuts import render
from django.views.decorators.csrf import ensure_csrf_cookie
from django.views.decorators.http import require_http_methods, require_POST
from .security import match_token, denied, authenticated, new_session, revoke_session, client_ip, digest

logger = logging.getLogger('wheel.security')

@require_http_methods(['GET', 'POST'])
@ensure_csrf_cookie
def login(request):
    if request.method == 'GET':
        if authenticated(request):
            return HttpResponseRedirect('/')
        return render(request, 'wheel/login.html')
    supplied = request.POST.get('token', '')
    token_id = match_token(supplied)
    if token_id is None:
        logger.warning('login_failed client=%s', digest(client_ip(request))[:12])
        return render(request, 'wheel/login.html', {'error': 'Неверный токен доступа.'}, status=401)
    response = HttpResponseRedirect('/')
    try:
        new_session(request, response, token_id)
    except redis.RedisError:
        logger.error('security_store_unavailable')
        return denied(request, 'Сервис авторизации временно недоступен.', 503)
    rotate_token(request)
    logger.info('login_success client=%s', digest(client_ip(request))[:12])
    return response

@require_POST
def logout(request):
    response = HttpResponseRedirect('/login/')
    try:
        revoke_session(request, response)
    except redis.RedisError:
        logger.error('security_store_unavailable')
        return denied(request, 'Не удалось завершить сессию. Повторите выход позже.', 503)
    rotate_token(request)
    return response
