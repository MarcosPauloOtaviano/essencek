from io import BytesIO
import textwrap

from django.core.files.base import ContentFile
from django.core.management.base import BaseCommand
from django.utils.text import slugify
from PIL import Image, ImageDraw, ImageFont, ImageFilter

from products.models import Product, ProductImage


IMAGE_ALT_PREFIX = 'Imagem demonstrativa gerada'
SIZE = 1200


PALETTES = {
    'perfume': {
        'bg': (255, 249, 244),
        'panel': (248, 200, 220),
        'accent': (17, 17, 17),
        'muted': (150, 108, 125),
        'glass': (255, 255, 255, 180),
    },
    'kbeauty': {
        'bg': (255, 250, 247),
        'panel': (238, 247, 242),
        'accent': (17, 17, 17),
        'muted': (116, 145, 129),
        'glass': (255, 255, 255, 190),
    },
    'tech': {
        'bg': (246, 248, 250),
        'panel': (219, 230, 238),
        'accent': (17, 17, 17),
        'muted': (77, 92, 105),
        'glass': (255, 255, 255, 200),
    },
    'default': {
        'bg': (255, 249, 244),
        'panel': (238, 238, 238),
        'accent': (17, 17, 17),
        'muted': (120, 120, 120),
        'glass': (255, 255, 255, 190),
    },
}


def load_font(size, bold=False):
    candidates = [
        'C:/Windows/Fonts/segoeuib.ttf' if bold else 'C:/Windows/Fonts/segoeui.ttf',
        'C:/Windows/Fonts/arialbd.ttf' if bold else 'C:/Windows/Fonts/arial.ttf',
        'C:/Windows/Fonts/calibrib.ttf' if bold else 'C:/Windows/Fonts/calibri.ttf',
    ]
    for path in candidates:
        try:
            return ImageFont.truetype(path, size)
        except OSError:
            continue
    return ImageFont.load_default()


def product_kind(product):
    text = f'{product.name} {product.short_description} {product.description} {product.category.slug if product.category else ""}'.casefold()
    if product.is_fractioned or 'fracionado' in text:
        return 'fractioned'
    if 'perfume' in text or 'parfum' in text or 'splash' in text or 'eau de' in text:
        return 'perfume'
    if any(token in text for token in ['serum', 'sérum', 'snail', 'cream', 'creme', 'mask', 'máscara', 'cleanser', 'sun', 'probiotics', 'lip']):
        return 'kbeauty'
    if any(token in text for token in ['fone', 'smartwatch', 'iphone', 'carregador', 'caixa de som', 'bluetooth', 'usb']):
        return 'tech'
    if product.category and product.category.slug == 'beleza-coreana':
        return 'kbeauty'
    if product.category and product.category.slug == 'eletronicos':
        return 'tech'
    return 'default'


def palette_for(kind):
    if kind in ('perfume', 'fractioned'):
        return PALETTES['perfume']
    if kind == 'kbeauty':
        return PALETTES['kbeauty']
    if kind == 'tech':
        return PALETTES['tech']
    return PALETTES['default']


def add_soft_background(draw, palette):
    bg = palette['bg']
    panel = palette['panel']
    for y in range(SIZE):
        t = y / SIZE
        color = tuple(int(bg[i] * (1 - t) + panel[i] * t) for i in range(3))
        draw.line([(0, y), (SIZE, y)], fill=color)


def rounded(draw, box, radius, fill, outline=None, width=1):
    draw.rounded_rectangle(box, radius=radius, fill=fill, outline=outline, width=width)


def centered_text(draw, xy, text, font, fill):
    bbox = draw.textbbox((0, 0), text, font=font)
    draw.text((xy[0] - (bbox[2] - bbox[0]) / 2, xy[1] - (bbox[3] - bbox[1]) / 2), text, font=font, fill=fill)


def draw_perfume(draw, palette):
    accent = palette['accent']
    muted = palette['muted']
    glass = palette['glass']
    rounded(draw, (405, 330, 795, 850), 56, fill=glass, outline=(230, 210, 218), width=4)
    rounded(draw, (480, 250, 720, 360), 26, fill=(245, 232, 238), outline=(220, 190, 204), width=3)
    rounded(draw, (535, 195, 665, 265), 18, fill=accent, outline=None)
    rounded(draw, (485, 610, 715, 725), 28, fill=(255, 249, 244), outline=(235, 214, 222), width=2)
    draw.line((455, 385, 745, 820), fill=(255, 255, 255), width=5)
    draw.ellipse((335, 770, 865, 890), fill=(220, 190, 204, 60))
    centered_text(draw, (600, 670), 'EAU DE PARFUM', load_font(31, True), muted)


def draw_fractioned(draw, palette):
    accent = palette['accent']
    muted = palette['muted']
    for index, x in enumerate([395, 510, 625, 740]):
        h = 360 + index * 28
        rounded(draw, (x, 820 - h, x + 82, 820), 34, fill=(255, 255, 255, 205), outline=(222, 198, 208), width=3)
        rounded(draw, (x + 21, 820 - h - 48, x + 61, 820 - h + 12), 10, fill=accent)
        draw.line((x + 18, 820 - h + 90, x + 64, 820 - 40), fill=(248, 200, 220), width=7)
    draw.ellipse((330, 795, 870, 900), fill=(220, 190, 204, 70))
    centered_text(draw, (600, 625), 'DECANTS', load_font(42, True), muted)


def draw_kbeauty(draw, palette, product):
    accent = palette['accent']
    muted = palette['muted']
    text = product.name.casefold()
    if any(token in text for token in ['cream', 'creme', 'lip']):
        draw.ellipse((365, 465, 835, 835), fill=(255, 255, 255, 225), outline=(215, 230, 220), width=4)
        rounded(draw, (405, 380, 795, 545), 58, fill=palette['panel'], outline=(215, 230, 220), width=3)
        centered_text(draw, (600, 635), 'CREAM', load_font(44, True), muted)
    elif any(token in text for token in ['mask', 'máscara']):
        rounded(draw, (360, 330, 840, 840), 38, fill=(255, 255, 255, 225), outline=(215, 230, 220), width=4)
        rounded(draw, (420, 500, 780, 650), 30, fill=palette['panel'], outline=None)
        centered_text(draw, (600, 575), 'SHEET MASK', load_font(37, True), muted)
    else:
        rounded(draw, (455, 275, 745, 850), 70, fill=(255, 255, 255, 225), outline=(215, 230, 220), width=4)
        rounded(draw, (520, 205, 680, 295), 22, fill=accent)
        rounded(draw, (500, 560, 700, 710), 26, fill=palette['panel'], outline=None)
        centered_text(draw, (600, 635), 'SKINCARE', load_font(36, True), muted)
    draw.ellipse((335, 805, 865, 905), fill=(190, 218, 204, 70))


def draw_tech(draw, palette, product):
    accent = palette['accent']
    muted = palette['muted']
    text = product.name.casefold()
    if 'fone' in text:
        draw.arc((330, 285, 870, 845), start=190, end=350, fill=accent, width=38)
        rounded(draw, (300, 560, 430, 790), 52, fill=(255, 255, 255), outline=(190, 202, 212), width=4)
        rounded(draw, (770, 560, 900, 790), 52, fill=(255, 255, 255), outline=(190, 202, 212), width=4)
        centered_text(draw, (600, 805), 'AUDIO', load_font(39, True), muted)
    elif 'carregador' in text:
        rounded(draw, (405, 375, 795, 790), 58, fill=(255, 255, 255), outline=(190, 202, 212), width=4)
        draw.rectangle((500, 310, 540, 395), fill=accent)
        draw.rectangle((660, 310, 700, 395), fill=accent)
        centered_text(draw, (600, 590), 'USB-C', load_font(52, True), muted)
    elif 'caixa de som' in text:
        rounded(draw, (300, 430, 900, 760), 92, fill=(30, 35, 40), outline=(120, 135, 145), width=5)
        draw.ellipse((370, 495, 610, 735), fill=(65, 75, 84), outline=(180, 194, 204), width=5)
        draw.ellipse((650, 520, 825, 695), fill=(65, 75, 84), outline=(180, 194, 204), width=4)
        centered_text(draw, (600, 825), 'SPEAKER', load_font(38, True), muted)
    else:
        rounded(draw, (430, 265, 770, 840), 86, fill=(255, 255, 255), outline=(185, 200, 210), width=5)
        rounded(draw, (470, 325, 730, 780), 56, fill=(23, 28, 33), outline=None)
        centered_text(draw, (600, 555), 'TECH', load_font(54, True), (255, 255, 255))
    draw.ellipse((320, 810, 880, 905), fill=(180, 193, 204, 85))


def draw_default_product(draw, palette):
    rounded(draw, (380, 345, 820, 820), 54, fill=(255, 255, 255, 220), outline=(220, 220, 220), width=4)
    centered_text(draw, (600, 585), 'PRODUTO', load_font(42, True), palette['muted'])


def add_labels(draw, product, palette):
    accent = palette['accent']
    muted = palette['muted']
    brand = product.display_brand or 'Essence K'
    category = product.category.name if product.category else 'Produto'
    title_font = load_font(48, True)
    brand_font = load_font(28, True)
    note_font = load_font(24)
    small_font = load_font(20)

    centered_text(draw, (600, 110), brand.upper()[:34], brand_font, muted)
    wrapped = textwrap.wrap(product.name, width=24)
    y = 930
    for line in wrapped[:3]:
        centered_text(draw, (600, y), line, title_font, accent)
        y += 58
    centered_text(draw, (600, 1110), category, note_font, muted)
    centered_text(draw, (600, 1160), 'Imagem demonstrativa - substitua por foto real no painel', small_font, (150, 150, 150))


def create_image(product):
    kind = product_kind(product)
    palette = palette_for(kind)
    image = Image.new('RGB', (SIZE, SIZE), palette['bg'])
    draw = ImageDraw.Draw(image, 'RGBA')
    add_soft_background(draw, palette)
    draw.ellipse((-120, -90, 470, 480), fill=(255, 255, 255, 85))
    draw.ellipse((760, 90, 1320, 650), fill=(255, 255, 255, 55))
    draw.ellipse((120, 760, 500, 1120), fill=(*palette['panel'], 75))

    if kind == 'perfume':
        draw_perfume(draw, palette)
    elif kind == 'fractioned':
        draw_fractioned(draw, palette)
    elif kind == 'kbeauty':
        draw_kbeauty(draw, palette, product)
    elif kind == 'tech':
        draw_tech(draw, palette, product)
    else:
        draw_default_product(draw, palette)

    add_labels(draw, product, palette)
    return image.filter(ImageFilter.UnsharpMask(radius=1.2, percent=105, threshold=3))


class Command(BaseCommand):
    help = 'Gera imagens demonstrativas locais e coerentes para produtos da vitrine.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--only-missing',
            action='store_true',
            help='Cria imagem apenas para produtos sem foto.',
        )

    def handle(self, *args, **options):
        only_missing = options['only_missing']
        created = 0
        updated = 0
        skipped = 0

        for product in Product.objects.select_related('category', 'brand_fk').prefetch_related('images').order_by('name'):
            if only_missing and product.images.exists():
                skipped += 1
                continue

            image = create_image(product)
            output = BytesIO()
            image.save(output, format='JPEG', quality=88, optimize=True, progressive=True)
            output.seek(0)

            ProductImage.objects.filter(product=product, is_main=True).update(is_main=False)
            generated = product.images.filter(alt_text__startswith=IMAGE_ALT_PREFIX).first()
            if generated:
                updated += 1
            else:
                generated = ProductImage(product=product)
                created += 1

            generated.alt_text = f'{IMAGE_ALT_PREFIX}: {product.name}'
            generated.is_main = True
            generated.order = 0
            filename = f'catalogo-{slugify(product.slug or product.name)}.jpg'
            generated.image.save(filename, ContentFile(output.read()), save=True)
            self.stdout.write(f'OK {product.name}')

        self.stdout.write(self.style.SUCCESS(
            f'Imagens sincronizadas. Criadas: {created}. Atualizadas: {updated}. Puladas: {skipped}.'
        ))
