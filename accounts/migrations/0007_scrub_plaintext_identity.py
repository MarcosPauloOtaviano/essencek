from django.db import migrations


def scrub_plaintext_identity(apps, schema_editor):
    from accounts.validators import normalize_cpf, normalize_whatsapp
    from core.pii import make_pii_lookup

    User = apps.get_model('accounts', 'User')
    alias = schema_editor.connection.alias
    for user in User.objects.using(alias).select_for_update().all():
        cpf = normalize_cpf(user.legacy_cpf or user.cpf_encrypted)
        whatsapp = normalize_whatsapp(user.legacy_whatsapp or user.whatsapp_encrypted)
        updates = {
            'cpf_lookup': make_pii_lookup(cpf),
            'whatsapp_lookup': make_pii_lookup(whatsapp),
            'legacy_cpf': None,
            'legacy_whatsapp': None,
        }
        if cpf:
            updates['cpf_encrypted'] = cpf
        if whatsapp:
            updates['whatsapp_encrypted'] = whatsapp
        User.objects.using(alias).filter(pk=user.pk).update(**updates)


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
