#!/usr/bin/env python3
"""Add exactly one named access token to .env; preserve existing credentials."""
import argparse
import json
import os
from pathlib import Path
import re
import secrets
import sys
import tempfile


def main():
    parser = argparse.ArgumentParser(description='Добавить один токен доступа прямо в .env')
    parser.add_argument('name', help='Имя пользователя/токена: friend, intneo, moderator')
    args = parser.parse_args()
    if not re.fullmatch(r'[A-Za-z0-9_.-]{1,64}', args.name):
        parser.error('Имя: 1–64 латинских буквы, цифры, точка, дефис или подчёркивание.')
    root = Path(__file__).resolve().parent
    path = root / '.env'
    if not path.is_file():
        raise SystemExit('Не найден .env рядом со скриптом. Сначала выполните python3 setup_env.py.')
    # The multi-token update already contains this shared validator.
    sys.path.insert(0, str(root / 'frontend'))
    try:
        from wheel.access_tokens import parse_access_tokens
    except ImportError:
        raise SystemExit('Сначала установите обновление с поддержкой WHEEL_ACCESS_TOKENS.') from None
    lock = root / '.env.access-tokens.lock'
    try:
        lock_fd = os.open(lock, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError:
        raise SystemExit('Другой процесс изменяет токены. Повторите позже. Если процесс аварийно завершился, удалите оставшийся .env.access-tokens.lock.') from None
    temporary = None
    try:
        os.close(lock_fd)
        text = path.read_text()
        lines = text.splitlines()

        def setting(key):
            found = [line.split('=', 1)[1].strip() for line in lines
                     if '=' in line and line.split('=', 1)[0].strip() == key]
            if len(found) > 1:
                raise ValueError('Удалите дублирующиеся строки ' + key + ' из .env.')
            raw = found[0] if found else ''
            if raw.startswith("'"):
                if not raw.endswith("'"):
                    raise ValueError('Незакрытая кавычка у ' + key + '.')
                return raw[1:-1].replace("\\'", "'")
            if raw.startswith('"'):
                try:
                    value = json.loads(raw)
                    if not isinstance(value, str):
                        raise ValueError
                    return value
                except ValueError:
                    raise ValueError('Для ' + key + ' используйте литеральное значение в одинарных кавычках без комментария в конце строки.') from None
            return raw

        raw, legacy = setting('WHEEL_ACCESS_TOKENS'), setting('WHEEL_ACCESS_TOKEN')
        tokens = parse_access_tokens(raw, legacy)
        if args.name in tokens:
            raise ValueError('Токен с таким именем уже существует. Он не изменён. Для смены используйте rotate_access_token.py --name ' + args.name + '.')
        token = secrets.token_hex(32)
        while token in tokens.values():
            token = secrets.token_hex(32)
        tokens[args.name] = token
        # Validate capacity and names again before changing the file.
        value = json.dumps(tokens, separators=(',', ':'))
        parse_access_tokens(value)
        encoded = "WHEEL_ACCESS_TOKENS='" + value.replace("'", "\\'") + "'"
        output = []
        replaced = False
        for line in lines:
            if '=' in line and line.split('=', 1)[0].strip() == 'WHEEL_ACCESS_TOKENS':
                output.append(encoded)
                replaced = True
            else:
                output.append(line)
        if not replaced:
            output.append(encoded)
        fd, temporary = tempfile.mkstemp(prefix='.env.tokens-', dir=root)
        with os.fdopen(fd, 'w') as stream:
            stream.write('\n'.join(output) + '\n')
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
        temporary = None
    except ValueError as error:
        raise SystemExit(str(error)) from None
    finally:
        if temporary is not None:
            Path(temporary).unlink(missing_ok=True)
        lock.unlink(missing_ok=True)
    print('Добавлен токен: ' + args.name)
    print('Токен для входа: ' + token)
    print('Сохранён в .env. Примените: docker compose up -d frontend')


if __name__ == '__main__':
    main()
