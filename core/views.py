from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.utils import timezone
from django.contrib.auth import authenticate, login, logout
from django.contrib import messages
from django.contrib.auth import get_user_model
from .models import Product, Customer, Order, OrderItem, Batch, Invoice, Business
from django.http import HttpResponse
from django.db.models import Sum, F, ExpressionWrapper, DecimalField
from django.utils.timezone import now
from datetime import datetime
from datetime import timedelta
import requests
from django.conf import settings
from collections import defaultdict
from django.urls import reverse
import json
from django.views.decorators.csrf import csrf_exempt
from django.http import JsonResponse
import json







User = get_user_model()

# --------------------------
# Signup View
# --------------------------


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
        user.business = business
        user.save()

        # Start 7-day free trial
        user.start_trial()  # uses the method in your User model
        # This automatically sets plan='free_trial', trial_start, subscription_end

        # Log in
        login(request, user)
        messages.success(
            request,
            'Signup successful! Your 7-day free trial has started.'
        )

        # Redirect to dashboard (trial is active)
        return redirect('dashboard')

    return render(request, 'signup.html')


# --------------------------
# Login View
# --------------------------
def login_view(request):
    if request.method == "POST":
        username = request.POST.get("username")
        password = request.POST.get("password")
        user = authenticate(request, username=username, password=password)

        if user is not None:
            login(request, user)
            messages.success(request, 'Login successful!')

            # Check if subscription OR trial is active
            now_time = timezone.now()
            if getattr(user, 'subscription_end', None) and user.subscription_end > now_time:
                return redirect('dashboard')
            elif getattr(user, 'trial_end', None) and user.trial_end > now_time:
                return redirect('dashboard')
            else:
                # No active subscription or trial
                messages.info(request, "Your trial or subscription has expired. Please choose a plan.")
                return redirect('pricing')
        else:
            messages.error(request, 'Invalid username or password')
            return redirect('login')

    return render(request, 'login.html')



# --------------------------
# Logout View
# --------------------------
@login_required
def logout_view(request):
    logout(request)
    return redirect("home")









@login_required
def initialize_payment(request, plan):

    user = request.user
    plan_code = settings.PAYSTACK_PLANS.get(plan)

    headers = {
        "Authorization": f"Bearer {settings.PAYSTACK_SECRET_KEY}",
        "Content-Type": "application/json"
    }

    data = {
        "email": user.email,
        "plan": plan_code,
        "callback_url": request.build_absolute_uri("/payment/verify/")
    }

    response = requests.post(
        f"{settings.PAYSTACK_BASE_URL}/transaction/initialize",
        json=data,
        headers=headers
    )

    res = response.json()

    if res["status"]:
        return redirect(res["data"]["authorization_url"])







@login_required
def verify_payment(request):

    reference = request.GET.get("reference")

    headers = {
        "Authorization": f"Bearer {settings.PAYSTACK_SECRET_KEY}"
    }

    response = requests.get(
        f"{settings.PAYSTACK_BASE_URL}/transaction/verify/{reference}",
        headers=headers
    )

    res = response.json()

    if res["status"] and res["data"]["status"] == "success":

        user = request.user
        user.plan = res["data"]["plan"]["name"].lower()

        # 30 day subscription
        user.subscription_end = timezone.now() + timedelta(days=30)

        user.save()

        return render(request, "payment_success.html")

    return render(request, "payment_failed.html")







@csrf_exempt
def paystack_webhook(request):

    payload = json.loads(request.body)

    event = payload["event"]

    if event == "invoice.payment_success":

        email = payload["data"]["customer"]["email"]

        user = User.objects.get(email=email)

        from datetime import timedelta
        from django.utils import timezone

        user.subscription_end = timezone.now() + timedelta(days=30)
        user.save()

    return HttpResponse(status=200)





@login_required
def start_trial(request):
    user = request.user
    if user.plan != 'free_trial' and not user.subscription_end:
        # Start 7-day free trial
        user.plan = 'free_trial'
        user.trial_start = timezone.now()
        user.subscription_end = timezone.now() + timedelta(days=7)
        user.save()
        messages.success(request, "Your 7-day free trial has started!")
    else:
        messages.info(request, "You already have an active trial or paid plan.")
    return redirect("dashboard")




def pricing(request):
    # Define your plans here, or pass from settings
    plans = [
        {"name": "Starter", "price": 5000, "pay_url": "#"},
        {"name": "Professional", "price": 15000, "pay_url": "#"},
        {"name": "Business", "price": 50000, "pay_url": "#"},
    ]
    return render(request, "pricing.html", {"plans": plans})







@csrf_exempt
@login_required
def paystack_verify(request):
    import json
    data = json.loads(request.body)
    reference = data.get("reference")
    plan = data.get("plan")

    url = f"https://api.paystack.co/transaction/verify/{reference}"
    headers = {"Authorization": f"Bearer {settings.PAYSTACK_SECRET_KEY}"}
    resp = requests.get(url, headers=headers)
    result = resp.json()

    if result.get("status") == True and result["data"]["status"] == "success":
        # Upgrade plan
        user = request.user
        user.plan = plan.lower()
        user.subscription_end = timezone.now() + timedelta(days=30)  # 1 month subscription
        user.save()
        return JsonResponse({"status": "success"})
    return JsonResponse({"status": "failed"})





@csrf_exempt
@login_required
def paystack_initialize(request):
    if request.method == "POST":
        data = json.loads(request.body)
        plan_name = data.get("plan")
        email = request.user.email
        amount = int(data.get("amount", 0))  # in kobo

        headers = {
            "Authorization": f"Bearer {settings.PAYSTACK_SECRET_KEY}",
            "Content-Type": "application/json",
        }
        payload = {
            "email": email,
            "amount": amount,
            "callback_url": request.build_absolute_uri(reverse("paystack_verify")),
            "metadata": {"plan": plan_name}
        }
        r = requests.post("https://api.paystack.co/transaction/initialize", json=payload, headers=headers)
        response = r.json()
        return JsonResponse(response)
    return JsonResponse({"status": "error", "message": "Invalid request"})

# --------------------------
# Home / Dashboard
# --------------------------
def home(request):
    return render(request, "home.html")



def My_pricing(request):
    return render(request, 'my_price.html')



# -------------------------




@login_required
def dashboard(request):
    user = request.user
    business = getattr(user, 'business', None)

    now = timezone.now()
    current_month = now.month
    current_year = now.year

    # ----------------------
    # Monthly Counts
    # ----------------------
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

    total_orders = Order.objects.filter(
        business=business,
        status='paid',
        created_at__year=current_year,
        created_at__month=current_month
    ).count()

    # ----------------------
    # Monthly Sales & Profit
    # ----------------------
    orders_this_month = Order.objects.filter(
        business=business,
        status='paid',
        created_at__year=current_year,
        created_at__month=current_month
    )

    total_sales = orders_this_month.aggregate(total=Sum('total'))['total'] or 0

    order_items = OrderItem.objects.filter(order__in=orders_this_month)
    total_profit = sum(
        (item.total_price - item.product.cost_price * item.quantity)
        for item in order_items
    )

    # Product-wise sales & profit
    product_data = defaultdict(lambda: {'sales': 0, 'profit': 0})
    for item in order_items:
        product_data[item.product.name]['sales'] += item.total_price
        product_data[item.product.name]['profit'] += (
            item.total_price - item.product.cost_price * item.quantity
        )

    product_labels = list(product_data.keys())
    product_sales_values = [v['sales'] for v in product_data.values()]
    product_profit_values = [v['profit'] for v in product_data.values()]

    # Weekly Sales (splitting by week of month)
    weekly_sales = [0, 0, 0, 0]  # week 1 - 4
    for order in orders_this_month:
        day = order.created_at.day
        week_index = min((day-1)//7, 3)
        weekly_sales[week_index] += order.total

    # Subscription
    subscription_active = user.subscription_end and user.subscription_end > now
    trial_active = user.plan == 'free_trial' and user.subscription_end and user.subscription_end > now
    trial_days_remaining = 0
    if trial_active:
        trial_days_remaining = (user.subscription_end - now).days

    # Plans for upgrade buttons
    plans = [
        {"name": "Starter", "price": 5000},
        {"name": "Professional", "price": 10000},
        {"name": "Business", "price": 25000},
    ]

    context = {
        "total_products": total_products,
        "total_customers": total_customers,
        "total_orders": total_orders,
        "total_sales": total_sales,
        "total_profit": total_profit,
        "product_labels": product_labels,
        "product_sales_values": product_sales_values,
        "product_profit_values": product_profit_values,
        "weekly_sales": weekly_sales,
        "profile": user,
        "subscription_active": subscription_active,
        "trial_active": trial_active,
        "trial_days_remaining": trial_days_remaining,
        "subscription_end": user.subscription_end,
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
def product_create(request):
    user = request.user
    business = user.business

    # Count current products
    current_count = Product.objects.filter(business=business).count()
    limit = user.product_limit

    # Check plan limit
    if limit is not None and current_count >= limit:
        messages.error(
            request,
            f"You have reached your plan limit of {limit} products. Upgrade to add more."
        )
        return redirect("dashboard")

    if request.method == "POST":
        name = request.POST.get("name")
        sku = request.POST.get("sku")
        cost_price = request.POST.get("cost_price")
        selling_price = request.POST.get("selling_price")

        # Validate input
        if not name or not sku or not cost_price or not selling_price :
            messages.error(request, "All fields are required")
            return redirect("product_create")

        # Create product
        Product.objects.create(
            business=business,
            name=name,
            sku=sku,
            cost_price=cost_price,
            selling_price=selling_price
        )
        messages.success(request, "Product added successfully!")
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


  


