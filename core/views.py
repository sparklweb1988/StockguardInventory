from django.http import HttpResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.models import User
from django.contrib import messages
from .models import Product, Batch, Customer, Order, Business, Profile, Blog
from django.contrib.auth.decorators import login_required
from django.utils import timezone
from datetime import timedelta, datetime
import requests
from django.conf import settings
from django.views.decorators.csrf import csrf_exempt


# -------------------------------
# Authentication
# -------------------------------
def signup(request):
    if request.method == "POST":
        username = request.POST['username']
        email = request.POST['email']
        password = request.POST['password']
        user = User.objects.create_user(username=username, email=email, password=password)
        user.save()
        messages.success(request, "Account created successfully!")
        return redirect('login')
    return render(request, "signup.html")


def login_view(request):
    if request.method == "POST":
        username = request.POST['username']
        password = request.POST['password']
        user = authenticate(request, username=username, password=password)
        if user:
            login(request, user)
            return redirect('dashboard')
        messages.error(request, "Invalid credentials")
    return render(request, "login.html")


def logout_view(request):
    logout(request)
    return redirect('login')


# -------------------------------
# Dashboard / Home
# -------------------------------
def dashboard(request):
    profile = request.user.profile
    today = timezone.now().date()

    # Products
    total_products = Product.objects.filter(business=profile.business).count()

    # Customers added this month
    total_customers = Customer.objects.filter(
        business=profile.business,
        created_at__month=today.month,
        created_at__year=today.year
    ).count()

    # Orders placed this month
    total_orders = Order.objects.filter(
        business=profile.business,
        created_at__month=today.month,
        created_at__year=today.year
    ).count()

    # Expired products (any batch expired)
    total_expired_products = Product.objects.filter(
        business=profile.business,
        batches__expiry_date__lt=today
    ).distinct().count()

    # Total sales (sum of orders this month)
    orders_this_month = Order.objects.filter(
        business=profile.business,
        created_at__month=today.month,
        created_at__year=today.year,
        status='paid'
    )
    total_sales = sum(order.total for order in orders_this_month)
    total_profit = sum(
        order.total - sum(item.price * item.quantity for item in order.items.all())
        for order in orders_this_month
    )

    # Check subscription/trial
    subscription_active = profile.has_active_subscription()
    trial_active = profile.is_trial_active()
    trial_days_remaining = 0
    if trial_active and profile.subscription_expiry:
        trial_days_remaining = (profile.subscription_expiry.date() - today).days

    # Pass available plans (example)
    plans = [
        {"name": "Basic", "price": 5000, "code": settings.PAYSTACK_PLAN_CODE},
    ]

    context = {
        "profile": profile,
        "total_products": total_products,
        "total_customers": total_customers,
        "total_orders": total_orders,
        "total_expired_products": total_expired_products,
        "total_sales": total_sales,
        "total_profit": total_profit,
        "subscription_active": subscription_active,
        "trial_active": trial_active,
        "trial_days_remaining": trial_days_remaining,
        "plans": plans,
    }

    return render(request, "dashboard.html", context)


def home(request):
    return render(request, 'home.html')


# -------------------------------
# Products
# -------------------------------
@login_required
def product_list(request):
    products = Product.objects.filter(business=request.user.profile.business)
    return render(request, "product_list.html", {"products": products})


@login_required
def product_create(request):
    if request.method == "POST":
        name = request.POST['name']
        price = request.POST['price']
        Product.objects.create(name=name, selling_price=price, cost_price=0, business=request.user.profile.business)
        return redirect('product_list')
    return render(request, "product_create.html")


@login_required
def product_update(request, id):
    product = get_object_or_404(Product, id=id, business=request.user.profile.business)
    if request.method == "POST":
        product.name = request.POST['name']
        product.selling_price = request.POST['price']
        product.save()
        return redirect('product_list')
    return render(request, "product_update.html", {"product": product})


@login_required
def product_delete(request, id):
    product = get_object_or_404(Product, id=id, business=request.user.profile.business)
    product.delete()
    return redirect('product_list')


# -------------------------------
# Batch Management
# -------------------------------
@login_required
def batch_list(request, product_id):
    batches = Batch.objects.filter(product_id=product_id)
    return render(request, "batch_list.html", {"batches": batches, "product_id": product_id})


@login_required
def batch_create(request, product_id):
    if request.method == "POST":
        quantity = request.POST['quantity']
        expiry_date = request.POST['expiry_date']
        Batch.objects.create(product_id=product_id, quantity=quantity, expiry_date=expiry_date, business=request.user.profile.business)
        return redirect('batch_list', product_id=product_id)
    return render(request, "batch_form.html", {"product_id": product_id})


@login_required
def batch_update(request, pk):
    batch = get_object_or_404(Batch, pk=pk)
    if request.method == "POST":
        batch.quantity = request.POST['quantity']
        batch.expiry_date = request.POST['expiry_date']
        batch.save()
        return redirect('batch_list', product_id=batch.product.id)
    return render(request, "batch_form.html", {"batch": batch})


@login_required
def batch_delete(request, pk):
    batch = get_object_or_404(Batch, pk=pk)
    product_id = batch.product.id
    batch.delete()
    return redirect('batch_list', product_id=product_id)


# -------------------------------
# Customers
# -------------------------------
@login_required
def customer_list(request):
    customers = Customer.objects.filter(business=request.user.profile.business)
    return render(request, "customer_list.html", {"customers": customers})


@login_required
def customer_create(request):
    if request.method == "POST":
        name = request.POST['name']
        phone = request.POST.get('phone', '')
        Customer.objects.create(name=name, phone=phone, business=request.user.profile.business)
        return redirect('customer_list')
    return render(request, "customer_create.html")


@login_required
def customer_update(request, id):
    customer = get_object_or_404(Customer, id=id, business=request.user.profile.business)
    if request.method == "POST":
        customer.name = request.POST['name']
        customer.phone = request.POST.get('phone', '')
        customer.save()
        return redirect('customer_list')
    return render(request, "customer_update.html", {"customer": customer})


@login_required
def customer_delete(request, id):
    customer = get_object_or_404(Customer, id=id, business=request.user.profile.business)
    customer.delete()
    return redirect('customer_list')


# -------------------------------
# Orders
# -------------------------------
@login_required
def order_list(request):
    orders = Order.objects.filter(business=request.user.profile.business)
    return render(request, "order_list.html", {"orders": orders})


@login_required
def order_create(request):
    if request.method == "POST":
        customer_id = request.POST['customer']
        total_amount = request.POST['total_amount']
        Order.objects.create(
            customer_id=customer_id,
            total=total_amount,
            subtotal=total_amount,
            business=request.user.profile.business
        )
        return redirect('order_list')
    customers = Customer.objects.filter(business=request.user.profile.business)
    return render(request, "order_create.html", {"customers": customers})


@login_required
def change_order_status(request, pk):
    order = get_object_or_404(Order, pk=pk, business=request.user.profile.business)
    order.status = "paid" if order.status != "paid" else "draft"
    order.save()
    return redirect('order_list')


# -------------------------------
# Static Pages
# -------------------------------
def about(request):
    return render(request, "about.html")


def terms(request):
    return render(request, "terms.html")


def privacy(request):
    return render(request, "privacy.html")


def contact(request):
    return render(request, "contact.html")


# -------------------------------
# Invoice
# -------------------------------
@login_required
def invoice_view(request, order_id):
    order = get_object_or_404(Order, pk=order_id, business=request.user.profile.business)
    return render(request, "invoice.html", {"order": order})


# -------------------------------
# Blog
# -------------------------------
def blog_view(request):
    posts = Blog.objects.all()
    return render(request, "blog/blog_list.html", {"posts": posts})


def blog_detail(request, slug):
    post = get_object_or_404(Blog, slug=slug)
    return render(request, "blog/blog_detail.html", {"post": post})


# -------------------------------
# Paystack Subscription
# -------------------------------
@login_required
def subscribe(request):
    email = request.user.email
    secret_key = settings.PAYSTACK_SECRET_KEY
    plan_code = settings.PAYSTACK_PLAN_CODE

    # Check if customer exists on Paystack
    url = f"https://api.paystack.co/customer?email={email}"
    res = requests.get(url, headers={"Authorization": f"Bearer {secret_key}"})
    res_json = res.json()

    if res_json.get("status") and res_json["data"]:
        customer_code = res_json["data"][0]["customer_code"]
    else:
        # Create customer if not exists
        create_url = "https://api.paystack.co/customer"
        payload = {"email": email, "first_name": request.user.username}
        create_res = requests.post(create_url, json=payload, headers={"Authorization": f"Bearer {secret_key}"})
        create_json = create_res.json()
        if create_json.get("status"):
            customer_code = create_json["data"]["customer_code"]
        else:
            return HttpResponse("Failed to create Paystack customer: " + create_json.get("message", "Unknown error"))

    # Create subscription
    sub_url = "https://api.paystack.co/subscription"
    sub_data = {"customer": customer_code, "plan": plan_code}
    sub_res = requests.post(sub_url, json=sub_data, headers={"Authorization": f"Bearer {secret_key}"})
    sub_json = sub_res.json()

    if sub_json.get("status"):
        auth_url = sub_json["data"].get("authorization_url")
        if auth_url:
            return redirect(auth_url)
        return HttpResponse("Subscription created successfully! You may need to verify manually.")
    else:
        return HttpResponse("Payment initialization failed: " + sub_json.get("message", "Unknown error"))
    
    
    
    
@login_required
def verify(request):
    reference = request.GET.get("reference")
    if not reference:
        return HttpResponse("No reference provided", status=400)

    headers = {"Authorization": f"Bearer {settings.PAYSTACK_SECRET_KEY}"}
    response = requests.get(f"https://api.paystack.co/transaction/verify/{reference}", headers=headers)

    if response.status_code == 200:
        res_data = response.json()
        if res_data["data"]["status"] == "success":
            profile = request.user.profile
            profile.is_paid = True
            profile.subscription_expiry = None  # Optional: set actual subscription expiry if you track
            profile.save()
            return HttpResponse("Payment successful. You are now on Premium plan.")
        else:
            return HttpResponse("Payment failed")
    return HttpResponse("Error verifying payment", status=400)





# -------------------------------
# Paystack webhook
# -------------------------------
@csrf_exempt
def paystack_webhook(request):
    if request.method == "POST":
        print("Paystack webhook received:", request.body)
        return HttpResponse(status=200)
    return HttpResponse(status=400)