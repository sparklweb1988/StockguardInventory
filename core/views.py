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
User = get_user_model()  




# --------------------------
# Signup View
# --------------------------


User = get_user_model()

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

        # Create User (no plan active yet)
        user = User.objects.create_user(username=username, email=email, password=password)
        user.business = business
        user.subscription_end = None   # <-- no plan active
        user.save()

        # Log in
        login(request, user)
        messages.success(request, 'Signup successful! Please choose a plan to start.')

        # Redirect to pricing first
        return redirect('pricing')

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

            # Check subscription
            now_time = timezone.now()
            subscription_end = getattr(user, 'subscription_end', None)

            if subscription_end and subscription_end > now_time:
                return redirect('dashboard')
            else:
                return redirect('pricing')
        else:
            messages.error(request, 'Invalid username or password')
            return redirect('signin')

    return render(request, 'login.html')







# --------------------------
# Logout View
# --------------------------
@login_required
def logout_view(request):
    logout(request)
    return redirect("home")






# -------------------------
# Payment Success (after Paystack)
# -------------------------
PLAN_DURATION_DAYS = {
    'starter': 30,
    'professional': 30,
    'business': 30
}

def payment_success(request, plan_name):
    user = request.user
    plan_name = plan_name.lower()

    if plan_name not in PLAN_DURATION_DAYS:
        messages.error(request, "Invalid plan.")
        return redirect("dashboard")

    now = timezone.now()
    duration_days = PLAN_DURATION_DAYS[plan_name]

    # Extend plan if already active
    if user.subscription_end and user.subscription_end > now:
        new_end = user.subscription_end + timedelta(days=duration_days)
    else:
        new_end = now + timedelta(days=duration_days)

    user.subscription_end = new_end
    user.subscription_plan = plan_name   # optional field to store plan
    user.save()

    messages.success(
        request,
        f"Payment successful! You are now on the {plan_name.title()} plan until {new_end.strftime('%d %b %Y')}."
    )
    return redirect("dashboard")



# --------------------------
# Pricing Page
# --------------------------

def pricing_view(request):

    if request.user.subscription_active:
        return redirect("dashboard")

    plans = [
        {"name": "Starter", "pay_url": "https://paystack.shop/pay/gzlmfb1q8x"},
        {"name": "Professional", "pay_url": "https://paystack.shop/pay/b2hi35ebej"},
        {"name": "Business", "pay_url": "https://paystack.shop/pay/058chi19tu"},
    ]

    return render(request, "pricing.html", {"plans": plans})







def verify_payment(request):

    reference = request.GET.get("reference")

    if not reference:
        messages.error(request, "Payment reference missing")
        return redirect("pricing")

    url = f"https://api.paystack.co/transaction/verify/{reference}"

    headers = {
        "Authorization": f"Bearer {settings.PAYSTACK_SECRET_KEY}"
    }

    response = requests.get(url, headers=headers)
    data = response.json()

    if data["status"] and data["data"]["status"] == "success":

        amount = data["data"]["amount"] / 100
        user = request.user

        # Determine plan based on amount
        if amount == 5000:
            plan = "starter"
        elif amount == 10000:
            plan = "professional"
        elif amount == 25000:
            plan = "business"
        else:
            messages.error(request, "Invalid payment amount")
            return redirect("pricing")

        duration = 30
        now = timezone.now()

        if user.subscription_end and user.subscription_end > now:
            new_end = user.subscription_end + timedelta(days=duration)
        else:
            new_end = now + timedelta(days=duration)

        user.plan = plan
        user.subscription_end = new_end
        user.save()

        messages.success(request, "Payment verified! Subscription activated.")
        return redirect("dashboard")

    messages.error(request, "Payment verification failed")
    return redirect("pricing")



# --------------------------
# Home / Dashboard
# --------------------------
def home(request):
    return render(request, "home.html")







# -------------------------


@login_required
def dashboard(request):
    user = request.user
    business = getattr(user, 'business', None)

    now_time = timezone.now()
    current_month = now_time.month
    current_year = now_time.year

    # Summary counts
    total_products = Product.objects.filter(business=business).count()
    total_customers = Customer.objects.filter(business=business).count()
    total_orders = Order.objects.filter(business=business).count()

    # Orders this month
    orders_this_month = Order.objects.filter(
        business=business,
        status='paid',
        created_at__year=current_year,
        created_at__month=current_month
    )

    total_sales = orders_this_month.aggregate(total=Sum('total'))['total'] or 0
    order_items = OrderItem.objects.filter(order__in=orders_this_month)
    total_profit = sum(
        (item.total_price - (item.product.cost_price * item.quantity))
        for item in order_items
    )

    # Product-wise sales/profit
    product_data = defaultdict(lambda: {'sales': 0, 'profit': 0})
    for item in order_items:
        product_data[item.product.name]['sales'] += item.total_price
        product_data[item.product.name]['profit'] += item.total_price - (item.product.cost_price * item.quantity)

    product_labels = list(product_data.keys())
    product_sales_values = [data['sales'] for data in product_data.values()]
    product_profit_values = [data['profit'] for data in product_data.values()]

    # Subscription status
    subscription_active = user.subscription_end and user.subscription_end > now_time
    subscription_end = user.subscription_end

    # Available plans
    plans = [
        {"name": "Starter", "pay_url": "https://paystack.shop/pay/gzu54tykc6"},
        {"name": "Professional", "pay_url": "https://paystack.shop/pay/b2hi35ebej"},
        {"name": "Business", "pay_url": "https://paystack.shop/pay/058chi19tu"},
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
        "profile": user,               # user acts as profile in template
        "subscription_active": subscription_active,
        "subscription_end": subscription_end,
        "plans": plans,
        "now": now_time,
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
    if request.method == "POST":
        Product.objects.create(
            business=request.user.business,
            name=request.POST["name"],
            sku=request.POST["sku"],
            cost_price=request.POST["cost_price"],
            selling_price=request.POST["selling_price"]
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


  


