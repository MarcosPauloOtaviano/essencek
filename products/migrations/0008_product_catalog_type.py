from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('products', '0007_home_collections'),
    ]

    operations = [
        migrations.AddField(
            model_name='product',
            name='decanter_of',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='decanter_products',
                to='products.product',
                verbose_name='Perfume principal relacionado',
            ),
        ),
        migrations.AddField(
            model_name='product',
            name='decanter_volume_ml',
            field=models.PositiveIntegerField(
                blank=True,
                null=True,
                verbose_name='Volume do decanter (ml)',
            ),
        ),
        migrations.AddField(
            model_name='product',
            name='product_kind',
            field=models.CharField(
                choices=[
                    ('standard', 'Produto principal / frasco'),
                    ('decanter', 'Decanter'),
                ],
                db_index=True,
                default='standard',
                max_length=20,
                verbose_name='Tipo de catálogo',
            ),
        ),
    ]
