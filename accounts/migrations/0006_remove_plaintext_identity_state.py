from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0005_user_identity_blind_indexes'),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            database_operations=[],
            state_operations=[
                migrations.RemoveField(model_name='user', name='cpf'),
                migrations.RemoveField(model_name='user', name='whatsapp'),
                migrations.AddField(
                    model_name='user', name='legacy_cpf',
                    field=models.CharField(db_column='cpf', max_length=11, unique=True, null=True, blank=True, editable=False),
                ),
                migrations.AddField(
                    model_name='user', name='legacy_whatsapp',
                    field=models.CharField(db_column='whatsapp', max_length=11, unique=True, null=True, blank=True, editable=False),
                ),
            ],
        ),
    ]
