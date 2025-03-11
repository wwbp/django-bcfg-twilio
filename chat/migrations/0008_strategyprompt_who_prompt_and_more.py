# Generated by Django 5.1.7 on 2025-03-07 15:57

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('chat', '0007_strategyprompt'),
    ]

    operations = [
        migrations.AddField(
            model_name='strategyprompt',
            name='who_prompt',
            field=models.TextField(default='', help_text="Criteria for selecting the response's addressee"),
        ),
        migrations.AlterField(
            model_name='strategyprompt',
            name='what_prompt',
            field=models.TextField(default='', help_text='Prompt used to generate a response'),
        ),
        migrations.AlterField(
            model_name='strategyprompt',
            name='when_prompt',
            field=models.TextField(default='', help_text='Conditions or triggers for using this strategy'),
        ),
    ]
