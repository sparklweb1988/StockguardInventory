from django.urls import path
from . import views
from django.conf import settings
from django.conf.urls.static import static
from django.contrib.auth import views as auth_views
urlpatterns = [

    # Products
    path('', views.home, name="home"),
    path("products/", views.product_list, name="product_list"),
    path("products/create/", views.product_create, name="product_create"),
    path("products/update/<int:id>/", views.product_update, name="product_update"),
    path("products/delete/<int:id>/", views.product_delete, name="product_delete"),
    path("dashboard/", views.dashboard, name="dashboard"),
 
    # Batch Management
    path("batches/<int:product_id>/", views.batch_list, name="batch_list"),
    path("batch/create/<int:product_id>/", views.batch_create, name="batch_create"),
    path("batch/update/<int:pk>/", views.batch_update, name="batch_update"),
    path("batch/delete/<int:pk>/", views.batch_delete, name="batch_delete"),
  
    # Customers
    path("customers/", views.customer_list, name="customer_list"),
    path("customers/create/", views.customer_create, name="customer_create"),
    path("customers/update/<int:id>/", views.customer_update, name="customer_update"),
    path("customers/delete/<int:id>/", views.customer_delete, name="customer_delete"),

    # Orders
    path("orders/", views.order_list, name="order_list"),
    path("orders/create/", views.order_create, name="order_create"),
    path("orders/status/<int:pk>/", views.change_order_status, name="change_order_status"),
    
    # Authentication
    path('signup/', views.signup, name="signup"),
    path('login/', views.login_view, name="login"),
    path('logout/', views.logout_view, name="logout"),
    
    # Static Pages
    path('about/', views.about, name="about"),
    path('terms/', views.terms, name="terms"),
    path('privacy/', views.privacy, name="privacy"),
    path('contact/', views.contact, name="contact"),
    
    # Invoice
    path("invoice/<int:order_id>/", views.invoice_view, name="invoice_view"),

    # Blog
    path('blog/', views.blog_view, name='blog_view'),
    path('blog/<slug:slug>/', views.blog_detail, name='blog_detail'),
    
    # Paystack subscription
    path('subscribe/', views.subscribe, name='subscribe'),
    path('verify/', views.verify, name='verify'),
    path('paystack/webhook/', views.paystack_webhook, name='paystack_webhook'),
    
    
    # Forgot password
    
    
    path('forgot-password/', auth_views.PasswordResetView.as_view(
        template_name='auth/forgot_password.html'
    ), name='password_reset'),

    path('forgot-password/done/', auth_views.PasswordResetDoneView.as_view(
        template_name='auth/password_reset_done.html'
    ), name='password_reset_done'),

    path('reset/<uidb64>/<token>/', auth_views.PasswordResetConfirmView.as_view(
        template_name='auth/password_reset_confirm.html'
    ), name='password_reset_confirm'),

    path('reset/done/', auth_views.PasswordResetCompleteView.as_view(
        template_name='auth/password_reset_complete.html'
    ), name='password_reset_complete'),

]

urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)