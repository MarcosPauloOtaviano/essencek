"""
Generate product placeholder images using Pillow.
Creates professional-looking gradient images with product icons/text
for each product in the database.
"""
import os
from django.core.management.base import BaseCommand
from django.core.files.base import ContentFile
from django.conf import settings
from PIL import Image, ImageDraw, ImageFont, ImageFilter
from io import BytesIO
import math


# Color palettes per category
PALETTES = {
    'perfumes': {
        'bg_start': (232, 207, 195),  # nude-rose
        'bg_end': (184, 149, 122),    # suede-beige
        'accent': (43, 26, 20),       # dark-brown
        'overlay': (255, 240, 230),
    },
    'beleza-coreana': {
        'bg_start': (248, 241, 236),  # cream
        'bg_end': (232, 207, 195),    # nude-rose
        'accent': (184, 149, 122),    # suede-beige
        'overlay': (255, 250, 245),
    },
    'eletronicos': {
        'bg_start': (43, 26, 20),     # dark-brown
        'bg_end': (80, 50, 35),       # medium-brown
        'accent': (232, 207, 195),    # nude-rose
        'overlay': (60, 40, 30),
    },
    'default': {
        'bg_start': (248, 241, 236),
        'bg_end': (232, 207, 195),
        'accent': (43, 26, 20),
        'overlay': (255, 245, 238),
    }
}

PRODUCT_ICONS = {
    'perfume-importado-premium': 'PERFUME',
    'body-splash-luxo': 'SPLASH',
    'perfume-feminino-elegance': 'PARFUM',
    'serum-facial-coreano': 'SERUM',
    'mascara-facial-hidratante': 'MASK',
    'creme-clareador-coreano': 'CREAM',
    'fone-bluetooth-premium': 'HEADPHONES',
    'smartwatch-ultra': 'WATCH',
    'caixa-de-som-portatil': 'SPEAKER',
}


def create_gradient(size, color_start, color_end, direction='diagonal'):
    img = Image.new('RGB', size)
    draw = ImageDraw.Draw(img)
    w, h = size
    for y in range(h):
        for x in range(w):
            if direction == 'diagonal':
                t = (x / w * 0.5 + y / h * 0.5)
            else:
                t = y / h
            r = int(color_start[0] + (color_end[0] - color_start[0]) * t)
            g = int(color_start[1] + (color_end[1] - color_start[1]) * t)
            b = int(color_start[2] + (color_end[2] - color_start[2]) * t)
            draw.point((x, y), fill=(r, g, b))
    return img


def create_product_image(product_name, category_slug, size=(800, 800)):
    palette = PALETTES.get(category_slug, PALETTES['default'])

    img = create_gradient(size, palette['bg_start'], palette['bg_end'])
    draw = ImageDraw.Draw(img)
    w, h = size

    # Draw decorative circles
    overlay = Image.new('RGBA', size, (0, 0, 0, 0))
    overlay_draw = ImageDraw.Draw(overlay)

    # Large decorative circle (product silhouette area)
    cx, cy = w // 2, h // 2
    radius = int(w * 0.3)
    overlay_draw.ellipse(
        [cx - radius, cy - radius, cx + radius, cy + radius],
        fill=(*palette['overlay'], 40)
    )

    # Smaller accent circles
    for i in range(3):
        r = int(w * (0.1 + i * 0.05))
        offset_x = int(w * 0.25 * math.cos(i * 2.1))
        offset_y = int(h * 0.25 * math.sin(i * 2.1))
        overlay_draw.ellipse(
            [cx + offset_x - r, cy + offset_y - r,
             cx + offset_x + r, cy + offset_y + r],
            fill=(*palette['overlay'], 20)
        )

    img = Image.alpha_composite(img.convert('RGBA'), overlay).convert('RGB')
    draw = ImageDraw.Draw(img)

    # Draw product label text
    icon_text = PRODUCT_ICONS.get(
        product_name.lower().replace(' ', '-'),
        product_name.split()[0].upper()[:8]
    )

    # Try to get a decent font
    font_large = None
    font_small = None
    font_paths = [
        'C:/Windows/Fonts/segoeui.ttf',
        'C:/Windows/Fonts/arial.ttf',
        'C:/Windows/Fonts/calibri.ttf',
    ]
    for fp in font_paths:
        if os.path.exists(fp):
            try:
                font_large = ImageFont.truetype(fp, 48)
                font_small = ImageFont.truetype(fp, 24)
                break
            except Exception:
                continue

    if not font_large:
        font_large = ImageFont.load_default()
        font_small = ImageFont.load_default()

    # Draw icon text centered
    accent = palette['accent']
    bbox = draw.textbbox((0, 0), icon_text, font=font_large)
    tw = bbox[2] - bbox[0]
    th = bbox[3] - bbox[1]
    draw.text((cx - tw // 2, cy - th // 2 - 20), icon_text,
              fill=(*accent, ), font=font_large)

    # Draw product name below
    short_name = product_name[:30]
    bbox2 = draw.textbbox((0, 0), short_name, font=font_small)
    tw2 = bbox2[2] - bbox2[0]
    draw.text((cx - tw2 // 2, cy + th // 2 + 20), short_name,
              fill=(*accent,), font=font_small)

    # Add subtle vignette
    vignette = Image.new('RGBA', size, (0, 0, 0, 0))
    vig_draw = ImageDraw.Draw(vignette)
    for i in range(40):
        alpha = int(i * 1.5)
        vig_draw.rectangle(
            [i, i, w - i, h - i],
            outline=(0, 0, 0, alpha)
        )
    img = Image.alpha_composite(img.convert('RGBA'), vignette).convert('RGB')

    # Apply slight blur for premium feel
    img = img.filter(ImageFilter.GaussianBlur(radius=0.5))

    return img


def create_category_default(category_slug, size=(800, 800)):
    palette = PALETTES.get(category_slug, PALETTES['default'])
    img = create_gradient(size, palette['bg_start'], palette['bg_end'], 'vertical')
    draw = ImageDraw.Draw(img)
    w, h = size

    # Category label
    labels = {
        'perfumes': 'Perfume',
        'beleza-coreana': 'Beleza',
        'eletronicos': 'Tech',
        'default': 'Produto',
    }
    label = labels.get(category_slug, 'Produto')

    font = None
    for fp in ['C:/Windows/Fonts/segoeui.ttf', 'C:/Windows/Fonts/arial.ttf']:
        if os.path.exists(fp):
            try:
                font = ImageFont.truetype(fp, 60)
                break
            except Exception:
                continue
    if not font:
        font = ImageFont.load_default()

    bbox = draw.textbbox((0, 0), label, font=font)
    tw = bbox[2] - bbox[0]
    th = bbox[3] - bbox[1]
    draw.text((w // 2 - tw // 2, h // 2 - th // 2),
              label, fill=palette['accent'], font=font)

    return img


class Command(BaseCommand):
    help = 'Gera imagens placeholder para produtos sem foto'

    def handle(self, *args, **kwargs):
        from products.models import Product, ProductImage

        # 1. Generate category default images in static
        defaults_dir = os.path.join(settings.BASE_DIR, 'static', 'img', 'defaults')
        os.makedirs(defaults_dir, exist_ok=True)

        for slug in ['perfumes', 'beleza-coreana', 'eletronicos', 'default']:
            filepath = os.path.join(defaults_dir, f'default-{slug}.jpg')
            if not os.path.exists(filepath):
                img = create_category_default(slug)
                img.save(filepath, 'JPEG', quality=85)
                self.stdout.write(f'  Criado: {filepath}')
            else:
                self.stdout.write(f'  Existe: {filepath}')

        # 2. Generate images for products without images
        products = Product.objects.all()
        created_count = 0

        for product in products:
            if product.images.exists():
                self.stdout.write(f'  Pulando (tem foto): {product.name}')
                continue

            cat_slug = product.category.slug if product.category else 'default'
            img = create_product_image(product.name, cat_slug)

            buffer = BytesIO()
            img.save(buffer, format='JPEG', quality=90)
            buffer.seek(0)

            filename = f'{product.slug}.jpg'
            product_image = ProductImage(
                product=product,
                alt_text=product.name,
                is_main=True,
                order=0
            )
            product_image.image.save(filename, ContentFile(buffer.read()), save=True)
            created_count += 1
            self.stdout.write(self.style.SUCCESS(f'  Imagem criada: {product.name}'))

        self.stdout.write(self.style.SUCCESS(
            f'\nConcluido! {created_count} imagens criadas.'
        ))
