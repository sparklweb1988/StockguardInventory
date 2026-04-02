from django.contrib import admin
from .models import Profile, Business, Product, Batch, Customer, Order, OrderItem, Invoice


admin.site.register(Product)
admin.site.register(Batch)
admin.site.register(Customer)
admin.site.register(Order)
admin.site.register(OrderItem)









# Register Profile to manage subscription plans
@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'plan', 'plan_expiry', 'paystack_ref', 'is_active')
    search_fields = ('user__username', 'user__email', 'paystack_ref')
    list_filter = ('plan',)
