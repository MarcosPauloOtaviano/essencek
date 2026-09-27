from django.db import migrations


def scrub_plaintext_identity(apps, schema_editor):
    from accounts.validators import normalize_cpf, normalize_whatsapp
    from core.pii import make_pii_lookup

    User = apps.get_model('accounts', 'User')
    table = schema_editor.connection.ops.quote_name(User._meta.db_table)
    with schema_editor.connection.cursor() as cursor:
        cursor.execute(
            f'SELECT id, cpf, whatsapp FROM {table} WHERE cpf IS NOT NULL OR whatsapp IS NOT NULL'
        )
        rows = cursor.fetchall()

    for user_id, raw_cpf, raw_whatsapp in rows:
        cpf = normalize_cpf(raw_cpf)
        whatsapp = normalize_whatsapp(raw_whatsapp)
        updates = {
            'cpf_lookup': make_pii_lookup(cpf),
            'whatsapp_lookup': make_pii_lookup(whatsapp),
        }
        if cpf:
            updates['cpf_encrypted'] = cpf
        if whatsapp:
            updates['whatsapp_encrypted'] = whatsapp
        User.objects.filter(pk=user_id).update(**updates)

    with schema_editor.connection.cursor() as cursor:
        cursor.execute(f'UPDATE {table} SET cpf = NULL, whatsapp = NULL')


def restore_plaintext_identity(apps, schema_editor):
    User = apps.get_model('accounts', 'User')
    table = schema_editor.connection.ops.quote_name(User._meta.db_table)
    with schema_editor.connection.cursor() as cursor:
        for user in User.objects.all().iterator():
            cursor.execute(
                f'UPDATE {table} SET cpf = %s, whatsapp = %s WHERE id = %s',
                [user.cpf_encrypted or None, user.whatsapp_encrypted or None, user.pk],
            )


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0006_remove_plaintext_identity_state'),
    ]

    operations = [
        migrations.RunPython(scrub_plaintext_identity, restore_plaintext_identity),
    ]
