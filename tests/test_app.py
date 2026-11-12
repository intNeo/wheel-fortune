import importlib.util
import os
from pathlib import Path
import sys
import threading
import uuid
import redis
import redislite
import socket
import subprocess
import atexit
import time
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
# Dedicated real Redis subprocess. No production connection or FLUSHDB.
with socket.socket() as probe:
    probe.bind(('127.0.0.1', 0))
    _test_port = probe.getsockname()[1]
_test_url = f'redis://127.0.0.1:{_test_port}/0'
_binary = str(Path(redislite.__file__).parent / 'bin/redis-server')
_test_process = subprocess.Popen([_binary, '--bind', '127.0.0.1', '--port', str(_test_port),
                                  '--save', '', '--appendonly', 'no', '--daemonize', 'no'],
                                 stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
def _stop_redis():
    _test_process.terminate()
    _test_process.wait(timeout=5)
atexit.register(_stop_redis)
for _ in range(50):
    try:
        redis.Redis.from_url(_test_url).ping()
        break
    except redis.RedisError:
        time.sleep(.02)
else:
    raise RuntimeError('Test Redis could not start')
os.environ.update(API_TOKEN='test-token-' + 'a' * 40,
                  DJANGO_SECRET_KEY='test-secret-' + 'b' * 40,
                  DJANGO_SETTINGS_MODULE='config.settings',
                  WHEEL_ACCESS_TOKEN='test-access-token-' + 'c' * 40, REDIS_URL=_test_url,
                  ALLOWED_HOSTS='localhost,127.0.0.1,testserver')
sys.path.insert(0, str(ROOT / 'frontend'))
spec = importlib.util.spec_from_file_location('draw_backend', ROOT / 'backend/app.py')
backend = importlib.util.module_from_spec(spec)
spec.loader.exec_module(backend)
import django
django.setup()
from django.core.management import call_command
call_command('collectstatic', interactive=False, verbosity=0)
from django.test import Client, RequestFactory, override_settings
from django.http import HttpResponse
from wheel import security
from werkzeug.serving import make_server

class TestContext(unittest.TestCase):
    def setUp(self):
        self.prefix = 'fortune-test-' + uuid.uuid4().hex
        self.config = override_settings(REDIS_PREFIX=self.prefix, CSRF_COOKIE_SECURE=False)
        self.config.enable()
        self.addCleanup(self.config.disable)
        self.addCleanup(self.clean_redis)
        self.client = backend.create_app().test_client()
        self.headers = {'Authorization': 'Bearer ' + os.environ['API_TOKEN']}
        self.payload = {'names': ['test'] * 3 + ['test1'] * 2 + ['test2'], 'mode': 'normal', 'duration': 3}

    def clean_redis(self):
        keys = security.store().keys(self.prefix + ':*')
        if keys:
            security.store().delete(*keys)

    def web(self, csrf=False, ip='127.0.0.1'):
        web = Client(enforce_csrf_checks=csrf, REMOTE_ADDR=ip)
        web.get('/login/')
        response = web.post('/login/', {'token': os.environ['WHEEL_ACCESS_TOKEN']},
                            HTTP_X_CSRFTOKEN=web.cookies['csrftoken'].value)
        self.assertEqual(response.status_code, 302)
        return web

    def post(self, **changes):
        return self.client.post('/api/spin', json=self.payload | changes, headers=self.headers)

class DrawTests(TestContext):
    def test_normal_nickname_probability(self):
        with patch.object(backend.secrets, 'randbelow', return_value=0):
            data = self.post().json
        self.assertEqual(data['winner'], 'test')
        self.assertEqual(data['probability'], .5)

    def test_weighted(self):
        with patch.object(backend.secrets, 'randbelow', return_value=5):
            data = self.post(mode='weighted').json
        self.assertEqual(data['selected_index'], 2)
        self.assertAlmostEqual(data['probability'], 1/6)

    def test_inverse_exact_integer_weights(self):
        with patch.object(backend.secrets, 'randbelow', return_value=5) as rand:
            data = self.post(mode='inverse').json
        rand.assert_called_once_with(11)  # exact weights 2, 3, 6
        self.assertEqual(data['winner'], 'test2')
        self.assertAlmostEqual(data['probability'], 6/11)

    def test_invalid_payloads(self):
        for change in [{'names': []}, {'names': ['x']*5001}, {'names': ['x'*101]},
                       {'names': [None]}, {'duration': True}, {'duration': 2},
                       {'duration': 21}, {'mode': 'unknown'}]:
            with self.subTest(change=change):
                self.assertEqual(self.post(**change).status_code, 400)

    def test_token_required(self):
        self.assertEqual(self.client.post('/api/spin', json=self.payload).status_code, 401)

    def test_single_nickname(self):
        self.assertEqual(self.post(names=['only'], mode='inverse', duration=20).json['probability'], 1)

    def test_django_csrf_and_real_flask_roundtrip(self):
        server = make_server('127.0.0.1', 0, backend.create_app())
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            with override_settings(FLASK_API_URL=f'http://127.0.0.1:{server.server_port}'):
                web = self.web(csrf=True)
                self.assertEqual(web.get('/').status_code, 200)
                self.assertEqual(web.post('/api/spin', self.payload, content_type='application/json').status_code, 403)
                csrf = web.cookies['csrftoken'].value
                response = web.post('/api/spin', self.payload, content_type='application/json', HTTP_X_CSRFTOKEN=csrf)
                self.assertEqual(response.status_code, 200)
                self.assertIn(response.json()['winner'], self.payload['names'])
        finally:
            server.shutdown()
            thread.join(timeout=2)

    def test_service_unavailable(self):
        with patch('wheel.views.requests.post', side_effect=__import__('requests').ConnectionError):
            response = self.web().post('/api/spin', self.payload, content_type='application/json')
        self.assertEqual(response.status_code, 503)

class SecurityTests(TestContext):
    def test_protected_api(self):
        client = Client()
        self.assertEqual(client.get('/').status_code, 302)
        with patch('wheel.views.requests.post') as proxy:
            response = client.post('/api/spin', self.payload, content_type='application/json')
        self.assertEqual(response.status_code, 401)
        proxy.assert_not_called()

    def test_login_bruteforce(self):
        client = Client()
        for _ in range(5):
            self.assertEqual(client.post('/login/', {'token': 'wrong'}).status_code, 401)
        response = client.post('/login/', {'token': os.environ['WHEEL_ACCESS_TOKEN']})
        self.assertEqual(response.status_code, 429)
        self.assertTrue(int(response['Retry-After']) > 0)

    def test_login_csrf_required(self):
        client = Client(enforce_csrf_checks=True)
        response = client.post('/login/', {'token': os.environ['WHEEL_ACCESS_TOKEN']})
        self.assertEqual(response.status_code, 403)

    def test_cookie_and_logout_replay(self):
        web = self.web(csrf=True)
        cookie = web.cookies[security.COOKIE]
        self.assertTrue(cookie['httponly'])
        self.assertEqual(cookie['samesite'], 'Strict')
        self.assertNotEqual(cookie.value, os.environ['WHEEL_ACCESS_TOKEN'])
        replay = Client()
        replay.cookies[security.COOKIE] = cookie.value
        response = web.post('/logout/', HTTP_X_CSRFTOKEN=web.cookies['csrftoken'].value)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(replay.post('/api/spin').status_code, 401)

    def test_session_expiry(self):
        web = self.web()
        security.store().expire(security.session_key(web.cookies[security.COOKIE].value), 0)
        self.assertEqual(web.post('/api/spin').status_code, 401)

    def test_cookie_forgery(self):
        web = Client()
        web.cookies[security.COOKIE] = 'A' * 43
        self.assertEqual(web.post('/api/spin').status_code, 401)

    def test_access_token_rotation(self):
        web = self.web()
        with override_settings(WHEEL_ACCESS_TOKENS={'default': 'rotated-token-'+'z'*40}):
            self.assertEqual(web.post('/api/spin').status_code, 401)

    def test_same_ip_sessions_share_spin_limit(self):
        a, b = self.web(), self.web()
        with override_settings(SPINS_PER_MINUTE=2, SPIN_BURST_PER_SECOND=10):
            with patch('wheel.views.requests.post') as proxy:
                proxy.return_value.status_code = 200
                proxy.return_value.json.return_value = {'winner': 'test'}
                self.assertEqual(a.post('/api/spin', self.payload, content_type='application/json').status_code, 200)
                self.assertEqual(b.post('/api/spin', self.payload, content_type='application/json').status_code, 200)
                response = a.post('/api/spin', self.payload, content_type='application/json')
                self.assertEqual(response.status_code, 429)
                self.assertEqual(proxy.call_count, 2)

    def test_global_limit_across_ips(self):
        a = self.web(ip='192.0.2.10')
        b = self.web(ip='192.0.2.11')
        with override_settings(SPINS_GLOBAL_PER_MINUTE=1):
            with patch('wheel.views.requests.post') as proxy:
                proxy.return_value.status_code = 200
                proxy.return_value.json.return_value = {'winner': 'test'}
                self.assertEqual(a.post('/api/spin', self.payload, content_type='application/json').status_code, 200)
                self.assertEqual(b.post('/api/spin', self.payload, content_type='application/json').status_code, 429)

    def test_untrusted_proxy_header_ignored(self):
        request = RequestFactory().get('/', REMOTE_ADDR='192.0.2.1', HTTP_X_REAL_IP='198.51.100.2')
        with override_settings(TRUSTED_PROXY_CIDRS=[]):
            self.assertEqual(security.client_ip(request), '192.0.2.1')
        with override_settings(TRUSTED_PROXY_CIDRS=['192.0.2.1/32']):
            self.assertEqual(security.client_ip(request), '198.51.100.2')

    def test_redis_outage_fails_closed(self):
        with patch('wheel.security.store', side_effect=redis.ConnectionError):
            self.assertEqual(Client().post('/api/spin').status_code, 503)
            self.assertEqual(Client().get('/login/').status_code, 503)

    def test_concurrent_atomic_limit(self):
        from concurrent.futures import ThreadPoolExecutor
        with ThreadPoolExecutor(max_workers=8) as executor:
            results = list(executor.map(lambda _: security.consume('parallel', 'same-ip', 5, 60)[0], range(30)))
        self.assertEqual(sum(results), 5)
        # A separate client/worker sees the same persisted count and TTL.
        other = redis.Redis.from_url(_test_url, decode_responses=True)
        key = self.prefix + ':rate:parallel:' + security.digest('same-ip')
        self.assertEqual(int(other.get(key)), 30)
        self.assertGreater(other.ttl(key), 0)

    def test_secure_cookie_default_option(self):
        with override_settings(CSRF_COOKIE_SECURE=True):
            client = self.web()
            self.assertTrue(client.cookies[security.COOKIE]['secure'])

class MultiTokenTests(TestContext):
    tokens = {'intneo': 'a' * 64, 'friend': 'b' * 64}

    def login_as(self, name, ip='192.0.2.25'):
        web = Client(enforce_csrf_checks=True, REMOTE_ADDR=ip)
        web.get('/login/')
        response = web.post('/login/', {'token': self.tokens[name]},
                            HTTP_X_CSRFTOKEN=web.cookies['csrftoken'].value)
        self.assertEqual(response.status_code, 302)
        return web

    def test_two_tokens_have_separate_sessions(self):
        with override_settings(WHEEL_ACCESS_TOKENS=self.tokens):
            a, b = self.login_as('intneo'), self.login_as('friend')
            self.assertNotEqual(a.cookies[security.COOKIE].value, b.cookies[security.COOKIE].value)
            for client, name in ((a, 'intneo'), (b, 'friend')):
                value = security.store().get(security.session_key(client.cookies[security.COOKIE].value))
                data = __import__('json').loads(value)
                self.assertEqual(data['token_id'], name)
                self.assertNotIn(self.tokens[name], value)
                self.assertEqual(client.get('/').status_code, 200)

    def test_removing_one_token_only_revokes_its_sessions(self):
        with override_settings(WHEEL_ACCESS_TOKENS=self.tokens):
            a, b = self.login_as('intneo'), self.login_as('friend')
        with override_settings(WHEEL_ACCESS_TOKENS={'intneo': self.tokens['intneo']}):
            self.assertEqual(a.get('/').status_code, 200)
            self.assertEqual(b.post('/api/spin').status_code, 401)
            response = Client().post('/login/', {'token': self.tokens['friend']})
            self.assertEqual(response.status_code, 401)

    def test_rotating_one_token_preserves_other_session(self):
        with override_settings(WHEEL_ACCESS_TOKENS=self.tokens):
            a, b = self.login_as('intneo'), self.login_as('friend')
        with override_settings(WHEEL_ACCESS_TOKENS=self.tokens | {'friend': 'c' * 64}):
            self.assertEqual(a.get('/').status_code, 200)
            self.assertEqual(b.post('/api/spin').status_code, 401)

    def test_add_and_reorder_preserves_sessions(self):
        with override_settings(WHEEL_ACCESS_TOKENS=self.tokens):
            a = self.login_as('intneo')
        with override_settings(WHEEL_ACCESS_TOKENS={'friend': 'b' * 64, 'new': 'c' * 64, 'intneo': 'a' * 64}):
            self.assertEqual(a.get('/').status_code, 200)

    def test_logout_only_revokes_current_browser(self):
        with override_settings(WHEEL_ACCESS_TOKENS=self.tokens):
            a, b = self.login_as('intneo'), self.login_as('intneo')
            a.post('/logout/', HTTP_X_CSRFTOKEN=a.cookies['csrftoken'].value)
            self.assertEqual(b.get('/').status_code, 200)
            self.assertEqual(a.post('/api/spin').status_code, 401)

    def test_tokens_do_not_bypass_ip_limit(self):
        with override_settings(WHEEL_ACCESS_TOKENS=self.tokens, SPINS_PER_MINUTE=1):
            a, b = self.login_as('intneo'), self.login_as('friend')
            with patch('wheel.views.requests.post') as proxy:
                proxy.return_value.status_code = 200
                proxy.return_value.json.return_value = {'winner': 'test'}
                for client, expected in ((a, 200), (b, 429)):
                    response = client.post('/api/spin', self.payload, content_type='application/json',
                                           HTTP_X_CSRFTOKEN=client.cookies['csrftoken'].value)
                    self.assertEqual(response.status_code, expected)

    def test_pre_upgrade_session_requires_login(self):
        web = Client()
        session_id = 'A' * 43
        security.store().set(security.session_key(session_id), 'e' * 64, ex=60)
        web.cookies[security.COOKIE] = session_id
        self.assertEqual(web.post('/api/spin').status_code, 401)

    def test_config_parser_and_precedence(self):
        from wheel.access_tokens import parse_access_tokens
        import json
        self.assertEqual(parse_access_tokens('', 'l'*64), {'default': 'l'*64})
        self.assertEqual(parse_access_tokens(json.dumps(self.tokens), 'l'*64), self.tokens)
        for raw in ('{}', '[]', 'invalid', '{"a":"short"}',
                    '{"a":"'+'a'*64+'","a":"'+'b'*64+'"}',
                    json.dumps({'a': 'a'*64, 'b': 'a'*64}),
                    json.dumps({'bad name': 'a'*64})):
            with self.subTest(raw=raw):
                with self.assertRaises(ValueError):
                    parse_access_tokens(raw, 'l'*64)

if __name__ == '__main__':
    unittest.main()
