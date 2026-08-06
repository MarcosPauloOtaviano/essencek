import mimetypes
import shutil
from pathlib import Path, PurePosixPath

from django.conf import settings
from django.core.files.storage import default_storage
from django.http import FileResponse, Http404


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


def serve_media_file(request, path):
    path = _clean_media_path(path)
    _try_lazy_copy(path)

    try:
        media_file = default_storage.open(path, 'rb')
    except (OSError, ValueError):
        raise Http404('Arquivo nao encontrado.')
    content_type = mimetypes.guess_type(path)[0] or 'application/octet-stream'
    response = FileResponse(media_file, content_type=content_type)
    response['Cache-Control'] = 'public, s-maxage=31536000, max-age=31536000, immutable'
    return response
