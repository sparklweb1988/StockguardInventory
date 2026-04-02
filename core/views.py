from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.utils import timezone
from django.contrib.auth import authenticate, login, logout
from django.contrib import messages
from django.contrib.auth import get_user_model
from django.db.models import Sum
from django.http import JsonResponse
from datetime import timedelta
from collections import defaultdict
import requests
from .models import Product, Customer, Order, OrderItem, Batch, Invoice, Business,Profile
from .decorators import subscription_required
from .models import Profile
from django.conf import settings
import json, requests





# Use the key like this
# secret_key = settings.PAYSTACK_SECRET_KEY


# views.py


User = get_user_model()




from datetime import timedelta
from django.utils import timezone

def signup(request):
    if request.method == "POST":
        username = request.POST.get("username")
        email = request.POST.get("email")
        password = request.POST.get("password")
        business_name = request.POST.get("business_name")

        if User.objects.filter(username=username).exists():
            messages.error(request, "Username already exists")
            return redirect("signup")

        if User.objects.filter(email=email).exists():
            messages.error(request, "Email already exists")
            return redirect("signup")

        # Create Business
        business = Business.objects.create(name=business_name)

        # Create User
        user = User.objects.create_user(
            username=username,
            email=email,
            password=password
        )

        # Attach business to user (if your User model has it)
        user.business = business
        user.save()

        # Login the user
        login(request, user)

        messages.success(request, "Signup successful! Your 7-day free trial has started.")

        return redirect('dashboard')

    return render(request, "signup.html")

# --------------------------
# Login View
# --------------------------




def login_view(request):
    if request.method == "POST":
        username = request.POST.get("username")
        password = request.POST.get("password")

        user = authenticate(request, username=username, password=password)
        if user:
            login(request, user)
            profile = user.profile

            # Redirect based on plan status
            if profile.is_trial_active() or profile.is_active():
                return redirect('dashboard')
            else:
                return redirect('pricing')

        messages.error(request, "Invalid credentials")
        return redirect("login")

    return render(request, "login.html")

# --------------------------
# Logout View
# --------------------------
@login_required
def logout_view(request):
    logout(request)
    return redirect("home")








# --------------------------
# Home / Dashboard
# --------------------------
def home(request):
    return render(request, "home.html")






# -------------------------

@login_required
def dashboard(request):
    user = request.user
    profile = user.profile
    business = getattr(user, 'business', None)
    now = timezone.now()

    # ---------------------
    # PLAN / TRIAL CHECK
    # ---------------------
    # Free trial logic: 7 days free
    trial_active = profile.plan == 'free' and (
        profile.plan_expiry is None or profile.plan_expiry > now
    )

    # Paid subscription logic
    subscription_active = profile.plan != 'free' and profile.is_active()

    # Redirect paid users if their subscription expired
    if profile.plan != 'free' and not subscription_active:
        return redirect('pricing')

    # Calculate remaining days for trial
    trial_days_remaining = 0
    if trial_active and profile.plan_expiry:
        trial_days_remaining = (profile.plan_expiry - now).days

    # ---------------------
    # DASHBOARD STATS
    # ---------------------
    current_month = now.month
    current_year = now.year

    total_products = Product.objects.filter(
        business=business,
        created_at__year=current_year,
        created_at__month=current_month
    ).count()

    total_customers = Customer.objects.filter(
        business=business,
        created_at__year=current_year,
        created_at__month=current_month
    ).count()

    orders_this_month = Order.objects.filter(
        business=business,
        status='paid',
        created_at__year=current_year,
        created_at__month=current_month
    )
    total_orders = orders_this_month.count()
    total_sales = orders_this_month.aggregate(total=Sum('total'))['total'] or 0

    order_items = OrderItem.objects.filter(order__in=orders_this_month)
    total_profit = sum(
        (item.total_price - item.product.cost_price * item.quantity)
        for item in order_items
    )

    # Product-wise sales and profit
    product_data = defaultdict(lambda: {'sales': 0, 'profit': 0})
    for item in order_items:
        product_data[item.product.name]['sales'] += item.total_price
        product_data[item.product.name]['profit'] += (
            item.total_price - item.product.cost_price * item.quantity
        )

    product_labels = list(product_data.keys())
    product_sales_values = [v['sales'] for v in product_data.values()]
    product_profit_values = [v['profit'] for v in product_data.values()]

    # Weekly sales
    weekly_sales = [0, 0, 0, 0]
    for order in orders_this_month:
        day = order.created_at.day
        week_index = min((day - 1) // 7, 3)
        weekly_sales[week_index] += order.total

    total_expired_products = Product.objects.filter(
        business=business,
        batches__expiry_date__lt=now.date()
    ).distinct().count()

    plans = [
        {"name": "Starter", "price": 5000, "link": "https://paystack.shop/pay/hdmy3drkw5"},
        {"name": "Professional", "price": 10000, "link": "https://paystack.shop/pay/z82uimy46i"},
        {"name": "Business", "price": 25000, "link": "https://paystack.shop/pay/h-cvl5ma5r"},
    ]

    context = {
        "total_products": total_products,
        "total_customers": total_customers,
        "total_orders": total_orders,
        "total_expired_products": total_expired_products,
        "total_sales": total_sales,
        "total_profit": total_profit,
        "product_labels": product_labels,
        "product_sales_values": product_sales_values,
        "product_profit_values": product_profit_values,
        "weekly_sales": weekly_sales,
        "profile": profile,
        "subscription_active": subscription_active,
        "trial_active": trial_active,
        "trial_days_remaining": trial_days_remaining,
        "subscription_end": profile.plan_expiry,
        "plans": plans,
        "now": now,
    }

    return render(request, "dashboard.html", context)

# ==============================
# PRODUCTS
# ==============================





@login_required
def product_list(request):
    products = Product.objects.filter(business=request.user.business)
    return render(request, "product_list.html", {"products": products})



@login_required
@subscription_required
def product_create(request):
    user = request.user
    profile = user.profile
    business = user.business

    current_count = Product.objects.filter(business=business).count()
    limit = profile.product_limit()

    if limit is not None and current_count >= limit:
        messages.error(
            request,
            f"You reached your limit of {limit} products. Upgrade your plan."
        )
        return redirect("dashboard")

    if request.method == "POST":
        Product.objects.create(
            business=business,
            name=request.POST.get("name"),
            sku=request.POST.get("sku"),
            cost_price=request.POST.get("cost_price"),
            selling_price=request.POST.get("selling_price"),
        )
        return redirect("product_list")

    return render(request, "product_create.html")





@login_required
def product_update(request, id):
    product = get_object_or_404(Product, id=id, business=request.user.business)
    if request.method == "POST":
        product.name = request.POST["name"]
        product.sku = request.POST["sku"]
        product.cost_price = request.POST["cost_price"]
        product.selling_price = request.POST["selling_price"]
        product.save()
        return redirect("product_list")
    return render(request, "product_update.html", {"product": product})




@login_required
def product_delete(request, id):
    product = get_object_or_404(Product, id=id, business=request.user.business)
    if request.method == "POST":
        product.delete()
        return redirect("product_list")
    return render(request, "product_delete.html", {"product": product})


# ==============================
# BATCH
# ==============================
@login_required
def batch_list(request, product_id):
    product = get_object_or_404(Product, pk=product_id, business=request.user.business)
    batches = product.batches.all()
    return render(request, "batch_list.html", {"product": product, "batches": batches})




@login_required
def batch_create(request, product_id):
    product = get_object_or_404(Product, pk=product_id, business=request.user.business)
    if request.method == "POST":
        Batch.objects.create(
            business=request.user.business,
            product=product,
            batch_number=request.POST["batch_number"],
            quantity=request.POST["quantity"],
            expiry_date=request.POST["expiry_date"]
        )
        return redirect("batch_list", product_id=product.id)
    return render(request, "batch_create.html", {"product": product})






@login_required
def batch_update(request, pk):
    batch = get_object_or_404(Batch, pk=pk, business=request.user.business)
    if request.method == "POST":
        batch.batch_number = request.POST["batch_number"]
        batch.quantity = request.POST["quantity"]
        batch.expiry_date = request.POST["expiry_date"]
        batch.save()
        return redirect("batch_list", product_id=batch.product.id)
    return render(request, "batch_update.html", {"batch": batch})




@login_required
def batch_delete(request, pk):
    batch = get_object_or_404(Batch, pk=pk, business=request.user.business)
    product_id = batch.product.id
    batch.delete()
    return redirect("batch_list", product_id=product_id)


# ==============================
# CUSTOMERS
# ==============================



@login_required
def customer_list(request):
    customers = Customer.objects.filter(business=request.user.business)
    return render(request, "customer_list.html", {"customers": customers})




@login_required
def customer_create(request):
    if request.method == "POST":
        Customer.objects.create(
            business=request.user.business,
            name=request.POST["name"],
            phone=request.POST.get("phone")
        )
        return redirect("customer_list")
    return render(request, "customer_create.html")




@login_required
def customer_update(request, id):
    customer = get_object_or_404(Customer, id=id, business=request.user.business)
    if request.method == "POST":
        customer.name = request.POST["name"]
        customer.phone = request.POST.get("phone")
        customer.save()
        return redirect("customer_list")
    return render(request, "customer_update.html", {"customer": customer})




@login_required
def customer_delete(request, id):
    customer = get_object_or_404(Customer, id=id, business=request.user.business)
    if request.method == "POST":
        customer.delete()
        return redirect("customer_list")
    return render(request, "customer_delete.html", {"customer": customer})


# ==============================
# ORDERS
# ==============================


@login_required
def order_list(request):
    orders = Order.objects.filter(business=request.user.business)
    return render(request, "order_list.html", {"orders": orders})




@login_required
def order_create(request):
    products = Product.objects.filter(business=request.user.business)
    customers = Customer.objects.filter(business=request.user.business)

    if request.method == "POST":
        customer_id = request.POST.get("customer")
        customer = Customer.objects.get(id=customer_id)
        
        order = Order.objects.create(
            business=request.user.business,
            order_number=f"ORD-{timezone.now().strftime('%Y%m%d%H%M%S')}",
            customer=customer,
        )

        for product in products:
            qty_str = request.POST.get(f"quantity_{product.id}", '').strip()
            try:
                qty = int(qty_str) if qty_str else 0
            except ValueError:
                qty = 0

            if qty > 0:
                OrderItem.objects.create(
                    business=request.user.business,
                    order=order,
                    product=product,
                    quantity=qty,
                    price=product.selling_price,
                    total_price=qty * product.selling_price,
                )

                remaining = qty
                for batch in product.batches.filter(quantity__gt=0).order_by('expiry_date'):
                    if batch.quantity >= remaining:
                        batch.quantity -= remaining
                        batch.save()
                        break
                    else:
                        remaining -= batch.quantity
                        batch.quantity = 0
                        batch.save()

        order.calculate_total()
        return redirect("order_list")

    return render(request, "order_create.html", {"products": products, "customers": customers})



@login_required
def change_order_status(request, pk):
    business = request.user.business
    order = get_object_or_404(Order, pk=pk, business=business)
    new_status = request.POST["status"]

    if order.status != "paid" and new_status == "paid":
        for item in order.items.all():
            remaining = item.quantity
            for batch in Batch.objects.filter(business=business, product=item.product, quantity__gt=0, expiry_date__gte=timezone.now().date()).order_by("expiry_date"):
                if batch.quantity >= remaining:
                    batch.quantity -= remaining
                    batch.save()
                    remaining = 0
                    break
                else:
                    remaining -= batch.quantity
                    batch.quantity = 0
                    batch.save()
            if remaining > 0:
                raise Exception(f"Not enough stock for {item.product.name}")

    if order.status == "paid" and new_status == "cancelled":
        for item in order.items.all():
            batch = Batch.objects.filter(business=business, product=item.product).order_by("-expiry_date").first()
            if batch:
                batch.quantity += item.quantity
                batch.save()

    order.status = new_status
    order.save()
    return redirect("order_list")


# ==============================
# STATIC PAGES
# ==============================
def about(request):
    return render(request, "about.html")


def terms(request):
    return render(request, "terms.html")


def privacy(request):
    return render(request, "privacy.html")


def contact(request):
    return render(request, "contact.html")


# ==============================
# INVOICES (HTML Only)
# ==============================
@login_required
def invoice_list(request):
    invoices = Invoice.objects.filter(order__business=request.user.business)
    return render(request, "invoice_list.html", {"invoices": invoices})

@login_required
def invoice_view(request, order_id):
    order = get_object_or_404(Order, pk=order_id, business=request.user.business)
    invoice, created = Invoice.objects.get_or_create(order=order)
    order_items = order.items.all()

    return render(request, "invoice_view.html", {
        "invoice": invoice,
        "order": order,
        "order_items": order_items

    })


  






# PAYSTACK


from django.contrib.auth.decorators import login_required

@login_required
def pricing(request):
    profile = request.user.profile
    # Only redirect to dashboard if plan is active (paid), not expired
    if profile.plan != 'free' and profile.is_active():
        return redirect('dashboard')
    
    # Otherwise render pricing page
    plans = [
        {"name": "Starter", "price": 5000, "link": "https://paystack.shop/pay/hdmy3drkw5"},
        {"name": "Professional", "price": 10000, "link": "https://paystack.shop/pay/z82uimy46i"},
        {"name": "Business", "price": 25000, "link": "https://paystack.shop/pay/h-cvl5ma5r"},
    ]
    return render(request, 'pricing.html', {"plans": plans})

# PAYMENT SUCCESS + VERIFICATION





@login_required
def paystack_verify(request):
    """
    AJAX endpoint to verify Paystack transaction and assign plan
    """
    if request.method != "POST":
        return JsonResponse({"status": "failed", "message": "Invalid method"}, status=400)

    data = json.loads(request.body)
    reference = data.get("reference")
    plan = data.get("plan")

    if not reference or not plan:
        return JsonResponse({"status": "failed", "message": "Missing reference or plan"}, status=400)

    # Verify transaction with Paystack
    url = f"https://api.paystack.co/transaction/verify/{reference}"
    headers = {"Authorization": f"Bearer {settings.PAYSTACK_SECRET_KEY}"}
    resp = requests.get(url, headers=headers)
    result = resp.json()

    if result.get("status") and result["data"]["status"] == "success":
        profile = request.user.profile

        # Prevent duplicate reference updates
        if profile.paystack_ref == reference:
            return JsonResponse({"status": "success"})

        profile.paystack_ref = reference
        plan_lower = plan.lower()

        # Assign plan and expiry
        if plan_lower == "starter":
            profile.plan = "starter"
            profile.plan_expiry = timezone.now() + timedelta(days=30)
        elif plan_lower == "professional":
            profile.plan = "professional"
            profile.plan_expiry = timezone.now() + timedelta(days=30)
        elif plan_lower == "business":
            profile.plan = "business"
            profile.plan_expiry = timezone.now() + timedelta(days=30)
        else:
            return JsonResponse({"status": "failed", "message": "Invalid plan"}, status=400)

        profile.save()
        return JsonResponse({"status": "success"})

    return JsonResponse({"status": "failed", "message": "Transaction verification failed"})






@login_required
def payment_success(request):
    """
    Show success page after verified Paystack payment
    """
    reference = request.GET.get("reference")
    plan = request.GET.get("plan")

    if not reference or not plan:
        return redirect("pricing")

    profile = request.user.profile

    # Only allow access if the reference matches
    if profile.paystack_ref != reference:
        return redirect("pricing")

    # Display plan & expiry
    context = {
        "user": request.user,
        "plan": plan.title(),
        "subscription_end": profile.plan_expiry,
    }

    return render(request, "payment_success.html", context)




