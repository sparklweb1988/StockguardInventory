from django.http import HttpResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.models import User
from django.contrib import messages
from .models import DemoVideo, Product, Batch, Customer, Order, Business, Profile, Blog,OrderItem,Invoice
from django.contrib.auth.decorators import login_required
from django.utils import timezone
from datetime import timedelta, datetime
import requests
from django.conf import settings
from django.views.decorators.csrf import csrf_exempt
from django.db.models import Sum
from urllib.parse import urlparse, parse_qs

from django.db.models import Q
# -------------------------------
# Authentication
# -------------------------------



def signup(request):
    if request.method == "POST":
        username = request.POST.get('username')
        email = request.POST.get('email')
        password = request.POST.get('password')
        business_name = request.POST.get('business_name')

        # -----------------------------
        # Validate required fields
        # -----------------------------
        if not username or not email or not password or not business_name:
            messages.error(request, "All fields are required.")
            return redirect('signup')

        # -----------------------------
        # Check for duplicates
        # -----------------------------
        if User.objects.filter(username=username).exists():
            messages.error(request, "Username already taken.")
            return redirect('signup')

        if User.objects.filter(email=email).exists():
            messages.error(request, "Email already registered.")
            return redirect('signup')

        # -----------------------------
        # Create user
        # -----------------------------
        user = User.objects.create_user(
            username=username,
            email=email,
            password=password
        )

        # -----------------------------
        # Create business and profile
        # -----------------------------
        # business = Business.objects.create(name=business_name)  # Use user input only
        # profile = Profile.objects.create(
        #     user=user,
        #     business=business
        # )

        messages.success(request, "Account created successfully! You can now login.")
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
    return redirect('home')


# -------------------------------
# Dashboard / Home
# -------------------------------



@login_required
def dashboard(request):
    profile = request.user.profile
    today = timezone.now().date()

    # ==========================
    # Basic Counts
    # ==========================
    total_products = Product.objects.filter(business=profile.business).count()

    total_customers = Customer.objects.filter(
        business=profile.business,
        created_at__month=today.month,
        created_at__year=today.year
    ).count()

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

 
    # ✅ Low stock products (using batches)
    low_stock_products = Product.objects.filter(
        business=profile.business
    ).annotate(
        total_stock=Sum('batches__quantity')
    ).filter(
        total_stock__lt=10  # your threshold
    )

    total_low_products = low_stock_products.count()

    # ==========================
    # Total Sales and Profit
    # ==========================
    orders_this_month = Order.objects.filter(
        business=profile.business,
        created_at__month=today.month,
        created_at__year=today.year,
        status='paid'
    )

    total_sales = sum(order.total for order in orders_this_month)

    # Correct profit calculation
    total_profit = 0
    for order in orders_this_month:
        for item in order.items.all():
            total_profit += (item.price - item.product.cost_price) * item.quantity

    # ==========================
    # Subscription / Trial Info
    # ==========================
    subscription_active = profile.has_active_subscription()
    trial_active = profile.is_trial_active()
    trial_days_remaining = 0

    if trial_active and profile.subscription_expiry:
        trial_days_remaining = (profile.subscription_expiry.date() - today).days

    # Example plans
    plans = [
        {"name": "Basic", "price": 5000, "code": settings.PAYSTACK_PLAN_CODE},
    ]

    # ==========================
    # Context
    # ==========================
    context = {
        "profile": profile,
        "total_products": total_products,
        "total_customers": total_customers,
        "total_orders": total_orders,
        "total_expired_products": total_expired_products,
        "total_low_products": total_low_products,  # ✅ NEW
        "total_sales": total_sales,
        "total_profit": total_profit,
        "subscription_active": subscription_active,
        "trial_active": trial_active,
        "trial_days_remaining": trial_days_remaining,
        "plans": plans,
    }

    return render(request, "dashboard.html", context)






def home(request):
    video = DemoVideo.objects.last()

    if request.method == "POST" and request.user.is_staff:
        file = request.FILES.get("video")

        if file:
            DemoVideo.objects.create(video_file=file)
            return redirect("home")

    # 👇 ADD THIS
    blogs = Blog.objects.all().order_by('-created_at')[:3]

    return render(request, "home.html", {
        "video": video,
        "blogs": blogs,   # ✅ THIS FIXES YOUR ISSUE
    })
    
    
# -------------------------------
# Products
# -------------------------------
@login_required
def product_list(request):
    products = Product.objects.filter(business=request.user.profile.business)
    query = request.GET.get('q')
    start_date = request.GET.get('start_date')
    end_date = request.GET.get('end_date')
    if query:
        products = Product.objects.filter(name__icontains=query)
    start_date = request.GET.get(start_date)
    end_date = request.GET.get(end_date)
    
    if start_date:
        products = Product.objects.filter(created_at__date__gte=start_date) 

    
    if end_date:
        products = Product.objects.filter(created_at__date__lte=end_date) 
    return render(request, "product_list.html", {"products": products})







@login_required
def product_create(request):
    profile = request.user.profile

    # Safety check
    if not profile.business:
        business = Business.objects.create(name=f"{request.user.username}'s Business")
        profile.business = business
        profile.save()

    if request.method == "POST":
        name = request.POST.get('name')
        cost_price = request.POST.get('cost_price')
        selling_price = request.POST.get('selling_price')

        Product.objects.create(
            name=name,
            cost_price=cost_price,
            selling_price=selling_price,
            business=profile.business
        )

        return redirect('product_list')

    return render(request, "product_create.html")





@login_required
def product_update(request, id):
    product = get_object_or_404(Product, id=id, business=request.user.profile.business)
    if request.method == "POST":
        product.cost_price = request.POST.get('cost_price')
        product.selling_price = request.POST.get('selling_price')
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
    product = get_object_or_404(
        Product,
        id=product_id,
        business=request.user.profile.business
    )

    batches = Batch.objects.filter(
        product=product,
        business=request.user.profile.business
    ).order_by('created_at')

    return render(request, "batch_list.html", {
        "product": product,
        "batches": batches
    })
    
    
@login_required
def batch_create(request, product_id):
    product = get_object_or_404(
        Product, 
        id=product_id, 
        business=request.user.profile.business
    )

    if request.method == "POST":
        batch_number = request.POST.get('batch_number')
        quantity = request.POST.get('quantity')
        expiry_date = request.POST.get('expiry_date')

        # Validation
        if not batch_number or not quantity:
            messages.error(request, "Batch number and quantity are required.")
            return redirect('batch_create', product_id=product.id)

        try:
            quantity = int(quantity)
            if quantity <= 0:
                raise ValueError
        except ValueError:
            messages.error(request, "Quantity must be a positive integer.")
            return redirect('batch_create', product_id=product.id)

        Batch.objects.create(
            product=product,
            batch_number=batch_number,
            quantity=quantity,
            expiry_date=expiry_date,
            business=request.user.profile.business
        )

        # Update product total stock after adding batch
        

        return redirect('batch_list', product_id=product.id)

    return render(request, "batch_create.html", {
        "product": product
    })
    
    
    
    
@login_required
def batch_update(request, pk):
    batch = get_object_or_404(Batch, pk=pk, business=request.user.profile.business)

    if request.method == "POST":
        batch.batch_number = request.POST.get('batch_number')
        batch.quantity = request.POST.get('quantity')
        batch.expiry_date = request.POST.get('expiry_date')
        batch.save()

        return redirect('batch_list', product_id=batch.product.id)

    return render(request, "batch_update.html", {
        "batch": batch
    })
    
    
    
    

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
    business = request.user.profile.business

    orders = Order.objects.filter(business=business)\
                          .select_related("customer")\
                          .order_by("-created_at")
    
    query = request.GET.get('q')
    start_date = request.GET.get('start_date')
    end_date = request.GET.get('end_date')
    
    if query:
        orders = orders.filter(
        Q(order_number__icontains=query) |
        Q(customer__name__icontains=query)
    )
    
    
    start_date = request.GET.get(start_date)
    end_date = request.GET.get(end_date)
    
    if start_date:
        orders = Order.objects.filter(created_at__date__gte=start_date) 

    
    if end_date:
        orders = Order.objects.filter(created_at__date__lte=end_date) 

    return render(request, "order_list.html", {
        "orders": orders
    })
    
    
    
@login_required
def order_create(request):
    business = request.user.profile.business

    if request.method == "POST":
        customer_id = request.POST.get('customer')
        order = Order.objects.create(
            customer_id=customer_id,
            business=business,
            status="draft"
        )

        products = Product.objects.filter(business=business)

        for product in products:
            qty = request.POST.get(f'quantity_{product.id}')
            if not qty or int(qty) <= 0:
                continue
            qty = int(qty)

            if qty > product.total_stock:
                continue  # optionally show error

            # create order item
            OrderItem.objects.create(
                order=order,
                product=product,
                quantity=qty,
                price=product.selling_price,
                business=business
            )

            # deduct stock from batches (FIFO)
            qty_to_deduct = qty
            batches = product.batches.filter(quantity__gt=0).order_by('created_at')

            for batch in batches:
                if qty_to_deduct <= 0:
                    break
                if batch.quantity >= qty_to_deduct:
                    batch.quantity -= qty_to_deduct
                    batch.save()
                    qty_to_deduct = 0
                else:
                    qty_to_deduct -= batch.quantity
                    batch.quantity = 0
                    batch.save()

        # calculate order total
        order.calculate_total()
        return redirect('order_list')

    customers = Customer.objects.filter(business=business)
    products = Product.objects.filter(business=business)

    return render(request, "order_create.html", {
        "customers": customers,
        "products": products
    })
    
    
    
    
    
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
@login_required
def invoice_view(request, order_id):
    business = request.user.profile.business
    order = get_object_or_404(Order, pk=order_id, business=business)
    
    # Make sure an Invoice exists or create one
    invoice, created = Invoice.objects.get_or_create(order=order)

    return render(request, "invoice.html", {
        "invoice": invoice
    })
    
# -------------------------------
# Blog
# -------------------------------
def blog_view(request):
    posts = Blog.objects.all().order_by('-created_at')
    query = request.GET.get('q')
    if query:
        posts = Blog.objects.filter(title__icontains=query)
    return render(request, "blog.html", {"blogs": posts})




def blog_detail(request, slug):
    post = get_object_or_404(Blog, slug=slug)

    # 🔥 RELATED POSTS (exclude current post)
    related = Blog.objects.exclude(id=post.id).order_by('-created_at')[:3]

    return render(request, "blog_detail.html", {
        "post": post,
        "related": related
    })





def get_youtube_embed(url):
    import re
    from urllib.parse import urlparse, parse_qs

    if not url:
        return None

    video_id = None

    if "youtu.be" in url:
        video_id = url.split("/")[-1].split("?")[0]

    elif "watch?v=" in url:
        parsed = urlparse(url)
        video_id = parse_qs(parsed.query).get("v", [None])[0]

    if not video_id:
        return None

    return f"https://www.youtube.com/embed/{video_id}"





# -------------------------------
# Paystack Subscription
# -------------------------------


# -------------------------------
























@login_required
def subscribe(request):
    """
    Upgrade free/trial users to Premium (monthly recurring payment)
    """
    profile = request.user.profile
    email = request.user.email
    secret_key = settings.PAYSTACK_SECRET_KEY
    plan_code = settings.PAYSTACK_PLAN_CODE

    # Prevent re-subscription if already paid
    if profile.is_paid:
        return HttpResponse("You are already on Premium plan.")

    # Step 1: Create or get Paystack customer
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

    # Step 2: Initialize first payment to collect card (₦5,000)
    initialize_url = "https://api.paystack.co/transaction/initialize"
    payload = {
        "email": email,
        "amount": 500000,  # Paystack expects kobo; ₦5,000 = 500000 kobo
        "callback_url": request.build_absolute_uri("/verify/"),
        "metadata": {"subscription": "premium"}
    }
    init_res = requests.post(initialize_url, json=payload, headers={"Authorization": f"Bearer {secret_key}"})
    init_json = init_res.json()

    if init_json.get("status"):
        # Redirect user to Paystack payment page
        auth_url = init_json["data"].get("authorization_url")
        return redirect(auth_url)
    else:
        return HttpResponse("Payment initialization failed: " + init_json.get("message", "Unknown error"))


from django.contrib import messages

@login_required
def verify(request):
    reference = request.GET.get("reference")
    if not reference:
        messages.error(request, "No payment reference provided.")
        return redirect("dashboard")

    secret_key = settings.PAYSTACK_SECRET_KEY
    headers = {"Authorization": f"Bearer {secret_key}"}
    response = requests.get(f"https://api.paystack.co/transaction/verify/{reference}", headers=headers)

    if response.status_code != 200:
        messages.error(request, "Error verifying payment.")
        return redirect("dashboard")

    res_data = response.json()
    if res_data["data"]["status"] != "success":
        messages.error(request, "Payment failed.")
        return redirect("dashboard")

    profile = request.user.profile
    customer_code = res_data["data"]["customer"]["customer_code"]
    plan_code = settings.PAYSTACK_PLAN_CODE

    # Try creating recurring subscription
    sub_url = "https://api.paystack.co/subscription"
    sub_data = {"customer": customer_code, "plan": plan_code}
    sub_res = requests.post(sub_url, json=sub_data, headers=headers)
    sub_json = sub_res.json()

    # Mark user as paid regardless if subscription already exists
    if sub_json.get("status") or "already in place" in sub_json.get("message", "").lower():
        profile.is_paid = True
        profile.subscription_expiry = None
        profile.save()

        messages.success(request, "Payment successful! You are now on Premium plan.")
        return redirect("dashboard")

    # If subscription creation fails for other reasons
    messages.warning(request, "Payment successful but subscription creation failed: " +
                     sub_json.get("message", "Unknown error"))
    profile.is_paid = True
    profile.subscription_expiry = None
    profile.save()
    return redirect("dashboard")





# Paystack webhook (optional)
@csrf_exempt
def paystack_webhook(request):
    if request.method == "POST":
        print("Paystack webhook received:", request.body)
        return HttpResponse(status=200)
    return HttpResponse(status=400)






@login_required
def report_view(request):
    business = request.user.profile.business

    # ==========================
    # BASE QUERYSETS
    # ==========================
    products = Product.objects.filter(business=business)
    orders = Order.objects.filter(business=business)
    customers = Customer.objects.filter(business=business)
    batches = Batch.objects.filter(business=business)

    # ==========================
    # FILTERS
    # ==========================
    start_date = request.GET.get("start_date")
    end_date = request.GET.get("end_date")
    report_type = request.GET.get("type")  # products, orders, customers, all

    # --------------------------
    # DATE FILTER (APPLY TO ALL)
    # --------------------------
    if start_date:
        products = products.filter(created_at__date__gte=start_date)
        orders = orders.filter(created_at__date__gte=start_date)
        customers = customers.filter(created_at__date__gte=start_date)
        batches = batches.filter(created_at__date__gte=start_date)

    if end_date:
        products = products.filter(created_at__date__lte=end_date)
        orders = orders.filter(created_at__date__lte=end_date)
        customers = customers.filter(created_at__date__lte=end_date)
        batches = batches.filter(created_at__date__lte=end_date)

    # ==========================
    # REPORT TYPE FILTER
    # ==========================
    if report_type == "products":
        orders = None
        customers = None
        batches = None

    elif report_type == "orders":
        products = None
        customers = None
        batches = None

    elif report_type == "customers":
        products = None
        orders = None
        batches = None

    elif report_type == "stock":
        products = None
        orders = None
        customers = None

    # ==========================
    # CONTEXT
    # ==========================
    context = {
        "products": products,
        "orders": orders,
        "customers": customers,
        "batches": batches,
        "start_date": start_date,
        "end_date": end_date,
        "report_type": report_type,
    }

    return render(request, "report.html", context)