from django.db import models

from .constant import MODERATION_MESSAGE_DEFAULT


class User(models.Model):
    id = models.CharField(primary_key=True, max_length=255)
    created_at = models.DateTimeField(auto_now_add=True)
    school_name = models.CharField(max_length=255, default='')
    school_mascot = models.CharField(max_length=255, default='')
    name = models.CharField(max_length=255, default='')
    initial_message = models.TextField(default='')
    is_test = models.BooleanField(default=False)


class Group(models.Model):
    id = models.CharField(primary_key=True, max_length=255)
    users = models.ManyToManyField(User, related_name="groups")
    created_at = models.DateTimeField(auto_now_add=True)
    is_test = models.BooleanField(default=False)


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


class GroupChatTranscript(models.Model):
    ROLE_CHOICES = (
        ('user', 'User'),
        ('assistant', 'Assistant'),
    )
    group = models.ForeignKey(
        Group, on_delete=models.DO_NOTHING, related_name='transcripts')
    sender = models.ForeignKey(
        User, on_delete=models.DO_NOTHING, related_name='group_transcripts', null=True)
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
    moderation = models.TextField(default=MODERATION_MESSAGE_DEFAULT)
    created_at = models.DateTimeField(auto_now_add=True)


class Summary(models.Model):
    TYPE_CHOICES = [
        ('influencer', 'Influencer'),
        ('song', 'Song'),
        ('spot', 'Spot'),
        ('idea', 'Idea'),
        ('pick', 'Pick'),
    ]

    school = models.CharField(max_length=255)
    type = models.CharField(max_length=20, choices=TYPE_CHOICES)
    summary = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)


class StrategyPrompt(models.Model):
    name = models.CharField(max_length=255)
    what_prompt = models.TextField(
        help_text="Prompt used to generate a response")
    when_prompt = models.TextField(
        help_text="Conditions or triggers for using this strategy")
    is_active = models.BooleanField(default=True, help_text="Soft delete flag")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
