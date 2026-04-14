from django.contrib.auth.models import User
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils import timezone
from datetime import timedelta
from .models import Profile


@receiver(post_save, sender=User)
def create_profile(sender, instance, created, **kwargs):
    if created:
        # ✅ Only create profile (NO business here)
        Profile.objects.create(
            user=instance,
            subscription_expiry=timezone.now() + timedelta(days=14)
        )


@receiver(post_save, sender=User)
def save_profile(sender, instance, **kwargs):
    if hasattr(instance, 'profile'):
        instance.profile.save()