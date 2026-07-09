import mimetypes
from pathlib import PurePosixPath

from django.conf import settings
from django.core.files.base import ContentFile
from django.core.files.storage import FileSystemStorage, Storage
from django.utils._os import safe_join
from django.utils.deconstruct import deconstructible
from django.utils.encoding import filepath_to_uri


@deconstructible
class PersistentMediaStorage(Storage):
    """Store new media in the database, with filesystem fallback for bundled files."""

    def __init__(self, location=None, base_url=None):
        self.location = str(location or settings.MEDIA_ROOT)
        self.base_url = base_url or settings.MEDIA_URL
        self.filesystem = FileSystemStorage(location=self.location, base_url=self.base_url)

    def _clean_name(self, name):
        normalized = PurePosixPath(str(name).replace('\\', '/')).as_posix().lstrip('/')
        if normalized.startswith('../') or '/..' in normalized:
            raise ValueError('Caminho de arquivo inválido.')
        return normalized

    def _model(self):
        from core.models import StoredMediaFile
        return StoredMediaFile

    def _open(self, name, mode='rb'):
        clean_name = self._clean_name(name)
        record = self._model().objects.filter(name=clean_name).first()
        if record:
            return ContentFile(bytes(record.data), name=clean_name)
        return self.filesystem.open(clean_name, mode)

    def _save(self, name, content):
        clean_name = self._clean_name(name)
        if hasattr(content, 'seek'):
            content.seek(0)
        if hasattr(content, 'chunks'):
            data = b''.join(chunk for chunk in content.chunks())
        else:
            data = content.read()
        content_type = getattr(content, 'content_type', '') or mimetypes.guess_type(clean_name)[0] or ''
        self._model().objects.update_or_create(
            name=clean_name,
            defaults={
                'content_type': content_type[:120],
                'size': len(data),
                'data': data,
            },
        )
        return clean_name

    def delete(self, name):
        clean_name = self._clean_name(name)
        self._model().objects.filter(name=clean_name).delete()
        if self.filesystem.exists(clean_name):
            self.filesystem.delete(clean_name)

    def exists(self, name):
        clean_name = self._clean_name(name)
        return self._model().objects.filter(name=clean_name).exists() or self.filesystem.exists(clean_name)

    def size(self, name):
        clean_name = self._clean_name(name)
        record = self._model().objects.filter(name=clean_name).only('size').first()
        if record:
            return record.size
        return self.filesystem.size(clean_name)

    def url(self, name):
        clean_name = self._clean_name(name)
        return self.base_url.rstrip('/') + '/' + filepath_to_uri(clean_name)

    def path(self, name):
        return safe_join(self.location, self._clean_name(name))

    def get_created_time(self, name):
        clean_name = self._clean_name(name)
        record = self._model().objects.filter(name=clean_name).only('created_at').first()
        if record:
            return record.created_at
        return self.filesystem.get_created_time(clean_name)

    def get_modified_time(self, name):
        clean_name = self._clean_name(name)
        record = self._model().objects.filter(name=clean_name).only('updated_at').first()
        if record:
            return record.updated_at
        return self.filesystem.get_modified_time(clean_name)
