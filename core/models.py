from django.db import models
from django.utils import timezone
from django.contrib.auth.models import User
from datetime import date
from django.utils.text import slugify
# ==========================
# BUSINESS
# ==========================


class Business(models.Model):
    name = models.CharField(max_length=255)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name





class Blog(models.Model):
    author = models.ForeignKey(User, on_delete=models.CASCADE)
    title = models.CharField(max_length=200)
    slug = models.SlugField(unique=True, blank=True)  # 👈 ADD THIS
    content = models.TextField()
    created_at = models.DateField(auto_now_add=True)
    updated_on = models.DateField(auto_now=True)

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.title)
        super().save(*args, **kwargs)

    def __str__(self):
        return self.title


class DemoVideo(models.Model):
    video_file = models.FileField(upload_to="demo_videos/", blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Demo Video {self.id}"
# ==========================
# PRODUCT
# ==========================
class Product(models.Model):
    business = models.ForeignKey(Business, on_delete=models.CASCADE)
    name = models.CharField(max_length=255)
    cost_price = models.DecimalField(max_digits=10, decimal_places=2)
    selling_price = models.DecimalField(max_digits=10, decimal_places=2)
    created_at = models.DateTimeField(auto_now_add=True, null=True)

    def __str__(self):
        return self.name

    # Calculate the total stock by summing up the quantity of all batches
    @property
    def total_stock(self):
        return sum(batch.quantity for batch in self.batches.all())

    # Check if the product has low stock (less than 10 items)
    @property
    def low_stock_warning(self):
        return self.total_stock < 10

    # Check if any of the batches for this product have expired
    @property
    def expired_stock_warning(self):
        # Only return True if any batch's is_expired property says "Expired"
        return any(batch.is_expired == "Expired" for batch in self.batches.all())
    
    
    
    
    
# ==========================
# BATCH
# ==========================
class Batch(models.Model):
    business = models.ForeignKey(Business, on_delete=models.CASCADE)
    product = models.ForeignKey(Product, related_name="batches", on_delete=models.CASCADE)
    batch_number = models.CharField(max_length=100)
    quantity = models.PositiveIntegerField()
    expiry_date = models.DateField()
    created_at = models.DateTimeField(auto_now_add=True, null=True)

    class Meta:
        ordering = ['expiry_date']

    @property
    def is_expired(self):
        """Returns a string indicating expiry status."""
        today = date.today()
        days_left = (self.expiry_date - today).days

        if days_left < 0:
            return "Expired"
        elif days_left <= 7:
            return "Expires in 7 days"
        elif days_left <= 30:
            return "Expires in 1 month"
        elif days_left <= 90:
            return "Expires in 3 months"
        return "Safe"



# ==========================
# CUSTOMER
# ==========================
class Customer(models.Model):
    business = models.ForeignKey(Business, on_delete=models.CASCADE)
    name = models.CharField(max_length=255)
    phone = models.CharField(max_length=20, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True, null=True)
    def __str__(self):
        return self.name




# ==========================
# ORDER
# ==========================
class Order(models.Model):

    STATUS_CHOICES = (
        ('draft', 'Draft'),
        ('paid', 'Paid'),
        ('cancelled', 'Cancelled'),
    )

    business = models.ForeignKey(Business, on_delete=models.CASCADE)
    order_number = models.CharField(max_length=50)
    customer = models.ForeignKey(Customer, on_delete=models.SET_NULL, null=True)

    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="draft")

    subtotal = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    total = models.DecimalField(max_digits=12, decimal_places=2, default=0)

    created_at = models.DateTimeField(auto_now_add=True)  # ⭐ add this

    def calculate_total(self):
        items = self.items.all()
        self.subtotal = sum(item.total_price for item in items)
        self.total = self.subtotal
        self.save()

    def __str__(self):
        return self.customer.name if self.customer else self.order_number
    
    
    
# ==========================
# ORDER ITEM
# ==========================
class OrderItem(models.Model):
    business = models.ForeignKey(Business, on_delete=models.CASCADE)
    order = models.ForeignKey(Order, related_name="items", on_delete=models.CASCADE)
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    quantity = models.PositiveIntegerField()
    price = models.DecimalField(max_digits=10, decimal_places=2)
    total_price = models.DecimalField(max_digits=12, decimal_places=2)
    created_at = models.DateTimeField(auto_now_add=True, null=True)
    def save(self, *args, **kwargs):
        self.total_price = self.quantity * self.price
        super().save(*args, **kwargs)
        
        
        
        
    


# ==========================
# INVOICE
# ==========================
class Invoice(models.Model):
    order = models.OneToOneField(Order, on_delete=models.CASCADE)
    issued_at = models.DateTimeField(auto_now_add=True)
    due_date = models.DateField(default=timezone.now)
    paid = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True, null=True)
    @property
    def invoice_number(self):
        return f"INV-{self.order.order_number}"

    @property
    def customer_name(self):
        return self.order.customer.name if self.order.customer else "Unknown"

    @property
    def total_amount(self):
        return self.order.total
    
    
 
 
 


class Profile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    business = models.OneToOneField(Business, on_delete=models.CASCADE, null=True, blank=True)
    is_paid = models.BooleanField(default=False)
    paystack_customer_code = models.CharField(max_length=100, blank=True, null=True)
    subscription_code = models.CharField(max_length=100, blank=True, null=True)
    subscription_expiry = models.DateTimeField(blank=True, null=True)

    FREE_PRODUCT_LIMIT = 5
    FREE_TRIAL_DAYS = 7

    def has_active_subscription(self):
        """Paid subscription or free trial not expired."""
        if self.is_paid:
            return True
        if self.subscription_expiry and self.subscription_expiry > timezone.now():
            return True
        return False

    def is_trial_active(self):
        """Check if user is in free trial period."""
        return self.subscription_expiry and self.subscription_expiry > timezone.now() and not self.is_paid

    def product_limit(self):
        """Return max products allowed based on plan."""
        return None if self.is_paid else self.FREE_PRODUCT_LIMIT