from django.contrib.auth.models import AbstractUser
from django.db import models

# Create your models here.
class CustomUser(AbstractUser):
    ROLE_CHOICES = (('driver', 'Driver') , ('admin', 'Admin'))
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='driver')
    phone_number = models.CharField(max_length=15, blank=True, null=True)
    plate_number = models.CharField(max_length=20, blank=True, null=True)

    def __str__(self):
        return f" {self.username} ({self.role})"   
