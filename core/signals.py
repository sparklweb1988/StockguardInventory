from django.contrib.auth.models import User
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils import timezone
from datetime import timedelta
from .models import Profile, Business


@receiver(post_save, sender=User)
def create_profile(sender, instance, created, **kwargs):
    if created:
        # ✅ Create business automatically
        business = Business.objects.create(name=f"{instance.username}'s Business")

        # ✅ Create profile with business + trial
        Profile.objects.create(
            user=instance,
            business=business,
            subscription_expiry=timezone.now() + timedelta(days=7)
        )


@receiver(post_save, sender=User)
def save_profile(sender, instance, **kwargs):
    instance.profile.save()