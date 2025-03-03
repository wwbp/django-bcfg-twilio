from django.db import models


class User(models.Model):
    id = models.CharField(primary_key=True, max_length=255)
    created_at = models.DateTimeField(auto_now_add=True)
    school_name = models.CharField(max_length=255, default='')
    school_mascot = models.CharField(max_length=255, default='')
    name = models.CharField(max_length=255, default='')
    initial_message = models.TextField(default='')


class ChatTranscript(models.Model):
    ROLE_CHOICES = (
        ('user', 'User'),
        ('assistant', 'Assistant'),
    )
    user = models.ForeignKey(
        User, on_delete=models.DO_NOTHING, related_name='transcripts')
    role = models.CharField(max_length=255, choices=ROLE_CHOICES)
    content = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)


class Prompt(models.Model):
    week = models.IntegerField()
    activity = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)


class Control(models.Model):
    persona = models.TextField()
    system = models.TextField()
    default = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
