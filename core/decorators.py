from django.shortcuts import redirect
from functools import wraps
from django.utils import timezone

def subscription_required(view_func):
    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        profile = getattr(request.user, 'profile', None)
        if not profile:
            return redirect('pricing')

        now = timezone.now()

        # Check if free trial is active
        trial_active = profile.plan == 'free' and (
            profile.plan_expiry is None or profile.plan_expiry > now
        )

        # Check if paid subscription is active
        subscription_active = profile.plan != 'free' and profile.is_active()

        # Allow access if trial OR subscription is active
        if not (trial_active or subscription_active):
            return redirect('pricing')

        return view_func(request, *args, **kwargs)
    return _wrapped_view