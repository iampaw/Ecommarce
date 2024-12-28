from django.urls import path, include
from . import views
from django.contrib.auth import views as auth_views
from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from .views import check_profile_exists
from .views import kurangi_stok


urlpatterns = [
    path('', views.home_page, name='home'),
    path('signup/', views.signup, name='signup'),
    path('logout/', views.logout_view, name='logout'),
    path('login/', auth_views.LoginView.as_view(template_name='signup.html'), name='login'),
    path('checkout/', views.checkout, name='checkout'),
    path('profile/', views.profile, name='profile'),
    path('profile/<str:username>/', views.profile_view, name='profile'),
    path('address/', views.address_view, name='address'),
    path('profile/topup/', views.top_up_balance, name='top_up_balance'),
    path('request-top-up/', views.request_top_up, name='request_top_up'),
    path('dashboard/top-up-requests/', views.admin_top_up_requests, name='admin_top_up_requests'),
    path('dashboard/approve-top-up/<int:request_id>/', views.approve_top_up, name='approve_top_up'),
    path('dashboard/reject-top-up/<int:request_id>/', views.reject_top_up, name='reject_top_up'),
    path('check-profile/<str:username>/', check_profile_exists, name='check_profile_exists'),
    path('order_success/', views.order_success, name='order_success'),
    path('add_to_cart/', views.add_to_cart, name='add_to_cart'),
    path('get_cart/', views.get_cart, name='get_cart'),
    path('order_status/<int:order_id>/', views.get_order_status, name='order_status'),
    path('admin/order/<int:order_id>/', views.order_admin_detail, name='admin_order_detail'),
    path('admin/order/<int:order_id>/approve/', views.approve_order, name='approve_order'),
    path('admin/order/<int:order_id>/reject/', views.reject_order, name='reject_order'),
    path('admin/order/<int:order_id>/pending/', views.set_pending, name='set_pending'),
    path('admin/order/<int:order_id>/status/', views.update_order_status, name='update_order_status'),
    path('update_balance/', views.update_balance, name='update_balance'),
    path('kurangi-stok/', kurangi_stok, name='kurangi_stok'),

    path('order/<int:order_id>/add-item/', views.add_order_item, name='add_order_item'),
    path('order/<int:order_id>/remove-item/<int:item_id>/', views.remove_order_item, name='remove_order_item'),
    path('order/<int:order_id>/update-item/<int:item_id>/', views.update_order_item_quantity, name='update_order_item_quantity'),
    path('order/<int:order_id>/items/', views.list_order_items, name='list_order_items'),
    path('order/<int:order_id>/item/<int:item_id>/', views.order_item_detail, name='order_item_detail'),
    

    # Django admin URL setelah custom admin URLs
    path('admin/', admin.site.urls),
    
    # URL patterns lainnya
    path('', views.home_page, name='home'),
    path('signup/', views.signup, name='signup'),



]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)