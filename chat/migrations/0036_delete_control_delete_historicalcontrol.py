# Generated by Django 5.1.8 on 2025-04-17 13:43

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("chat", "0035_controlconfig_historicalcontrolconfig_and_more"),
    ]

    operations = [
        migrations.DeleteModel(
            name="Control",
        ),
        migrations.DeleteModel(
            name="HistoricalControl",
        ),
    ]
