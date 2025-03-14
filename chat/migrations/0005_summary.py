# Generated by Django 5.1.6 on 2025-03-06 13:54

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('chat', '0004_control_moderation'),
    ]

    operations = [
        migrations.CreateModel(
            name='Summary',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('school', models.CharField(max_length=255)),
                ('type', models.CharField(choices=[('influencer', 'Influencer'), ('song', 'Song'), ('spot', 'Spot'), ('idea', 'Idea'), ('pick', 'Pick')], max_length=20)),
                ('summary', models.TextField()),
                ('created_at', models.DateTimeField(auto_now_add=True)),
            ],
        ),
    ]
