import re
from decimal import Decimal, ROUND_HALF_UP

_CONTROL_CHARS_RE = re.compile(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]')
_EXCESSIVE_WHITESPACE_RE = re.compile(r'[ \t]{2,}')


def sanitize_text(value):
    if not value:
        return value
    value = _CONTROL_CHARS_RE.sub('', value)
    value = _EXCESSIVE_WHITESPACE_RE.sub(' ', value)
    return value.strip()


def money(value):
    """Round a Decimal to 2 decimal places (standard currency rounding)."""
    if value is None:
        return None
    return value.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)


def image_url_if_exists(image_field):
    """Return the URL of an ImageField if the file exists on storage, else ''."""
    try:
        if image_field and image_field.name and image_field.storage.exists(image_field.name):
            return image_field.url
    except (OSError, ValueError):
        return ''
    return ''
