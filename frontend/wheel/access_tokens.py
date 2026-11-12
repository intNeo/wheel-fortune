"""Parse named access tokens without exposing credentials in configuration errors."""
import json
import re

TOKEN_NAME = re.compile(r'^[A-Za-z0-9_.-]{1,64}$')

def _unique_pairs(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError('Duplicate token name')
        result[key] = value
    return result

def parse_access_tokens(raw, legacy=''):
    """A nonempty JSON setting overrides the single-token legacy setting."""
    if raw.strip():
        try:
            tokens = json.loads(raw, object_pairs_hook=_unique_pairs)
        except (ValueError, TypeError):
            raise ValueError('WHEEL_ACCESS_TOKENS must be a valid JSON object with unique names') from None
    else:
        tokens = {'default': legacy} if legacy else {}
    if not isinstance(tokens, dict) or not 1 <= len(tokens) <= 100:
        raise ValueError('Configure 1 to 100 named access tokens')
    seen = set()
    for name, value in tokens.items():
        if not isinstance(name, str) or not TOKEN_NAME.fullmatch(name):
            raise ValueError('Token names must use 1 to 64 ASCII letters, digits, dots, hyphens or underscores')
        if not isinstance(value, str) or not 32 <= len(value) <= 256 or not value.isascii() or any(c.isspace() for c in value):
            raise ValueError('Each access token must contain 32 to 256 ASCII characters without whitespace')
        if value in seen:
            raise ValueError('Access token values must be distinct')
        seen.add(value)
    return tokens
