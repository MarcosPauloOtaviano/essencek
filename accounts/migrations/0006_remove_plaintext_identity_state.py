from django.db import migrations


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
            ],
        ),
    ]
