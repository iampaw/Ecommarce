from django.contrib import admin
from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User
from django.contrib.auth.admin import UserAdmin
from .models import (
    Makanan, Makanan2, LoginHistory, Address, TransactionHistory, 
    TopUpRequest, Profile, Order, OrderItem
)
from django.http import HttpResponseRedirect
from django.urls import path

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
    list_filter = ('user', 'login_time')
    search_fields = ('user__username', 'email', 'ip_address')

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

class OrderItemInline(admin.TabularInline):
    model = OrderItem
    readonly_fields = ['makanan', 'quantity', 'harga_total']
    can_delete = False
    extra = 0

@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ['id', 'user', 'total_price', 'status', 'created_at']
    list_filter = ['status']
    search_fields = ['user__username']
    inlines = [OrderItemInline]
    readonly_fields = ['total_price', 'created_at']

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path('<path:object_id>/approve/', self.admin_site.admin_view(self.approve_view), name='order_approve'),
            path('<path:object_id>/reject/', self.admin_site.admin_view(self.reject_view), name='order_reject'),
            path('<path:object_id>/pending/', self.admin_site.admin_view(self.pending_view), name='order_pending'),
        ]
        return custom_urls + urls

    def approve_view(self, request, object_id):
        order = self.get_object(request, object_id)
        if order:
            order.status = 'approved'
            order.save()
        return HttpResponseRedirect('../')

    def reject_view(self, request, object_id):
        order = self.get_object(request, object_id)
        if order:
            order.status = 'rejected'
            order.save()
        return HttpResponseRedirect('../')

    def pending_view(self, request, object_id):
        order = self.get_object(request, object_id)
        if order:
            order.status = 'pending'
            order.save()
        return HttpResponseRedirect('../')
    
@admin.register(OrderItem)
class OrderItemAdmin(admin.ModelAdmin):
    list_display = ['order', 'makanan', 'quantity', 'harga_total']
    list_filter = ['order']
    search_fields = ['order__id', 'makanan__nama_menu']