from django.db import models
from django.contrib.auth.models import AbstractUser


class CustomUser(AbstractUser):
    phone_number = models.CharField(max_length=10)
    salesperson_id = models.IntegerField(unique=True, null=True, blank=True)
    last_reminder_sent_at = models.DateTimeField(null=True, blank=True)
    odoo_user_id = models.CharField(max_length=255, null=True, blank=True)

    USERNAME_FIELD = 'username'
