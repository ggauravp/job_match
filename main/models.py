from django.db import models
from django.contrib.auth.models import User
import os
from django.utils import timezone

class JobResume(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, null=True, blank=True)
    resume = models.FileField(upload_to='resumes/')
    resume_text = models.TextField(blank=True)
    uploaded_at = models.DateTimeField(default=timezone.now)

    def save(self, *args, **kwargs):
        # Delete old resume file when user uploads a new one
        try:
            old = JobResume.objects.get(pk=self.pk)
            if old.resume and old.resume != self.resume:
                if os.path.isfile(old.resume.path):
                    os.remove(old.resume.path)
        except JobResume.DoesNotExist:
            pass
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.user.username}'s Resume"

class Job(models.Model):
    title = models.CharField(max_length=200)
    company = models.CharField(max_length=200)
    location = models.CharField(max_length=200)
    url = models.URLField()
    description = models.TextField(null=True, blank=True)
    qualifications = models.TextField(null=True, blank=True)
    country = models.CharField(max_length=50, null=True, blank=True)
    deadline = models.CharField(max_length=100, null=True, blank=True)
    adzuna_id = models.CharField(max_length=100, unique=True)

class JobRating(models.Model):
    job = models.ForeignKey(Job, on_delete=models.CASCADE, related_name='ratings')
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    stars = models.PositiveSmallIntegerField(default=0)  # 1 to 5 stars
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('job', 'user')  # one rating per user per job

    def __str__(self):
        return f"{self.user.username} - {self.job.title} - {self.stars}⭐"