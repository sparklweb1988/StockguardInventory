from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.utils import timezone
from django.contrib.auth import authenticate, login, logout
from django.contrib import messages
from django.contrib.auth import get_user_model
from .models import Product, Customer, Order, OrderItem, Batch, Invoice, Business
from django.http import HttpResponse

User = get_user_model()  

# --------------------------
# Signup View
# --------------------------
def signup(request):
    User = get_user_model() 
    if request.method == "POST":
        username = request.POST["username"]
        email = request.POST["email"]
        password = request.POST["password"]
        business_name = request.POST["business_name"]

        if User.objects.filter(username=username).exists():
            messages.error(request, "Username already exists")
            return redirect("signup")

        if User.objects.filter(email=email).exists():
            messages.error(request, "Email already exists")
            return redirect("signup")

        # Create Business
        business = Business.objects.create(name=business_name)

        # Create User and link to business
        user = User.objects.create_user(
            username=username,
            email=email,
            password=password
        )
        user.business = business
        user.save()

        # Log the user in
        login(request, user)
        return redirect("dashboard")

    return render(request, "signup.html")


# --------------------------
# Login View
# --------------------------
def login_view(request):
    if request.method == "POST":
        username = request.POST["username"]
        password = request.POST["password"]

        user = authenticate(request, username=username, password=password)

        if user is not None:
            login(request, user)
            return redirect("dashboard")
        else:
            messages.error(request, "Invalid username or password")
            return redirect("login")

    return render(request, "login.html")


# --------------------------
# Logout View
# --------------------------
def logout_view(request):
    logout(request)
    return redirect("home")


# --------------------------
# Home / Dashboard
# --------------------------
def home(request):
    return render(request, "home.html")


def dashboard(request):
    business = request.user.business
    total_products = Product.objects.filter(business=business).count()
    total_customers = Customer.objects.filter(business=business).count()
    total_orders = Order.objects.filter(business=business).count()

    context = {
        "total_products": total_products,
        "total_customers": total_customers,
        "total_orders": total_orders,
    }
    return render(request, "dashboard.html", context)


# ==============================
# PRODUCTS
# ==============================
def product_list(request):
    products = Product.objects.filter(business=request.user.business)
    return render(request, "product_list.html", {"products": products})


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


def product_delete(request, id):
    product = get_object_or_404(Product, id=id, business=request.user.business)
    if request.method == "POST":
        product.delete()
        return redirect("product_list")
    return render(request, "product_delete.html", {"product": product})


# ==============================
# BATCH
# ==============================
def batch_list(request, product_id):
    product = get_object_or_404(Product, pk=product_id, business=request.user.business)
    batches = product.batches.all()
    return render(request, "batch_list.html", {"product": product, "batches": batches})


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


def batch_update(request, pk):
    batch = get_object_or_404(Batch, pk=pk, business=request.user.business)
    if request.method == "POST":
        batch.batch_number = request.POST["batch_number"]
        batch.quantity = request.POST["quantity"]
        batch.expiry_date = request.POST["expiry_date"]
        batch.save()
        return redirect("batch_list", product_id=batch.product.id)
    return render(request, "batch_update.html", {"batch": batch})


def batch_delete(request, pk):
    batch = get_object_or_404(Batch, pk=pk, business=request.user.business)
    product_id = batch.product.id
    batch.delete()
    return redirect("batch_list", product_id=product_id)


# ==============================
# CUSTOMERS
# ==============================
def customer_list(request):
    customers = Customer.objects.filter(business=request.user.business)
    return render(request, "customer_list.html", {"customers": customers})


def customer_create(request):
    if request.method == "POST":
        Customer.objects.create(
            business=request.user.business,
            name=request.POST["name"],
            phone=request.POST.get("phone")
        )
        return redirect("customer_list")
    return render(request, "customer_create.html")


def customer_update(request, id):
    customer = get_object_or_404(Customer, id=id, business=request.user.business)
    if request.method == "POST":
        customer.name = request.POST["name"]
        customer.phone = request.POST.get("phone")
        customer.save()
        return redirect("customer_list")
    return render(request, "customer_update.html", {"customer": customer})


def customer_delete(request, id):
    customer = get_object_or_404(Customer, id=id, business=request.user.business)
    if request.method == "POST":
        customer.delete()
        return redirect("customer_list")
    return render(request, "customer_delete.html", {"customer": customer})


# ==============================
# ORDERS
# ==============================
def order_list(request):
    orders = Order.objects.filter(business=request.user.business)
    return render(request, "order_list.html", {"orders": orders})


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
def invoice_list(request):
    invoices = Invoice.objects.filter(order__business=request.user.business)
    return render(request, "invoice_list.html", {"invoices": invoices})


def invoice_view(request, order_id):
    order = get_object_or_404(Order, pk=order_id, business=request.user.business)
    invoice, created = Invoice.objects.get_or_create(order=order)
    order_items = order.items.all()

    return render(request, "invoice_view.html", {
        "invoice": invoice,
        "order": order,
        "order_items": order_items
    })