"""Create or safely extend local configuration without replacing existing keys."""
import os
from pathlib import Path
import secrets

path = Path(__file__).resolve().parent / '.env'
original = path.read_text() if path.exists() else ''
present = set()
for line in original.splitlines():
    clean = line.strip()
    if clean and not clean.startswith('#') and '=' in clean:
        present.add(clean.split('=', 1)[0].strip())
defaults = {
    'DJANGO_SECRET_KEY': lambda: secrets.token_hex(48),
    'API_TOKEN': lambda: secrets.token_hex(32),
    'WHEEL_ACCESS_TOKEN': lambda: secrets.token_hex(32),
    'REDIS_PASSWORD': lambda: secrets.token_hex(32),
    'ALLOWED_HOSTS': lambda: 'localhost,127.0.0.1',
    'CSRF_TRUSTED_ORIGINS': lambda: '',
    'COOKIE_SECURE': lambda: 'true',
    'TRUSTED_PROXY_CIDRS': lambda: '',
}
missing = [key for key in defaults if key not in present]
if missing:
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
    with os.fdopen(fd, 'a') as output:
        if original and not original.endswith('\n'):
            output.write('\n')
        for key in missing:
            output.write(f'{key}={defaults[key]()}\n')
    os.chmod(path, 0o600)
print('Configuration ready. Existing values preserved. Secrets are in .env (not printed).')
print('Before production, configure domain, HTTPS, COOKIE_SECURE=true and trusted proxy CIDRs.')
