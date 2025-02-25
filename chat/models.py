from django.db import models


# class User(Base):
#     __tablename__ = 'users'
#     id = Column(String, primary_key=True, index=True)
#     created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
#     transcripts = relationship("ChatTranscript", back_populates="user")
class User(models.Model):
    id = models.CharField(primary_key=True, max_length=255)
    created_at = models.DateTimeField(auto_now_add=True)
    
# class ChatTranscript(Base):
#     __tablename__ = 'chat_transcripts'
#     id = Column(Integer, primary_key=True, index=True)
#     user_id = Column(String, ForeignKey('users.id'), nullable=False)
#     role = Column(String, nullable=False)  # e.g., 'user' or 'assistant'
#     content = Column(String, nullable=False)
#     created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
#     user = relationship("User", back_populates="transcripts")

class ChatTranscript(models.Model):
    ROLE_CHOICES = (
        ('user', 'User'),
        ('assistant', 'Assistant'),
    )
    user = models.ForeignKey(User, on_delete=models.DO_NOTHING, related_name='transcripts')
    role = models.CharField(max_length=255, choices=ROLE_CHOICES)
    content = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    
