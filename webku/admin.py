from django.contrib import admin
from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User
from django.contrib.auth.admin import UserAdmin
from .models import (
    Makanan, Makanan2, LoginHistory, Address, TransactionHistory, 
    TopUpRequest, Profile
)

# Pendaftaran Model
@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'phone_number', 'gender', 'birth_date', 'balance')

@admin.register(Makanan)
class MakananAdmin(admin.ModelAdmin):
    list_display = ('nama_menu', 'harga', 'stok')

@admin.register(Makanan2)
class Makanan2Admin(admin.ModelAdmin):
    list_display = ('nama_category', 'harga', 'stok')

@admin.register(LoginHistory)
class LoginHistoryAdmin(admin.ModelAdmin):
    list_display = ('user', 'email', 'login_time', 'ip_address')
    search_fields = ('user__username', 'email')
    list_filter = ('login_time',)

@admin.register(Address)
class AddressAdmin(admin.ModelAdmin):
    list_display = ('user', 'full_name', 'phone', 'city', 'postal_code')

@admin.register(TransactionHistory)
class TransactionHistoryAdmin(admin.ModelAdmin):
    list_display = ('user', 'amount', 'status', 'processed_at')
    list_filter = ('status', 'processed_at')
    search_fields = ('user__username',)

@admin.register(TopUpRequest)
class TopUpRequestAdmin(admin.ModelAdmin):  
    list_display = ('user', 'amount', 'status', 'requested_at')
    list_filter = ('status',)
    actions = ['delete_selected']

# Custom User Creation Form
class SignupForm(UserCreationForm):
    email = forms.EmailField(required=True)

    class Meta:
        model = User
        fields = ['username', 'email', 'password1', 'password2']

# Custom User Admin
class CustomUserAdmin(admin.ModelAdmin):
    list_display = ('username', 'email', 'last_login', 'is_active', 'is_staff')
    list_filter = ('is_active', 'is_staff')
    search_fields = ('username', 'email')

admin.site.unregister(User)  # Unregister default User
admin.site.register(User, CustomUserAdmin)