from django.db import models
import os

class Candidate(models.Model):
    name = models.CharField(max_length=100)
    email = models.EmailField(unique=True)
    password = models.CharField(max_length=100)

class JobResume(models.Model):
    name = models.CharField(max_length=100)
    resume = models.FileField(upload_to='resumes/')
    resume_text = models.TextField()

    def save(self, *args, **kwargs):
        try:
            # check if updating an existing record
            old = JobResume.objects.get(pk=self.pk)
            if old.resume and old.resume != self.resume:
                if os.path.isfile(old.resume.path):
                    os.remove(old.resume.path)  # delete old file
        except JobResume.DoesNotExist:
            pass  # new record, nothing to delete

        super().save(*args, **kwargs)

class Job(models.Model):
    title = models.CharField(max_length=200)
    company = models.CharField(max_length=200)
    location = models.CharField(max_length=200)
    url = models.URLField()
    description = models.TextField(null=True, blank=True)
    country = models.CharField(max_length=50, null=True, blank=True)
    adzuna_id = models.CharField(max_length=100, unique=True)

