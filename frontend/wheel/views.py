import json
import requests
from django.conf import settings
from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.csrf import ensure_csrf_cookie
from django.views.decorators.http import require_GET, require_POST

@require_GET
@ensure_csrf_cookie
def index(request):
    return render(request, 'wheel/index.html')

@require_GET
def health(request):
    return JsonResponse({'status': 'ok'})

@require_POST
def spin(request):
    try:
        data = json.loads(request.body)
    except (ValueError, UnicodeDecodeError):
        return JsonResponse({'error': 'Некорректный JSON.'}, status=400)
    try:
        result = requests.post(settings.FLASK_API_URL + '/api/spin', json=data,
                               headers={'Authorization': f'Bearer {settings.API_TOKEN}'}, timeout=5)
        if result.status_code in (400, 413):
            return JsonResponse(result.json(), status=result.status_code)
        result.raise_for_status()
        return JsonResponse(result.json())
    except (requests.RequestException, ValueError):
        return JsonResponse({'error': 'Сервис розыгрышей временно недоступен. Попробуйте ещё раз.'}, status=503)
