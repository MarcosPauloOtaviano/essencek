import hashlib
import hmac

from django.conf import settings


def make_pii_lookup(value):
    """Return a deterministic blind index without storing the source value."""
    normalized = str(value or '').strip()
    if not normalized:
        return None
    key = settings.PII_HASH_KEY.encode('utf-8')
    return hmac.new(key, normalized.encode('utf-8'), hashlib.sha256).hexdigest()
