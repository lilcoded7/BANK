from django.db import models

class TimeBaseModel(models.Model):
    created_at = models.DateTimeField(auto_now_add=True, null=True, blank=True)  # Created once, when the object is first created
    updated_at = models.DateTimeField(auto_now=True, null=True, blank=True)      # Updated every time the object is saved

    class Meta:
        abstract = True
        ordering = ['-created_at']
