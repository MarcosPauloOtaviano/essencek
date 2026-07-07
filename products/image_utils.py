from io import BytesIO
from pathlib import Path

from django.core.files.base import ContentFile
from django import forms
from django.utils.text import slugify
from PIL import Image, ImageOps, UnidentifiedImageError

try:
    from pillow_heif import register_heif_opener
except ImportError:  # pragma: no cover - dependency is optional at import time
    HEIF_SUPPORTED = False
else:
    register_heif_opener()
    HEIF_SUPPORTED = True


ALLOWED_IMAGE_EXTENSIONS = {'jpg', 'jpeg', 'png', 'webp', 'heic', 'heif'}
HEIF_EXTENSIONS = {'heic', 'heif'}
MAX_IMAGE_UPLOAD_SIZE = 15 * 1024 * 1024  # 15 MB
MAX_IMAGE_PIXELS = 24_000_000
MAX_STORED_IMAGE_EDGE = 1800
JPEG_QUALITY = 85

Image.MAX_IMAGE_PIXELS = MAX_IMAGE_PIXELS


def validate_product_image_upload(uploaded_file):
    ext = Path(uploaded_file.name).suffix.lower().lstrip('.')
    if ext not in ALLOWED_IMAGE_EXTENSIONS:
        allowed = ', '.join(sorted(ALLOWED_IMAGE_EXTENSIONS))
        raise forms.ValidationError(f'Formato não suportado. Use fotos em: {allowed}.')
    if ext in HEIF_EXTENSIONS and not HEIF_SUPPORTED:
        raise forms.ValidationError('Fotos HEIC/HEIF precisam da dependência pillow-heif instalada.')
    if uploaded_file.size > MAX_IMAGE_UPLOAD_SIZE:
        raise forms.ValidationError('Imagem muito grande. Máximo 15 MB por foto.')


def build_web_product_image(uploaded_file):
    validate_product_image_upload(uploaded_file)
    uploaded_file.seek(0)
    try:
        image = Image.open(uploaded_file)
        if image.width * image.height > MAX_IMAGE_PIXELS:
            raise forms.ValidationError('Imagem com resolução muito grande. Envie uma foto de até 24 megapixels.')
        image = ImageOps.exif_transpose(image)
        image.thumbnail((MAX_STORED_IMAGE_EDGE, MAX_STORED_IMAGE_EDGE), Image.Resampling.LANCZOS)

        if image.mode in ('RGBA', 'LA') or (image.mode == 'P' and 'transparency' in image.info):
            background = Image.new('RGB', image.size, (255, 255, 255))
            background.paste(image.convert('RGBA'), mask=image.convert('RGBA').getchannel('A'))
            image = background
        else:
            image = image.convert('RGB')

        output = BytesIO()
        image.save(output, format='JPEG', quality=JPEG_QUALITY, optimize=True, progressive=True)
    except (OSError, UnidentifiedImageError, Image.DecompressionBombError) as exc:
        raise forms.ValidationError('Não foi possível ler esta foto. Envie uma imagem válida.') from exc
    finally:
        uploaded_file.seek(0)

    safe_name = slugify(Path(uploaded_file.name).stem) or 'foto-produto'
    return ContentFile(output.getvalue(), name=f'{safe_name}.jpg')
