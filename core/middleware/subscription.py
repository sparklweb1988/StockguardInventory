from django.shortcuts import redirect
from django.urls import reverse
from django.utils import timezone

class SubscriptionRequiredMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Exempt admin and staff
        if hasattr(request, 'user') and request.user.is_authenticated:
            if request.user.is_superuser or request.user.is_staff:
                return self.get_response(request)

            now = timezone.now()
            trial_active = getattr(request.user, 'trial_end', None) and request.user.trial_end > now
            subscription_active = getattr(request.user, 'subscription_end', None) and request.user.subscription_end > now

            if not trial_active and not subscription_active:
                # only redirect non-admins without active plan/trial
                if request.path not in [reverse('pricing'), reverse('logout')]:
                    return redirect('pricing')

        return self.get_response(request)