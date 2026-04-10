from datetime import timezone

from django.contrib import admin
from .models import Profile, Business, Product, Batch, Customer, Order, OrderItem, Invoice, Blog,DemoVideo


admin.site.register(Product)
admin.site.register(Batch)
admin.site.register(Customer)
admin.site.register(Order)
admin.site.register(OrderItem)



class BlogAdmin(admin.ModelAdmin):
    list_display = ('title', 'author', 'slug', 'created_at')
    prepopulated_fields = {'slug': ('title',)}  # 👈 AUTO GENERATE SLUG
    search_fields = ('title', 'content')
    list_filter = ('created_at', 'author')

admin.site.register(Blog, BlogAdmin)






@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):
    list_display = (
        'user',
        'subscription_code',
        'subscription_expiry',
        'paystack_customer_code',
        'is_paid',
        'has_active_subscription',
    )
    search_fields = (
        'user__username',
        'user__email',
        'paystack_customer_code',
        'subscription_code',
    )
    list_filter = ('subscription_expiry', 'is_paid')

    def has_active_subscription(self, obj):
        if obj.subscription_code and obj.subscription_expiry:
            return obj.subscription_expiry > timezone.now()
        return False
    has_active_subscription.boolean = True
    has_active_subscription.short_description = 'Active Subscription'
    
    
    
    


admin.site.register(DemoVideo)