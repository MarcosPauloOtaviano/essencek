import mimetypes

from django.core.files.storage import default_storage
from django.http import FileResponse, Http404


def serve_media_file(request, path):
    try:
        exists = path and default_storage.exists(path)
    except (OSError, ValueError):
        exists = False
    if not exists:
        raise Http404('Arquivo nao encontrado.')
    content_type = mimetypes.guess_type(path)[0] or 'application/octet-stream'
    response = FileResponse(default_storage.open(path, 'rb'), content_type=content_type)
    response['Cache-Control'] = 'public, max-age=31536000, immutable'
    return response
