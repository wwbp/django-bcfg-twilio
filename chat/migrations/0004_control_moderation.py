# Generated by Django 5.1.6 on 2025-03-05 06:23

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('chat', '0003_group_groupchattranscript'),
    ]

    operations = [
        migrations.AddField(
            model_name='control',
            name='moderation',
            field=models.TextField(default="I'm really sorry you're feeling this way, but I'm not equipped to help. It's important to talk to someone who can support you right now. Please contact UCLA resources such as UCLA CAPS: Counseling & Psychological Services | Counseling and Psychological Services (ucla.edu) at 310-825-0768, or the National Suicide Prevention Lifeline at 1-800-273-TALK (8255) or text HOME to 741741 to connect with a trained clinician. If you're in immediate danger, please call 911 or go to the nearest emergency room. Please also note that if you wish not to continue with the study, feel free to quit anytime."),
        ),
    ]
