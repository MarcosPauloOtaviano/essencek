import mimetypes
import shutil
from io import BytesIO
from pathlib import Path, PurePosixPath

from django.conf import settings
from django.core.files.storage import default_storage
from django.http import FileResponse, Http404
from PIL import Image, ImageOps, UnidentifiedImageError


THUMBNAIL_WIDTHS = frozenset({160, 480, 960})
MAX_THUMBNAIL_SOURCE_SIZE = 15 * 1024 * 1024
MAX_THUMBNAIL_PIXELS = 24_000_000
THUMBNAIL_JPEG_QUALITY = 82


def _clean_media_path(path):
    raw_path = str(path or '').replace('\\', '/')
    if not raw_path or raw_path.startswith('/'):
        raise Http404('Arquivo nao encontrado.')
    normalized = PurePosixPath(raw_path)
    if any(part in ('', '.', '..') for part in normalized.parts):
        raise Http404('Arquivo nao encontrado.')
    return normalized.as_posix()


def _try_lazy_copy(path):
    """Copy a media file from bundle source to runtime dir on first access."""
    media_root = Path(settings.MEDIA_ROOT)
    target = media_root / path
    if target.exists():
        return
    source_dir = getattr(settings, 'BASE_DIR', None)
    if not source_dir:
        return
    source = Path(source_dir) / 'media' / path
    if not source.exists():
        return
    target.parent.mkdir(parents=True, exist_ok=True)
    try:
        shutil.copy2(source, target)
    except OSError:
        pass


def _requested_thumbnail_width(request):
    value = request.GET.get('w')
    if value is None:
        return None
    try:
        width = int(value)
    except (TypeError, ValueError) as exc:
        raise Http404('Tamanho de imagem invalido.') from exc
    if width not in THUMBNAIL_WIDTHS:
        raise Http404('Tamanho de imagem invalido.')
    return width


def _build_thumbnail(media_file, width):
    source_size = getattr(media_file, 'size', None)
    if source_size is not None and source_size > MAX_THUMBNAIL_SOURCE_SIZE:
        raise ValueError('Imagem excede o limite para miniaturas.')

    try:
        with Image.open(media_file) as source:
            if source.width * source.height > MAX_THUMBNAIL_PIXELS:
                raise ValueError('Imagem excede o limite de pixels para miniaturas.')
            if getattr(source, 'is_animated', False):
                raise ValueError('Imagem animada nao deve ser convertida.')

            source_format = (source.format or '').upper()
            image = ImageOps.exif_transpose(source)
            image.thumbnail((width, width), Image.Resampling.LANCZOS)

            output = BytesIO()
            if source_format == 'PNG':
                if image.mode not in ('RGB', 'RGBA', 'L', 'LA', 'P'):
                    image = image.convert('RGBA')
                image.save(output, format='PNG', optimize=True, compress_level=9)
                content_type = 'image/png'
            elif source_format == 'WEBP':
                image.save(
                    output,
                    format='WEBP',
                    quality=THUMBNAIL_JPEG_QUALITY,
                    method=6,
                )
                content_type = 'image/webp'
            else:
                if image.mode != 'RGB':
                    image = image.convert('RGB')
                image.save(
                    output,
                    format='JPEG',
                    quality=THUMBNAIL_JPEG_QUALITY,
                    optimize=True,
                    progressive=True,
                )
                content_type = 'image/jpeg'
    except (OSError, UnidentifiedImageError, Image.DecompressionBombError) as exc:
        raise ValueError('Imagem invalida para miniatura.') from exc

    return output.getvalue(), content_type


def _original_media_response(path):
    try:
        media_file = default_storage.open(path, 'rb')
    except (OSError, ValueError):
        raise Http404('Arquivo nao encontrado.')
    content_type = mimetypes.guess_type(path)[0] or 'application/octet-stream'
    return FileResponse(media_file, content_type=content_type)


def serve_media_file(request, path):
    path = _clean_media_path(path)
    _try_lazy_copy(path)
    width = _requested_thumbnail_width(request)

    if width is None:
        response = _original_media_response(path)
    else:
        try:
            with default_storage.open(path, 'rb') as media_file:
                data, content_type = _build_thumbnail(media_file, width)
        except (OSError, ValueError):
            response = _original_media_response(path)
        else:
            response = FileResponse(BytesIO(data), content_type=content_type)
    response['Cache-Control'] = 'public, s-maxage=31536000, max-age=31536000, immutable'
    return response
