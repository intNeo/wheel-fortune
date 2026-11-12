#!/usr/bin/env python3
"""Rotate or delete one access token in .env. No secret values in stdout."""
import argparse
import json
import os
from pathlib import Path
import secrets
import sys
import tempfile


def main():
    parser = argparse.ArgumentParser(description='Смена или удаление токена доступа в .env')
    parser.add_argument('--name', help='Имя токена в WHEEL_ACCESS_TOKENS')
    parser.add_argument('--delete', action='store_true', help='Удалить токен вместо смены значения; требуется --name')
    args = parser.parse_args()
    if args.delete and not args.name:
        parser.error('Для удаления явно укажите --name ИМЯ.')
    root = Path(__file__).resolve().parent
    path = root / '.env'
    if not path.is_file():
        raise SystemExit('Не найден .env. Сначала выполните python3 setup_env.py.')
    sys.path.insert(0, str(root / 'frontend'))
    try:
        from wheel.access_tokens import parse_access_tokens
    except ImportError:
        raise SystemExit('Сначала установите поддержку WHEEL_ACCESS_TOKENS.') from None
    lock = root / '.env.access-tokens.lock'
    try:
        fd = os.open(lock, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError:
        raise SystemExit('Другой процесс изменяет токены. Повторите позже. Если он аварийно завершился, удалите оставшийся .env.access-tokens.lock.') from None
    temporary = None
    name = args.name or 'default'
    try:
        os.close(fd)
        lines = path.read_text().splitlines()

        def setting(key):
            matches = [line.split('=', 1)[1].strip() for line in lines
                       if '=' in line and line.split('=', 1)[0].strip() == key]
            if len(matches) > 1:
                raise ValueError('Удалите дублирующиеся строки ' + key + ' из .env.')
            raw = matches[0] if matches else ''
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
                    raise ValueError('Используйте литеральное значение ' + key + ' в одинарных кавычках без комментария после значения.') from None
            return raw

        raw, legacy = setting('WHEEL_ACCESS_TOKENS'), setting('WHEEL_ACCESS_TOKEN')
        tokens = parse_access_tokens(raw, legacy)
        if raw.strip() and not args.name:
            raise ValueError('В режиме нескольких токенов укажите --name ИМЯ.')
        if name not in tokens:
            raise ValueError('Токен с таким именем не найден. .env не изменён.')
        if args.delete:
            if len(tokens) == 1:
                raise ValueError('Нельзя удалить последний токен. Сначала добавьте другой.')
            del tokens[name]
        else:
            replacement = secrets.token_hex(32)
            while replacement in tokens.values():
                replacement = secrets.token_hex(32)
            tokens[name] = replacement
        if raw.strip():
            value = json.dumps(tokens, separators=(',', ':'))
            parse_access_tokens(value)
            key = 'WHEEL_ACCESS_TOKENS'
            encoded = "'" + value.replace("'", "\\'") + "'"
        else:
            key, encoded = 'WHEEL_ACCESS_TOKEN', tokens['default']
        output = []
        for line in lines:
            if '=' in line and line.split('=', 1)[0].strip() == key:
                output.append(key + '=' + encoded)
            else:
                output.append(line)
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
    print(('Удалён токен: ' if args.delete else 'Изменён токен: ') + name)
    print('Примените: docker compose up -d frontend')
    if not args.delete:
        print('Новое значение сохранено в .env.')


if __name__ == '__main__':
    main()
