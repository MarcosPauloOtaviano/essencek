from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from django import template
from django.conf import settings

from core.media_views import THUMBNAIL_WIDTHS


register = template.Library()


@register.filter
def media_thumbnail(url, width):
    value = str(url or '')
    try:
        width = int(width)
    except (TypeError, ValueError):
        return value
    if not value or width not in THUMBNAIL_WIDTHS:
        return value

    parsed = urlsplit(value)
    media_url = urlsplit(settings.MEDIA_URL)
    if parsed.scheme or parsed.netloc:
        if (parsed.scheme, parsed.netloc) != (media_url.scheme, media_url.netloc):
            return value
    media_path = media_url.path or '/media/'
    if not parsed.path.startswith(media_path):
        return value

    query = dict(parse_qsl(parsed.query, keep_blank_values=True))
    query['w'] = str(width)
    return urlunsplit(parsed._replace(query=urlencode(query)))
