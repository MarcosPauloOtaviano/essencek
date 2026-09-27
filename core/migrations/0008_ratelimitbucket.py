from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0007_showcaseslide_background_style_showcaseslide_kind_and_more'),
    ]

    operations = [
        migrations.CreateModel(
            name='RateLimitBucket',
            fields=[
                ('key', models.CharField(max_length=64, primary_key=True, serialize=False)),
                ('count', models.PositiveIntegerField(default=0)),
                ('expires_at', models.DateTimeField(db_index=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
            options={
                'verbose_name': 'Contador de limite de acesso',
                'verbose_name_plural': 'Contadores de limite de acesso',
            },
        ),
    ]
