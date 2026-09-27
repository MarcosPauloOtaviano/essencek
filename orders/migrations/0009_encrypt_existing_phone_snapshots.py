from django.db import migrations


def encrypt_phones(apps, schema_editor):
    from accounts.validators import normalize_whatsapp
    from core.pii import make_pii_lookup

    for model_name, field in [('Order', 'customer_whatsapp'), ('PreOrderRequest', 'whatsapp')]:
        Model = apps.get_model('orders', model_name)
        objects = Model.objects.using(schema_editor.connection.alias)
        for row in objects.select_for_update().all():
            phone = normalize_whatsapp(getattr(row, field)) or ''
            objects.filter(pk=row.pk).update(**{field: phone, 'phone_lookup': make_pii_lookup(phone)})


def decrypt_phones(apps, schema_editor):
    for model_name, field in [('Order', 'customer_whatsapp'), ('PreOrderRequest', 'whatsapp')]:
        Model = apps.get_model('orders', model_name)
        table = schema_editor.quote_name(Model._meta.db_table)
        column = schema_editor.quote_name(field)
        with schema_editor.connection.cursor() as cursor:
            for row in Model.objects.using(schema_editor.connection.alias).select_for_update().all():
                cursor.execute(f'UPDATE {table} SET {column} = %s WHERE id = %s', [getattr(row, field), row.pk])


class Migration(migrations.Migration):
    dependencies = [('orders', '0008_encrypted_phone_snapshots')]
    operations = [migrations.RunPython(encrypt_phones, decrypt_phones)]
