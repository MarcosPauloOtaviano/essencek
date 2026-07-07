import logging
from io import BytesIO
from urllib.parse import urlparse

import requests
from django.core.files.uploadedfile import InMemoryUploadedFile

from .image_utils import build_web_product_image

logger = logging.getLogger('products.gtin')

ALLOWED_SCHEMES = {'http', 'https'}
ALLOWED_CONTENT_TYPES = {'image/jpeg', 'image/png', 'image/webp', 'image/gif'}
MAX_DOWNLOAD_BYTES = 15 * 1024 * 1024
DOWNLOAD_TIMEOUT = 15


def download_and_process_image(url, filename_stem='produto'):
    parsed = urlparse(url)
    if parsed.scheme not in ALLOWED_SCHEMES:
        logger.warning('Image download blocked: scheme %s not allowed', parsed.scheme)
        return None

    try:
        resp = requests.get(
            url,
            timeout=DOWNLOAD_TIMEOUT,
            headers={'User-Agent': 'EssenceK/1.0'},
            stream=True,
        )
        resp.raise_for_status()
    except requests.RequestException as exc:
        logger.warning('Image download failed for %s: %s', url, exc)
        return None

    content_type = resp.headers.get('Content-Type', '').split(';')[0].strip().lower()
    if content_type not in ALLOWED_CONTENT_TYPES:
        logger.warning('Image download blocked: content type %s not allowed', content_type)
        return None

    content_length = int(resp.headers.get('Content-Length', 0))
    if content_length > MAX_DOWNLOAD_BYTES:
        logger.warning('Image download blocked: size %d exceeds limit', content_length)
        return None

    data = BytesIO()
    downloaded = 0
    for chunk in resp.iter_content(chunk_size=65536):
        downloaded += len(chunk)
        if downloaded > MAX_DOWNLOAD_BYTES:
            logger.warning('Image download aborted: exceeded max size during streaming')
            return None
        data.write(chunk)

    data.seek(0)

    ext_map = {
        'image/jpeg': '.jpg',
        'image/png': '.png',
        'image/webp': '.webp',
        'image/gif': '.gif',
    }
    ext = ext_map.get(content_type, '.jpg')
    safe_name = f'{filename_stem}{ext}'

    uploaded = InMemoryUploadedFile(
        file=data,
        field_name='image',
        name=safe_name,
        content_type=content_type,
        size=downloaded,
        charset=None,
    )

    try:
        return build_web_product_image(uploaded)
    except Exception as exc:
        logger.warning('Image processing failed for %s: %s', url, exc)
        return None
