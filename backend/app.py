"""Private draw API; only the Django service can reach it in Compose."""
import hmac
import math
import os
import secrets
from collections import Counter
from datetime import datetime, timezone
from fractions import Fraction
from uuid import uuid4
from flask import Flask, jsonify, request


def create_app():
    app = Flask(__name__)
    app.config['MAX_CONTENT_LENGTH'] = 1024 * 1024
    token = os.environ['API_TOKEN']
    if len(token) < 32:
        raise RuntimeError('API_TOKEN must contain at least 32 characters')

    @app.get('/healthz')
    def health():
        return {'status': 'ok'}

    @app.post('/api/spin')
    def spin():
        if not hmac.compare_digest(request.headers.get('Authorization', ''), f'Bearer {token}'):
            return jsonify(error='Unauthorized'), 401
        data = request.get_json(silent=True)
        if not isinstance(data, dict):
            return jsonify(error='Ожидается JSON-объект.'), 400
        names, mode, duration = data.get('names'), data.get('mode'), data.get('duration')
        if (not isinstance(names, list) or not 1 <= len(names) <= 5000
                or any(not isinstance(n, str) or not n.strip() or len(n) > 100 for n in names)):
            return jsonify(error='Введите от 1 до 5000 ников длиной до 100 символов.'), 400
        if mode not in ('normal', 'weighted', 'inverse'):
            return jsonify(error='Неизвестный режим.'), 400
        if type(duration) is not int or not 3 <= duration <= 20:
            return jsonify(error='Длительность должна быть целым числом от 3 до 20.'), 400
        names = [n.strip() for n in names]
        counts = Counter(names)
        if mode == 'normal':
            entries, weights = names, [1] * len(names)
        else:
            entries = list(counts)
            if mode == 'weighted':
                weights = list(counts.values())
            else:
                denominator = math.lcm(*counts.values())
                weights = [denominator // count for count in counts.values()]
        total = sum(weights)
        ticket = secrets.randbelow(total)
        index = 0
        for index, weight in enumerate(weights):
            if ticket < weight:
                break
            ticket -= weight
        winner = entries[index]
        nickname_weight = sum(w for n, w in zip(entries, weights) if n == winner)
        return jsonify(id=str(uuid4()), winner=winner, selected_index=index,
                       probability=float(Fraction(nickname_weight, total)),
                       duration=duration, mode=mode,
                       created_at=datetime.now(timezone.utc).isoformat())

    @app.errorhandler(413)
    def too_large(_):
        return jsonify(error='Слишком большой список участников.'), 413

    return app
