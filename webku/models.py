# webku/models.py

from django.db import models, transaction
from django.contrib.auth.models import User
from django.contrib import admin
from django.utils.timezone import now


class Makanan(models.Model):
    nama_menu = models.CharField(max_length=100)
    harga = models.DecimalField(max_digits=10, decimal_places=2)
    gambar = models.ImageField(upload_to='makanan_images/')
    stok = models.PositiveIntegerField(default=0)

    def __str__(self):
        return self.nama_menu

class Makanan2(models.Model):
    nama_category = models.CharField(max_length=100)
    harga = models.DecimalField(max_digits=10, decimal_places=2)
    gambar = models.ImageField(upload_to='category_makanan/')
    stok = models.PositiveIntegerField(default=0)
    category = models.CharField(max_length=50, default='', choices=[
        ('Ice Cream', 'Ice Cream'),
        ('Maccarone', 'Maccarone'),
        ('Cookies', 'Cookies'),
        ('Short Cake', 'Short Cake'),
    ])

    def __str__(self):
        return self.nama_category

class UserProfileAdmin(models.Model):
    list_display = ('user', 'full_name', 'user_email', 'last_login', 'is_active')

    # Fungsi untuk menampilkan email dari User
    def user_email(self, obj):
        return obj.user.email
    user_email.short_description = 'Email'

    # Fungsi untuk menampilkan login terakhir dari User
    def last_login(self, obj):
        return obj.user.last_login
    last_login.short_description = 'Last Login'

    # Fungsi untuk menampilkan status aktif
    def is_active(self, obj):
        return obj.user.is_active
    is_active.short_description = 'Active'
    is_active.boolean = True

class LoginHistory(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    email = models.EmailField()
    login_time = models.DateTimeField(default=now)
    ip_address = models.GenericIPAddressField(null=True)  # tambahkan null=True untuk antisipasi jika IP tidak terdeteksi
    
    class Meta:
        verbose_name_plural = "Login histories"  # untuk nama yang lebih baik di admin panel
        ordering = ['-login_time']  # urutkan dari login terbaru
    
    def __str__(self):
        return f"{self.user.username} logged in at {self.login_time}"

class Profile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    phone_number = models.CharField(max_length=15, default='+62 000000000')
    gender = models.CharField(max_length=10, choices=[('Male', 'Male'), ('Female', 'Female'), ('Other', 'Other')], default='Male')
    birth_date = models.DateField(default=now)
    balance = models.DecimalField(max_digits=10, decimal_places=2, default=0)

    def __str__(self):
        return f"{self.user.username}'s Profile"
    
class Address(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    full_name = models.CharField(max_length=255)
    phone = models.CharField(max_length=20)
    province = models.CharField(max_length=100)
    city = models.CharField(max_length=100)
    postal_code = models.CharField(max_length=10)
    housing_address = models.CharField(max_length=255)

    def __str__(self):
        return self.full_name
    
class Client(models.Model):
    username = models.CharField(max_length=100)
    email = models.EmailField()

    def __str__(self):
        return self.username
    
class TopUpRequest(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    amount = models.PositiveIntegerField()  # Jumlah yang diminta untuk top-up
    status = models.CharField(max_length=10, choices=[('Pending', 'Pending'), ('Approved', 'Approved'), ('Rejected', 'Rejected')], default='Pending')
    requested_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Permintaan top-up oleh {self.user.username} sebesar {self.amount} IDR"
    
class TransactionHistory(models.Model):
    STATUS_CHOICES = [
        ('Approved', 'Approved'),
        ('Rejected', 'Rejected'),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES)
    description = models.TextField()  # Pastikan kolom description ada
    processed_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user.username} - {self.status} - {self.amount}"
    
class HistoryLog(models.Model):
    ACTION_CHOICES = [
        ('create', 'Create'),
        ('update', 'Update'),
        ('delete', 'Delete'),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE)
    action = models.CharField(max_length=10, choices=ACTION_CHOICES)
    timestamp = models.DateTimeField(default=now)
    old_data = models.JSONField(null=True, blank=True)
    new_data = models.JSONField(null=True, blank=True)

    def __str__(self):
        return f"{self.action} - {self.user.username} at {self.timestamp}"
    
class Order(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
        ('processing', 'Processing'),
    ]
    
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    total_price = models.DecimalField(max_digits=10, decimal_places=2)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Order #{self.id} - {self.get_status_display()}"

class OrderItem(models.Model):
    order = models.ForeignKey(Order, related_name='items', on_delete=models.CASCADE)
    makanan = models.ForeignKey(Makanan, on_delete=models.CASCADE)
    quantity = models.PositiveIntegerField()
    harga_total = models.DecimalField(max_digits=10, decimal_places=2)

    def save(self, *args, **kwargs):
        with transaction.atomic():
            if self.makanan.stok < self.quantity:
                raise ValueError(f"Stok untuk {self.makanan.nama_menu} tidak cukup untuk quantity yang diminta.")
            self.harga_total = self.makanan.harga * self.quantity
            self.makanan.stok -= self.quantity
            self.makanan.save()
            super().save(*args, **kwargs)











