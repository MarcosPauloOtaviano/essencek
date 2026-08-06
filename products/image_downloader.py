import ipaddress
import logging
import socket
from io import BytesIO
from urllib.parse import urljoin, urlparse

import requests
from django.core.files.uploadedfile import InMemoryUploadedFile

from .image_utils import build_web_product_image

logger = logging.getLogger('products.gtin')

ALLOWED_SCHEMES = {'http', 'https'}
ALLOWED_CONTENT_TYPES = {'image/jpeg', 'image/png', 'image/webp', 'image/gif'}
MAX_DOWNLOAD_BYTES = 15 * 1024 * 1024
DOWNLOAD_TIMEOUT = 15
MAX_REDIRECTS = 3


def _is_public_image_url(url):
    parsed = urlparse(url)
    if parsed.scheme not in ALLOWED_SCHEMES or not parsed.hostname:
        return False
    if parsed.username or parsed.password:
        return False

    try:
        port = parsed.port or (443 if parsed.scheme == 'https' else 80)
        addresses = {
            item[4][0]
            for item in socket.getaddrinfo(
                parsed.hostname,
                port,
                type=socket.SOCK_STREAM,
            )
        }
    except (OSError, ValueError):
        return False

    for address in addresses:
        try:
            if not ipaddress.ip_address(address).is_global:
                return False
        except ValueError:
            return False
    return bool(addresses)


def download_and_process_image(url, filename_stem='produto'):
    if not _is_public_image_url(url):
        logger.warning('Image download blocked: URL is not a public HTTP(S) destination')
        return None

    resp = None
    try:
        current_url = url
        for redirect_count in range(MAX_REDIRECTS + 1):
            resp = requests.get(
                current_url,
                timeout=DOWNLOAD_TIMEOUT,
                headers={'User-Agent': 'EssenceK/1.0'},
                stream=True,
                allow_redirects=False,
            )
            if resp.is_redirect or resp.is_permanent_redirect:
                if redirect_count >= MAX_REDIRECTS:
                    logger.warning('Image download blocked: too many redirects')
                    return None
                next_url = urljoin(current_url, resp.headers.get('Location', ''))
                resp.close()
                if not _is_public_image_url(next_url):
                    logger.warning('Image download blocked: redirect target is not public')
                    return None
                current_url = next_url
                continue
            break
        resp.raise_for_status()
    except requests.RequestException as exc:
        if resp is not None:
            resp.close()
        logger.warning('Image download failed for %s: %s', url, exc)
        return None

    try:
        content_type = resp.headers.get('Content-Type', '').split(';')[0].strip().lower()
        if content_type not in ALLOWED_CONTENT_TYPES:
            logger.warning('Image download blocked: content type %s not allowed', content_type)
            return None

        try:
            content_length = int(resp.headers.get('Content-Length', 0))
        except (TypeError, ValueError):
            logger.warning('Image download blocked: invalid content length')
            return None
        if content_length < 0 or content_length > MAX_DOWNLOAD_BYTES:
            logger.warning('Image download blocked: size %d is invalid', content_length)
            return None

        data = BytesIO()
        downloaded = 0
        try:
            for chunk in resp.iter_content(chunk_size=65536):
                downloaded += len(chunk)
                if downloaded > MAX_DOWNLOAD_BYTES:
                    logger.warning('Image download aborted: exceeded max size during streaming')
                    return None
                data.write(chunk)
        except requests.RequestException as exc:
            logger.warning('Image download stream failed for %s: %s', url, exc)
            return None

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
    finally:
        resp.close()
