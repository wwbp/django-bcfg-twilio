# Generated by Django 5.1.7 on 2025-03-07 08:03

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('chat', '0006_summary_updated_at'),
    ]

    operations = [
        migrations.CreateModel(
            name='StrategyPrompt',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=255)),
                ('what_prompt', models.TextField(help_text='Prompt used to generate a response')),
                ('when_prompt', models.TextField(help_text='Conditions or triggers for using this strategy')),
                ('is_active', models.BooleanField(default=True, help_text='Soft delete flag')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
        ),
    ]
