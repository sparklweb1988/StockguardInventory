from django.contrib import admin
from .models import Profile, Business, Product, Batch, Customer, Order, OrderItem, Invoice, Blog


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









# Register Profile to manage subscription plans
@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'plan', 'plan_expiry', 'paystack_ref', 'is_active')
    search_fields = ('user__username', 'user__email', 'paystack_ref')
    list_filter = ('plan',)
