from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0004_alter_storesettings_whatsapp'),
    ]

    operations = [
        migrations.CreateModel(
            name='StoredMediaFile',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=500, unique=True, verbose_name='Caminho do arquivo')),
                ('content_type', models.CharField(blank=True, max_length=120, verbose_name='Tipo de arquivo')),
                ('size', models.PositiveBigIntegerField(default=0, verbose_name='Tamanho em bytes')),
                ('data', models.BinaryField(verbose_name='Arquivo')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='Criado em')),
                ('updated_at', models.DateTimeField(auto_now=True, verbose_name='Atualizado em')),
            ],
            options={
                'verbose_name': 'Arquivo de mídia persistente',
                'verbose_name_plural': 'Arquivos de mídia persistentes',
                'ordering': ['name'],
            },
        ),
    ]
