# Generated by Django 5.1.11 on 2025-07-21 08:37

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("quanly", "0003_alter_candidate_avatar"),
    ]

    operations = [
        migrations.AddField(
            model_name="voter",
            name="salt",
            field=models.CharField(
                blank=True,
                max_length=32,
                null=True,
                verbose_name="Salt cho mã hóa khóa bí mật",
            ),
        ),
    ]
