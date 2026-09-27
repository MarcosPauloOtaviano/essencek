from django.db import migrations, models


def backfill_identity_fields(apps, schema_editor):
    from accounts.validators import normalize_cpf, normalize_whatsapp
    from core.pii import make_pii_lookup

    User = apps.get_model('accounts', 'User')
    for user in User.objects.all().iterator():
        cpf = normalize_cpf(user.cpf or user.cpf_encrypted)
        whatsapp = normalize_whatsapp(user.whatsapp or user.whatsapp_encrypted)
        updates = {
            'cpf_lookup': make_pii_lookup(cpf),
            'whatsapp_lookup': make_pii_lookup(whatsapp),
        }
        if cpf:
            updates['cpf_encrypted'] = cpf
        if whatsapp:
            updates['whatsapp_encrypted'] = whatsapp
        User.objects.filter(pk=user.pk).update(**updates)


def clear_blind_indexes(apps, schema_editor):
    User = apps.get_model('accounts', 'User')
    User.objects.update(cpf_lookup=None, whatsapp_lookup=None)


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0004_alter_user_whatsapp_alter_user_whatsapp_encrypted'),
    ]

    operations = [
        migrations.AddField(
            model_name='user',
            name='cpf_lookup',
            field=models.CharField(blank=True, editable=False, max_length=64, null=True, unique=True),
        ),
        migrations.AddField(
            model_name='user',
            name='whatsapp_lookup',
            field=models.CharField(blank=True, editable=False, max_length=64, null=True, unique=True),
        ),
        migrations.RunPython(backfill_identity_fields, clear_blind_indexes),
    ]
