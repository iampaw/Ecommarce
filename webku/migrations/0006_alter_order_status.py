# Generated by Django 4.2.9 on 2024-12-25 17:07

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('webku', '0005_remove_cartitem_cart_remove_cartitem_makanan_and_more'),
    ]

    operations = [
        migrations.AlterField(
            model_name='order',
            name='status',
            field=models.CharField(choices=[('Pending', 'Pending'), ('Confirmed', 'Confirmed'), ('Shipped', 'Shipped'), ('Delivered', 'Delivered'), ('Cancelled', 'Cancelled')], default='Pending', max_length=20),
        ),
    ]