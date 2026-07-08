import shutil
import sqlite3
import sys
from pathlib import Path

import django
from django.contrib.auth.hashers import make_password
from django.utils.text import slugify
from django.utils import timezone


ROOT = Path(__file__).resolve().parents[1]
SOURCE_DB = ROOT / 'db.sqlite3'
TARGET_DB = ROOT / 'vercel_db.sqlite3'
MEDIA_PRODUCTS = ROOT / 'media' / 'products'


def delete_if_exists(cursor, table_name):
    cursor.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
        (table_name,),
    )
    if cursor.fetchone():
        cursor.execute(f'DELETE FROM {table_name}')


def reset_sequence(cursor, table_name):
    cursor.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='sqlite_sequence'",
    )
    if cursor.fetchone():
        cursor.execute('DELETE FROM sqlite_sequence WHERE name=?', (table_name,))


def find_product_image(name, slug):
    if not MEDIA_PRODUCTS.exists():
        return ''

    folder_map = {
        folder.name: folder
        for folder in MEDIA_PRODUCTS.iterdir()
        if folder.is_dir()
    }
    candidates = [slug, slugify(name)]
    for candidate in candidates:
        folder = folder_map.get(candidate)
        if folder:
            break
    else:
        return ''

    image_files = [
        path for path in folder.iterdir()
        if path.is_file() and path.suffix.lower() in {'.jpg', '.jpeg', '.png', '.webp'}
    ]
    if not image_files:
        return ''

    def score(path):
        filename = path.name.lower()
        if 'foto-real' in filename:
            return (0, filename)
        if 'catalogo' in filename:
            return (1, filename)
        return (2, filename)

    selected = sorted(image_files, key=score)[0]
    return str(selected.relative_to(ROOT / 'media')).replace('\\', '/')


def main():
    if not SOURCE_DB.exists():
        raise SystemExit(f'Banco local nao encontrado: {SOURCE_DB}')

    if TARGET_DB.exists():
        TARGET_DB.unlink()
    shutil.copyfile(SOURCE_DB, TARGET_DB)

    django.setup()
    password_hash = make_password('Preview123!')
    now = timezone.now().isoformat()

    with sqlite3.connect(TARGET_DB) as conn:
        cursor = conn.cursor()
        for table in [
            'accounts_user_groups',
            'accounts_user_user_permissions',
            'cart_cartitem',
            'cart_cart',
            'django_admin_log',
            'django_session',
            'orders_orderitem',
            'orders_order',
            'orders_preorderrequest',
            'otp_static_statictoken',
            'otp_static_staticdevice',
            'otp_totp_totpdevice',
            'payments_payment',
            'shipping_shippingrate',
            'two_factor_phonedevice',
            'accounts_user',
        ]:
            delete_if_exists(cursor, table)
            reset_sequence(cursor, table)

        cursor.execute(
            """
            INSERT INTO accounts_user (
                password, last_login, is_superuser, username, first_name, last_name,
                email, is_staff, is_active, date_joined, full_name, whatsapp, cep,
                address, address_number, address_complement, neighborhood, city,
                state, cpf, cpf_encrypted, whatsapp_encrypted
            )
            VALUES (?, NULL, 1, ?, '', '', ?, 1, 1, ?, ?, NULL, '', '', '', '', '', '', '', NULL, '', '')
            """,
            (
                password_hash,
                'admin@essencekimportados.com',
                'admin@essencekimportados.com',
                now,
                'Admin Preview',
            ),
        )

        cursor.execute(
            """
            UPDATE core_storesettings
               SET whatsapp='',
                   email='',
                   cep_origem='',
                   payment_gateway='sandbox'
             WHERE id=1
            """
        )

        cursor.execute('SELECT COUNT(*) FROM products_productimage')
        if cursor.fetchone()[0] == 0:
            cursor.execute('SELECT id, name, slug FROM products_product ORDER BY id')
            products = cursor.fetchall()
            for product_id, name, slug in products:
                image_path = find_product_image(name, slug)
                if not image_path:
                    continue
                cursor.execute(
                    """
                    INSERT INTO products_productimage (image, alt_text, is_main, "order", product_id)
                    VALUES (?, ?, 1, 0, ?)
                    """,
                    (image_path, name, product_id),
                )
        conn.commit()

    print(f'Banco de preview criado: {TARGET_DB}')


if __name__ == '__main__':
    sys.path.insert(0, str(ROOT))
    import os

    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'paraguashopping.settings.development')
    main()
