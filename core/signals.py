from django.contrib.auth.models import User
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils import timezone
from datetime import timedelta
from .models import Profile

@receiver(post_save, sender=User)
def create_profile(sender, instance, created, **kwargs):
    if created:
        Profile.objects.create(
            user=instance,
            is_paid=False,
            subscription_expiry=timezone.now() + timedelta(days=7)  # free trial period
        )

@receiver(post_save, sender=User)
def save_profile(sender, instance, **kwargs):
    instance.profile.save()