# Generated by Django 5.1.3 on 2024-11-20 13:52

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("webku", "0009_delete_userprofile"),
    ]

    operations = [
        migrations.AddField(
            model_name="makanan2",
            name="category",
            field=models.CharField(
                choices=[
                    ("makanan", "Makanan"),
                    ("minuman", "Minuman"),
                    ("cake", "Cake"),
                    ("cookies", "Cookies"),
                ],
                default="",
                max_length=50,
            ),
        ),
    ]