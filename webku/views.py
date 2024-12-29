from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, authenticate, logout
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm
from django.contrib import messages
from .models import Makanan, Makanan2, LoginHistory, Profile, Address, Client, TopUpRequest, TransactionHistory, OrderItem, Order, transaction, HistoryLog
from django.http import HttpResponse, JsonResponse
from django.contrib.auth.models import User
from django.utils.timezone import now
import logging, json
from django.contrib.auth.decorators import login_required
from .forms import ProfileForm, UserUpdateForm
from .forms import AddressForm
from django.contrib import messages
from decimal import Decimal, InvalidOperation
from datetime import datetime
from itertools import chain
from django.views.decorators.csrf import csrf_exempt
from django.core.exceptions import ObjectDoesNotExist
from django.contrib.admin.views.decorators import staff_member_required
from django.db import IntegrityError
from django.contrib.auth.signals import user_logged_in
from django.dispatch import receiver
from django.http import HttpResponseForbidden
from django.contrib.auth.decorators import user_passes_test
from django.urls import reverse


logger = logging.getLogger(__name__)


def superuser_required(function):
    def check_superuser(user):
        return user.is_superuser
    decorated_view = user_passes_test(check_superuser, login_url='login')(function)
    return decorated_view

@login_required
def get_cart(request):
    """Get cart contents for authenticated user only"""
    cart = request.session.get('cart', {}).get(str(request.user.id), [])
    return JsonResponse({'cart': cart})

@login_required
def order_status(request, order_id):
    try:
        # Cek apakah order yang diminta milik pengguna yang sedang login
        order = Order.objects.get(id=order_id, user=request.user)
        
        # Mengembalikan status pesanan dan saldo pengguna
        return JsonResponse({
            'status': order.status,
            'user_balance': request.user.profile.balance,
        })
    except Order.DoesNotExist:
        # Jika pesanan tidak ditemukan atau tidak milik pengguna, kembalikan status 404
        return JsonResponse({'error': 'Pesanan tidak ditemukan atau tidak ada akses'}, status=404)
    
@staff_member_required
def order_admin_detail(request, order_id):
    order = get_object_or_404(Order, id=order_id)
    if request.method == 'POST':
        action = request.POST.get('action')
        
        try:
            with transaction.atomic():
                if action == 'approve':
                    order.status = 'approved'
                    messages.success(request, f'Order #{order.id} telah disetujui')
                elif action == 'reject':
                    order.status = 'rejected'
                    messages.success(request, f'Order #{order.id} telah ditolak')
                elif action == 'pending':
                    order.status = 'pending'
                    messages.success(request, f'Order #{order.id} telah diset ke pending')
                
                order.save()
                
                # Jika disetujui, proses item order dan update stok
                if action == 'approve':
                    process_approved_order(order)

        except Exception as e:
            messages.error(request, f'Error: {str(e)}')
            
    context = {
        'order': order,
        'title': f'Order #{order.id} Details',
        'is_popup': False,
        'has_permission': True,
        'site_header': 'Administration',
        'site_title': 'Site Admin',
        'app_label': 'webku',
    }
    return render(request, 'admin/order_admin_detail.html', context)

def process_approved_order(order):
    """Memproses order yang disetujui dengan memperbarui stok dan membuat catatan transaksi"""
    with transaction.atomic():
        # Memperbarui stok untuk setiap item order
        for item in order.items.all():
            makanan = item.makanan
            makanan.stok -= item.quantity
            makanan.save()

        # Mengupdate status order menjadi 'approved'
        order.status = 'approved'
        order.save()

        # Membuat catatan transaksi
        TransactionHistory.objects.create(
            user=order.user,
            amount=order.total_price,
            status='Approved',
            description=f"Order #{order.id} disetujui"
        )

        return order

@login_required
def order_success(request):
    try:
        # Mengambil order terakhir dari user
        order = Order.objects.filter(user=request.user).latest('created_at')

        # Memuat item dengan relasi 'makanan' dan 'makanan2' dengan eager loading
        order_items = order.items.all().select_related('makanan', 'makanan2')
        order_status = order.status
        user_balance = request.user.profile.balance
        total_price_scaled = order.total_price / Decimal(100)

        # Debugging log untuk memastikan makanan2 ada
        print(f"Order ID: {order.id}")
        for item in order_items:
            print(f"Item ID: {item.id}, Makanan: {item.makanan}, Makanan2: {item.makanan2}")
        
        context = {
            'order': order,
            'order_items': order_items,
            'total_price_scaled': total_price_scaled,
            'user_balance': user_balance,
            'order_status': order_status,
        }
        return render(request, 'order_success.html', context)
    except Order.DoesNotExist:
        messages.error(request, "Tidak ada order yang ditemukan")
        return redirect('home')
    
def profile(request):
    # Check if profile exists for current user
    profile_exists = hasattr(request.user, 'profile')
    
    try:
        # Get user's profile if it exists
        profile = request.user.profile if profile_exists else None
        
        return render(request, 'see_profil.html', {
            'user': request.user,
            'profile': profile,
            'profile_exists': profile_exists
        })
    except:
        return render(request, 'see_profil.html', {
            'user': request.user,
            'profile': None,
            'profile_exists': False
        })

def check_profile_exists(request, username):
    try:
        user = User.objects.get(username=username)
        profile_exists = Profile.objects.filter(user=user).exists()
        return JsonResponse({'profile_exists': profile_exists})
    except User.DoesNotExist:
        return JsonResponse({'error': 'User not found'}, status=404)

def home_page(request):
    # Fetch all Makanan and Makanan2 objects
    makanan_list = Makanan.objects.all()  # Fetch all Makanan objects
    makanan2_list = Makanan2.objects.all()  # Fetch all Makanan2 objects
    
    # Return the rendered response with both lists
    return render(request, 'home.html', {
        'makanan_list': makanan_list,
        'makanan2_list': makanan2_list,
        'user_authenticated': request.user.is_authenticated  # Checking if the user is authenticated
    })


@login_required
def menu(request):
    # Ambil semua data Makanan dan Makanan2
    makanan_list = Makanan.objects.all()
    makanan2_list = Makanan2.objects.all()

    # Tambahkan informasi 'model' ke setiap item
    for item in makanan_list:
        item.model = 'makanan'  # Menambahkan atribut 'model' ke objek

    for item in makanan2_list:
        item.model = 'makanan2'  # Menambahkan atribut 'model' ke objek

    # Kirim data ke template
    return render(request, "menu.html", {
        "makanan_list": makanan_list,
        "makanan2_list": makanan2_list,
    })


@login_required
def checkout(request):
    if request.method == 'POST':
        try:
            # Parse JSON data from the request body
            try:
                data = json.loads(request.body)
            except json.JSONDecodeError as e:
                logger.error(f"JSON decode error: {e}")
                return JsonResponse({
                    'status': 'error',
                    'message': 'Invalid JSON data'
                }, status=400)

            cart_items = data.get('cart_items', [])
            total_price = data.get('total_price', '0')

            # Log parsed data
            logger.debug(f"Received data: {data}")

            # Validate cart items and total price
            if not cart_items:
                return JsonResponse({
                    'status': 'error',
                    'message': 'Keranjang belanja kosong'
                }, status=400)

            try:
                total_price = Decimal(total_price)
            except (ValueError, TypeError):
                return JsonResponse({
                    'status': 'error',
                    'message': 'Total price is invalid'
                }, status=400)

            # Get the user's profile and validate balance
            try:
                profile = request.user.profile
            except ObjectDoesNotExist:
                return JsonResponse({
                    'status': 'error',
                    'message': 'Profile pengguna tidak ditemukan'
                }, status=400)

            if profile.balance < total_price:
                return JsonResponse({
                    'status': 'error',
                    'message': f'Saldo tidak mencukupi. Saldo: {profile.balance}, Total: {total_price}'
                }, status=400)

            # Process the order inside a transaction
            with transaction.atomic():
                # Create the order
                try:
                    order = create_order(request.user, total_price, cart_items)
                except Exception as e:
                    logger.error(f"Order creation error: {e}")
                    raise

                # Update the user's balance
                profile.balance -= total_price
                profile.save()

                # Success response
                return JsonResponse({
                    'status': 'success',
                    'message': 'Order berhasil dibuat',
                    'redirect_url': reverse('order_success')  # Redirect to order success page
                })

        except Exception as e:
            logger.error(f"Unexpected error: {e}")
            return JsonResponse({
                'status': 'error',
                'message': 'Terjadi kesalahan sistem saat checkout'
            }, status=500)

    elif request.method == 'GET':
        # Render the checkout page for GET requests
        return render(request, 'checkout.html')

    # If the method is not allowed
    return JsonResponse({
        'status': 'error',
        'message': 'Method not allowed'
    }, status=405)

def get_makanan_by_id(item):
    """Helper function to get food item based on model type"""
    try:
        model_class = Makanan if item['model'] == 'makanan' else Makanan2
        return model_class.objects.get(id=item['id'])
    except (Makanan.DoesNotExist, Makanan2.DoesNotExist):
        return None


def address_view(request):
    return render(request, 'address.html')

@login_required
@csrf_exempt
def add_to_cart(request):
    if request.method != "POST":
        return JsonResponse({'success': False, 'error': 'Invalid method'})
    
    try:
        data = json.loads(request.body)
        item_id = data.get('id')
        item_name = data.get('name')
        item_price = data.get('price')
        item_image = data.get('image')
        item_model = data.get('model')
        item_quantity = data.get('quantity', 1)
        
        if not all([item_id, item_name, item_price, item_image, item_model]):
            return JsonResponse({'success': False, 'error': 'Incomplete data'})
        
        # Get the appropriate model
        model = Makanan if item_model == 'makanan' else Makanan2
        
        try:
            item = model.objects.get(id=item_id)
            # Hanya cek stok tersedia, tapi tidak menguranginya
            if item.stok < item_quantity:
                return JsonResponse({'success': False, 'error': 'Insufficient stock'})
            
        except model.DoesNotExist:
            return JsonResponse({'success': False, 'error': 'Item not found'})
        
        # Initialize cart structure if it doesn't exist
        if 'cart' not in request.session:
            request.session['cart'] = {}
            
        user_id = str(request.user.id)
        if user_id not in request.session['cart']:
            request.session['cart'][user_id] = []
            
        # Check if item already exists in cart
        user_cart = request.session['cart'][user_id]
        for cart_item in user_cart:
            if cart_item['id'] == item_id and cart_item['model'] == item_model:
                return JsonResponse({'success': False, 'error': 'Item already in cart'})
        
        # Add item to cart
        user_cart.append({
            'id': item_id,
            'name': item_name,
            'price': item_price,
            'image': item_image,
            'model': item_model,
            'quantity': item_quantity
        })
            
        request.session['cart'][user_id] = user_cart
        request.session.modified = True
        
        return JsonResponse({
            'success': True,
            'message': 'Item added to cart successfully',
            'cart_count': len(user_cart)
        })
        
    except json.JSONDecodeError:
        return JsonResponse({'success': False, 'error': 'Invalid JSON data'})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})

def get_user_cart(request):
    """Helper function untuk mengambil keranjang spesifik user"""
    cart = request.session.get('cart', {})
    if not isinstance(cart, dict):
        cart = {}
        request.session['cart'] = cart
    return cart.get(str(request.user.id), [])

def signup(request):
    if request.method == 'POST':
        username = request.POST.get('username')
        email = request.POST.get('email')
        password1 = request.POST.get('password1')
        password2 = request.POST.get('password2')

        # Validasi password
        if password1 != password2:
            messages.error(request, "Passwords do not match!")
            return redirect('signup')

        # Memeriksa ketersediaan username dan email
        if User.objects.filter(username=username).exists():
            messages.error(request, "Username already exists. Please choose another one.")
            return redirect('signup')

        if User.objects.filter(email=email).exists():
            messages.error(request, "Email already exists. Please use another email.")
            return redirect('signup')

        # Membuat user baru
        try:
            user = User.objects.create_user(username=username, email=email, password=password1)
            user.save()
            messages.success(request, "Account created successfully! Please log in.")
            return redirect('login')  # Mengarahkan ke halaman login setelah pendaftaran berhasil
        except Exception as e:
            messages.error(request, f"Error: {str(e)}")
            return redirect('signup')

    return render(request, 'signup.html')

def user_login(request):
    if request.method == "POST":
        username = request.POST.get('username')
        password = request.POST.get('password')
        user = authenticate(request, username=username, password=password)

        if user is not None:
            login(request, user)
            
            # Dapatkan IP address
            ip_address = get_client_ip(request)
            
            try:
                # Simpan login history
                LoginHistory.objects.create(
                    user=user,
                    email=user.email,
                    ip_address=ip_address
                )
                
                # Log additional information using HistoryLog
                HistoryLog.objects.create(
                    user=user,
                    action='login',
                    new_data={
                        'login_time': now().isoformat(),
                        'ip_address': ip_address,
                        'email': user.email,
                        'username': user.username
                    }
                )
                
                messages.success(request, f"Welcome back, {user.username}!")
                return redirect(request.GET.get('next', 'home'))
                
            except Exception as e:
                # Log error tapi tetap lanjutkan proses login
                print(f"Error saving login history: {str(e)}")
                return redirect(request.GET.get('next', 'home'))
        
        messages.error(request, "Username atau password tidak valid")
        return redirect('login')

    return render(request, 'login.html')

def logout_view(request):
    logout(request)
    return redirect('home')  # Alihkan ke homepage setelah logout

def home_page(request):
    makanan_list = Makanan.objects.all()  # Ambil semua data makanan dari database
    makanan2_list = Makanan2.objects.all() 
    context = {
        'makanan_list': makanan_list,
        'makanan2_list': makanan2_list,
    }
    return render(request, 'home.html', context)



@login_required
def profile_view(request, username):
    try:
        # Ambil pengguna berdasarkan username
        user = User.objects.get(username=username)

        try:
            # Ambil profil pengguna yang terkait
            profile = user.profile
            return render(request, 'profile.html', {'user': user, 'profile': profile, 'profile_exists': True})

        except Profile.DoesNotExist:
            # Jika profil tidak ada, buat profil baru
            if request.method == 'POST':
                form = ProfileForm(request.POST)
                if form.is_valid():
                    # Save the form data and link the profile to the user
                    profile = form.save(commit=False)
                    profile.user = user  # Set the user who owns this profile
                    profile.save()

                    # Redirect to the home page after saving the form
                    return redirect('home')  # Ganti 'home' dengan nama URL ke halaman home Anda

                else:
                    # If the form is not valid, re-render the form with errors
                    return render(request, 'profile.html', {'form': form, 'user': user, 'error_message': 'Form is not valid.'})
            
            else:
                # If the request is GET, show the form to create a profile
                form = ProfileForm()
                return render(request, 'profile.html', {'form': form, 'user': user, 'profile_exists': False})

    except User.DoesNotExist:
        return HttpResponse(f"Pengguna dengan username {username} tidak ditemukan.")

@login_required
def address_view(request):
    try:
        # Mengambil alamat pengguna yang sudah ada
        address = Address.objects.get(user=request.user)
    except Address.DoesNotExist:
        address = None

    if request.method == 'POST':
        # Mengambil data dari request.POST
        full_name = request.POST.get('full_name')
        phone = request.POST.get('phone')
        province = request.POST.get('province')
        city = request.POST.get('city')
        postal_code = request.POST.get('postal_code')
        housing_address = request.POST.get('housing_address')

        # Validasi data
        if full_name and phone and province and city and postal_code and housing_address:
            # Jika alamat sudah ada, update; jika tidak, buat baru
            if address:
                address.full_name = full_name
                address.phone = phone
                address.province = province
                address.city = city
                address.postal_code = postal_code
                address.housing_address = housing_address
                address.save()
            else:
                # Menyimpan data ke database jika belum ada
                address = Address(
                    user=request.user,
                    full_name=full_name,
                    phone=phone,
                    province=province,
                    city=city,
                    postal_code=postal_code,
                    housing_address=housing_address
                )
                address.save()

            return redirect('address')  # Redirect ke halaman yang sama setelah simpan
        else:
            error_message = 'Please fill out all fields.'
            return render(request, 'address.html', {'error_message': error_message, 'address': address})

    else:
        # Jika bukan POST, tampilkan form dengan data alamat yang ada (jika ada)
        return render(request, 'address.html', {'address': address})
    
def get_client_ip(request):
    """Helper function untuk mendapatkan IP address client"""
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0].strip()
    else:
        ip = request.META.get('REMOTE_ADDR')
    return ip

def top_up_balance(request):
    if not request.user.is_superuser:
        messages.error(request, "Anda tidak memiliki izin untuk mengakses halaman ini.")
        return redirect('profile')
    
    if request.method == 'POST':
        client_id = request.POST.get('client_id')
        nominal = request.POST.get('nominal')

        try:
            user = User.objects.get(id=client_id)
            formatted_nominal = "IDR {:,.0f}".format(float(nominal)).replace(",", ".")
            user.profile.balance += int(nominal)
            user.profile.save()
            messages.success(request, f"Saldo untuk {user.username} berhasil di-top up sebesar {formatted_nominal}")
        except User.DoesNotExist:
            messages.error(request, "User tidak ditemukan.")
        except ValueError:
            messages.error(request, "Nominal tidak valid.")
        
        return redirect('top_up_balance')

    users = User.objects.all()
    return render(request, 'topup.html', {'users': users})

@login_required(login_url='login')
def request_top_up(request):
    if request.method == 'POST':
        amount = request.POST.get('amount')
        
        try:
            amount = int(amount)
            if amount <= 0:
                messages.error(request, "Jumlah top-up harus lebih dari 0.")
                return render(request, 'request_top_up.html')

            formatted_amount = "IDR {:,.0f}".format(float(amount)).replace(",", ".")
            
            # Membuat permintaan top-up
            top_up_request = TopUpRequest.objects.create(
                user=request.user,
                amount=amount,
                status='Pending'  # Menambahkan status awal
            )
            
            messages.success(request, f"Permintaan top-up {formatted_amount} berhasil diajukan.")
            return redirect('profile')
            
        except ValueError:
            messages.error(request, "Jumlah yang dimasukkan tidak valid.")
            return render(request, 'request_top_up.html')
    
    return render(request, 'request_top_up.html')

@staff_member_required(login_url='login')
def admin_top_up_requests(request):
    if not request.user.is_superuser:
        messages.error(request, "Anda tidak memiliki izin untuk mengakses halaman ini.")
        return redirect('profile')
    
    try:
        requests = TopUpRequest.objects.all().order_by('-requested_at')
        return render(request, 'admin_top_up_requests.html', {'requests': requests})
    except Exception as e:
        messages.error(request, f"Terjadi kesalahan: {str(e)}")
        return redirect('profile')

@staff_member_required(login_url='login')
def approve_top_up(request, request_id):
    if not request.user.is_superuser:
        return HttpResponseForbidden("Anda tidak memiliki izin untuk melakukan ini.")
    
    try:
        top_up_request = get_object_or_404(TopUpRequest, id=request_id)
        
        # Validasi status
        if top_up_request.status != 'Pending':
            messages.error(request, "Permintaan top-up ini sudah diproses sebelumnya.")
            return redirect('admin_top_up_requests')
        
        # Update status top-up
        top_up_request.status = 'Sukses'
        top_up_request.save()
        
        # Update saldo user
        user = top_up_request.user
        top_up_amount = Decimal(top_up_request.amount)
        formatted_amount = "IDR {:,.0f}".format(float(top_up_amount)).replace(",", ".")
        
        user.profile.balance += top_up_amount
        user.profile.save()
        
        # Catat transaksi
        TransactionHistory.objects.create(
            user=user,
            amount=top_up_request.amount,
            status='Approved',
            description=f"Top-up sebesar {formatted_amount}"
        )
        
        # Hapus permintaan top-up
        top_up_request.delete()
        
        messages.success(request, f"Top-up sebesar {formatted_amount} disetujui untuk {user.username}.")
        
    except TopUpRequest.DoesNotExist:
        messages.error(request, "Permintaan top-up tidak ditemukan.")
    except Exception as e:
        messages.error(request, f"Terjadi kesalahan: {str(e)}")
    
    return redirect('admin_top_up_requests')

@staff_member_required(login_url='login')
def reject_top_up(request, request_id):
    if not request.user.is_superuser:
        return HttpResponseForbidden("Anda tidak memiliki izin untuk melakukan ini.")
    
    try:
        top_up_request = get_object_or_404(TopUpRequest, id=request_id)
        
        # Validasi status
        if top_up_request.status != 'Pending':
            messages.error(request, "Permintaan top-up ini sudah diproses sebelumnya.")
            return redirect('admin_top_up_requests')
        
        formatted_amount = "IDR {:,.0f}".format(float(top_up_request.amount)).replace(",", ".")
        
        # Catat transaksi
        TransactionHistory.objects.create(
            user=top_up_request.user,
            amount=top_up_request.amount,
            status='Rejected',
            description=f"Top-up ditolak: {formatted_amount}"
        )
        
        messages.success(request, f"Permintaan top-up {formatted_amount} oleh {top_up_request.user.username} ditolak.")
        
        # Hapus permintaan top-up
        top_up_request.delete()
        
    except TopUpRequest.DoesNotExist:
        messages.error(request, "Permintaan top-up tidak ditemukan.")
    except Exception as e:
        messages.error(request, f"Terjadi kesalahan: {str(e)}")
    
    return redirect('admin_top_up_requests')


@login_required
@csrf_exempt
def update_balance(request):
    if request.method == 'POST':
        try:
            # Ambil data dari body request
            data = json.loads(request.body)
            new_balance = data.get('balance')

            # Pastikan saldo diberikan
            if new_balance is None:
                return JsonResponse({'error': 'Saldo tidak diberikan'}, status=400)
            
            # Validasi nilai balance (pastikan berupa angka)
            if not isinstance(new_balance, (int, float)):
                return JsonResponse({'error': 'Saldo harus berupa angka'}, status=400)

            # Perbarui saldo pengguna
            user_profile = request.user.profile
            user_profile.balance = new_balance
            user_profile.save()

            # Kirimkan response sukses dengan saldo baru
            return JsonResponse({'success': True, 'new_balance': new_balance})

        except Exception as e:
            # Log error atau kirimkan pesan error
            return JsonResponse({'error': str(e)}, status=400)

    return JsonResponse({'error': 'Metode tidak diizinkan'}, status=405)


@login_required
def update_order_status(request, order_id):
    order = get_object_or_404(Order, id=order_id)
    
    if request.method == 'POST':
        new_status = request.POST.get('status')
        
        try:
            with transaction.atomic():
                if new_status == 'rejected':
                    # Jika status berubah menjadi 'rejected'
                    if order.status != 'rejected':
                        # 1. Kembalikan stok untuk setiap item
                        for order_item in order.items.all():
                            if order_item.makanan:
                                product = order_item.makanan
                                product.stok += order_item.quantity
                                product.save()
                            elif order_item.makanan2:
                                product = order_item.makanan2
                                product.stok += order_item.quantity
                                product.save()
                        
                        # 2. Kembalikan saldo ke user
                        user_profile = order.user.profile
                        user_profile.balance += order.total_price
                        user_profile.save()
                        
                        messages.success(request, f'Order #{order.id} ditolak, stok dikembalikan, dan saldo dikembalikan.')
                
                # Update status order
                order.status = new_status
                order.save()
                messages.success(request, f'Status order #{order.id} berhasil diperbarui menjadi {new_status}.')
                
                # Tambahkan ke history transaksi
                TransactionHistory.objects.create(
                    user=order.user,
                    amount=order.total_price,
                    status=new_status,
                    description=f"Order #{order.id} {new_status}"
                )
                
        except Exception as e:
            messages.error(request, f'Error updating order status: {str(e)}')
            
        return redirect('admin_order_detail', order_id=order_id)

    return redirect('admin_order_detail', order_id=order_id)


@staff_member_required
def approve_order(request, order_id):
    if request.method == 'POST':
        try:
            with transaction.atomic():
                # Get the order
                order = get_object_or_404(Order, id=order_id)
                
                # Only process if order is in pending state
                if order.status != 'pending':
                    messages.error(request, f'Order #{order.id} cannot be approved - invalid status')
                    return redirect('admin_order_detail', order_id=order_id)

                # Check stock availability before approving the order
                for item in order.items.all():
                    # Accessing either 'makanan' or 'makanan2' instead of 'product'
                    if item.makanan:
                        product = item.makanan
                    elif item.makanan2:
                        product = item.makanan2
                    else:
                        # If no valid product found, return an error
                        messages.error(request, f"Invalid product for order item #{item.id}.")
                        return redirect('admin_order_detail', order_id=order_id)

                    if product.stok < item.quantity:
                        # If stock is insufficient, return an error message
                        messages.error(request, f"Insufficient stock for {product.nama_menu}. Only {product.stok} left.")
                        return redirect('admin_order_detail', order_id=order_id)

                    # Deduct the stock for each item in the order
                    product.stok -= item.quantity
                    product.save()

                # Update the order status to approved
                order.status = 'approved'
                order.save()

                # Create transaction history entry for the approval
                TransactionHistory.objects.create(
                    user=order.user,
                    amount=order.total_price,
                    status='Approved',
                    description=f"Order #{order.id} approved"
                )

                # Record the items in OrderItem table (if not already done)
                cart = request.session.get('cart', {}).get(str(order.user.id), [])
                for item in cart:
                    food_model = Makanan if item['model'] == 'makanan' else Makanan2
                    
                    try:
                        food = food_model.objects.get(id=item['id'])
                        OrderItem.objects.create(
                            order=order,
                            makanan=food if item['model'] == 'makanan' else None,
                            makanan2=food if item['model'] == 'makanan2' else None,
                            quantity=item['quantity'],
                            harga_total=food.harga * item['quantity']
                        )
                    except food_model.DoesNotExist:
                        messages.warning(request, f"Item {item['name']} not found in database")
                        continue
                
                # Clear the user's cart after successful order
                if str(order.user.id) in request.session.get('cart', {}):
                    cart = request.session['cart']
                    cart[str(order.user.id)] = []
                    request.session['cart'] = cart

                messages.success(request, f'Order #{order.id} has been approved and items have been recorded')

        except Exception as e:
            messages.error(request, f'Error processing order: {str(e)}')
            return redirect('admin_order_detail', order_id=order_id)

        return redirect('admin_order_detail', order_id=order_id)

    return redirect('admin_order_detail', order_id=order_id)

@login_required
def reject_order(request, order_id):
    order = get_object_or_404(Order, id=order_id)

    # Pastikan status order bukan 'rejected' sebelum memproses
    if order.status != 'rejected':
        refund_amount = order.total_price
        user = order.user

        try:
            # Atomic transaction untuk memastikan kedua aksi berjalan bersamaan
            with transaction.atomic():
                # Update status order menjadi 'rejected'
                order.status = 'rejected'
                order.save()

                # Kembalikan stok untuk setiap item di order
                for item in order.items.all():
                    if item.makanan:
                        product = item.makanan
                    elif item.makanan2:
                        product = item.makanan2
                    else:
                        # Jika tidak ada produk yang ditemukan, kirim pesan error
                        messages.error(request, f"Item #{item.id} tidak memiliki produk yang valid.")
                        return redirect('admin_order_detail', order_id=order_id)

                    # Kembalikan stok produk
                    product.stok += item.quantity
                    product.save()

                # Kembalikan saldo ke user
                user.profile.balance += refund_amount
                user.profile.save()

                # Kirim response JSON yang menyertakan status order dan saldo pengguna terbaru
                return JsonResponse({
                    'status': 'rejected',
                    'user_balance': str(user.profile.balance),  # Pastikan format ini sesuai dengan yang diinginkan
                })

        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)

    # Jika status order sudah 'rejected', kembalikan error
    return JsonResponse({'error': 'Order sudah ditolak sebelumnya'}, status=400)
    
def process_order(order):
    """Memproses pesanan yang disetujui atau ditolak dengan memperbarui stok dan transaksi."""
    try:
        with transaction.atomic():
            if order.status == 'approved':
                for item in order.items.all():
                    makanan = item.makanan
                    makanan.stok -= item.quantity
                    makanan.save()

                # Membuat catatan transaksi
                TransactionHistory.objects.create(
                    user=order.user,
                    amount=order.total_price,
                    status='Approved',
                    description=f"Order #{order.id} disetujui"
                )

            elif order.status == 'rejected':
                # Mengembalikan saldo yang telah dipotong
                order.user.profile.balance += order.total_price
                order.user.profile.save()

                # Membuat catatan transaksi
                TransactionHistory.objects.create(
                    user=order.user,
                    amount=order.total_price,
                    status='Rejected',
                    description=f"Order #{order.id} ditolak dan saldo dikembalikan"
                )

            order.save()
            return order
    except Exception as e:
        # Tangani error dan buat pesan log jika diperlukan
        logging.error(f"Error processing order #{order.id}: {str(e)}")
        raise


@staff_member_required
def set_pending(request, order_id):
    if request.method == 'POST':
        order = get_object_or_404(Order, id=order_id)
        order.status = 'pending'
        order.save()
        messages.success(request, f'Order #{order.id} has been set to pending')
        return redirect('admin_order_detail', order_id=order_id)  # Remove 'admin:'
    
@login_required
def add_order_item(request, order_id):
    """Tambah item ke dalam order."""
    if request.method == 'POST':
        try:
            with transaction.atomic():
                # Ambil order yang sesuai
                order = get_object_or_404(Order, id=order_id, user=request.user)

                # Ambil data dari form
                makanan_id = request.POST.get('makanan_id')
                quantity = int(request.POST.get('quantity', 1))

                # Ambil objek makanan berdasarkan ID
                makanan = get_object_or_404(Makanan, id=makanan_id)

                # Validasi stok
                if makanan.stok < quantity:
                    messages.error(request, f"Stok tidak mencukupi untuk {makanan.nama_menu}.")
                    return redirect('order_detail', order_id=order_id)

                # Tambahkan item ke order
                order_item = OrderItem.objects.create(
                    order=order,
                    makanan=makanan,
                    quantity=quantity,
                )

                # Perbarui harga total order
                order.total_price += order_item.harga_total
                order.save()

                messages.success(request, f"{quantity}x {makanan.nama_menu} berhasil ditambahkan ke pesanan.")
                return redirect('order_detail', order_id=order_id)

        except ValueError as e:
            messages.error(request, str(e))
        except Exception as e:
            messages.error(request, "Terjadi kesalahan saat menambahkan item.")
    else:
        messages.error(request, "Hanya metode POST yang diizinkan.")
    
    return redirect('order_detail', order_id=order_id)

@login_required
def remove_order_item(request, order_id, item_id):
    """Remove an item from an order."""
    try:
        with transaction.atomic():
            order = get_object_or_404(Order, id=order_id, user=request.user)
            order_item = get_object_or_404(OrderItem, id=item_id, order=order)

            # Return stock
            makanan = order_item.makanan
            makanan.stok += order_item.quantity
            makanan.save()

            # Update order total
            order.total_price -= order_item.harga_total
            order.save()

            # Delete the item
            order_item.delete()

            messages.success(request, "Item berhasil dihapus dari pesanan")
    except Exception as e:
        messages.error(request, "Gagal menghapus item dari pesanan")

    return redirect('order_detail', order_id=order_id)

@login_required
def update_order_item_quantity(request, order_id, item_id):
    """Update the quantity of an order item."""
    if request.method == 'POST':
        try:
            with transaction.atomic():
                order = get_object_or_404(Order, id=order_id, user=request.user)
                order_item = get_object_or_404(OrderItem, id=item_id, order=order)
                new_quantity = int(request.POST.get('quantity', 1))

                if new_quantity <= 0:
                    return JsonResponse({'error': 'Quantity must be positive'}, status=400)

                makanan = order_item.makanan
                quantity_difference = new_quantity - order_item.quantity

                # Check if enough stock for increase
                if quantity_difference > 0 and makanan.stok < quantity_difference:
                    return JsonResponse({'error': 'Insufficient stock'}, status=400)

                # Update stock
                makanan.stok -= quantity_difference
                makanan.save()

                # Update order item
                old_total = order_item.harga_total
                order_item.quantity = new_quantity
                order_item.harga_total = makanan.harga * new_quantity
                order_item.save()

                # Update order total
                order.total_price = order.total_price - old_total + order_item.harga_total
                order.save()

                return JsonResponse({
                    'success': True,
                    'new_quantity': new_quantity,
                    'new_total': float(order_item.harga_total),
                    'order_total': float(order.total_price)
                })

        except ValueError:
            return JsonResponse({'error': 'Invalid quantity'}, status=400)
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)

    return JsonResponse({'error': 'Invalid request method'}, status=405)

@login_required
def list_order_items(request, order_id):
    """View to list all items in an order."""
    order = get_object_or_404(Order, id=order_id, user=request.user)
    items = order.items.all().select_related('makanan', 'makanan2')  # Eager loading untuk kedua model
    
    if not items.exists():
        print(f"Order {order.id} does not have any items.")
    
    context = {
        'order': order,
        'items': items,
        'total_items': items.count(),
        'total_price': order.total_price,
    }
    
    return render(request, 'order_items_list.html', context)

@login_required
def order_item_detail(request, order_id, item_id):
    """View detailed information about a specific order item."""
    order = get_object_or_404(Order, id=order_id, user=request.user)
    item = get_object_or_404(OrderItem, id=item_id, order=order)
    
    context = {
        'order': order,
        'item': item,
    }
    
    return render(request, 'order_item_detail.html', context)

def create_order(user, total_price, cart_items):
    with transaction.atomic():
        try:
            print(f"Creating order for user: {user}, total price: {total_price}")
            print(f"Cart items: {cart_items}")  # Debug logging
            
            new_order = Order.objects.create(
                user=user,
                status='pending',
                total_price=total_price
            )

            if user.profile.balance < total_price:
                raise ValueError("Insufficient balance.")

            user.profile.balance -= total_price
            user.profile.save()

            for item in cart_items:
                print(f"Processing item: {item}")  # Debug logging
                
                if item['model'] == 'makanan':
                    food_item = Makanan.objects.get(id=item['id'])
                    food_item.stok -= item['quantity']
                    food_item.save()
                    
                    order_item = OrderItem.objects.create(
                        order=new_order,
                        makanan=food_item,
                        quantity=item['quantity'],
                        harga_total=Decimal(str(item['price'])) * Decimal(str(item['quantity']))
                    )
                    print(f"Created order item: {order_item.id}")  # Debug logging
                    
                elif item['model'] == 'makanan2':
                    food_item = Makanan2.objects.get(id=item['id'])
                    food_item.stok -= item['quantity']
                    food_item.save()
                    
                    order_item = OrderItem.objects.create(
                        order=new_order,
                        makanan2=food_item,
                        quantity=item['quantity'],
                        harga_total=Decimal(str(item['price'])) * Decimal(str(item['quantity']))
                    )
                    print(f"Created order item: {order_item.id}")  # Debug logging

            return new_order
            
        except Exception as e:
            print(f"Error creating order: {str(e)}")  # Debug logging
            raise
        

def check_and_reduce_stock(item_id, model, quantity):
    """Check stock availability and reduce stock if sufficient"""
    with transaction.atomic():
        # Select appropriate model
        if model == 'makanan':
            item_obj = Makanan
        elif model == 'makanan2':
            item_obj = Makanan2
        else:
            raise ValueError(f"Invalid model: {model}")

        # Get item with lock for update
        item = item_obj.objects.select_for_update().get(id=item_id)

        # Check if enough stock
        if item.stok < quantity:
            raise ValueError(f"Insufficient stock for {item.nama_menu}. Available: {item.stok}, Requested: {quantity}")

        # Reduce stock
        item.stok -= quantity
        item.save()

        return item

def add_item_to_order(order, item, quantity):
    """Menambahkan item ke dalam order."""
    # Hitung harga total untuk item ini
    harga_total = item.harga * quantity

    # Tambahkan OrderItem
    OrderItem.objects.create(
        order=order,
        makanan=item,
        quantity=quantity,
        harga_total=harga_total
    )

    # Perbarui harga total order
    order.total_price += harga_total
    order.save()


def get_order_status(request, order_id):
    order = get_object_or_404(Order, id=order_id)

    return JsonResponse({
        'status': order.status,
        'user_balance': str(order.user.profile.balance)  # Pastikan saldo pengguna dikembalikan
    })

# Fungsi untuk memproses item ketika order disetujui
def approve_order_and_create_items(order, cart_items):
    if order.status != 'approved':
        order.status = 'approved'
        order.save()

    for item in cart_items:
        makanan = get_makanan_by_id(item['makanan_id'])  # Ambil makanan dari database
        if makanan:
            # Pastikan item ditambahkan jika tidak ada sebelumnya
            if not OrderItem.objects.filter(order=order, makanan=makanan).exists():
                OrderItem.objects.create(
                    order=order,
                    makanan=makanan,
                    quantity=item['quantity'],
                    harga_total=Decimal(item['price']) * item['quantity']
                )
                print(f"OrderItem created for order {order.id} - Makanan: {makanan.nama_menu}")

def save_order_and_items(order, cart_items):
    try:
        for item in cart_items:
            makanan = get_makanan_by_id(item)
            if makanan:
                OrderItem.objects.create(
                    order=order,
                    makanan=makanan,
                    quantity=item['quantity'],
                    harga_total=Decimal(item['price']) * item['quantity']
                )
        order.save()
    except IntegrityError as e:
        print(f"Error saving order items: {e}")

def update_stok_setelah_pesanan(item_pesanan):
    """
    Memperbarui level stok setelah konfirmasi pesanan
    Mengembalikan True jika berhasil, False jika stok tidak mencukupi
    """
    with transaction.atomic():
        for item in item_pesanan:
            makanan = item.get('makanan') or item.get('makanan2')
            if not makanan:
                continue

            if not makanan.kurangi_stok(item['quantity']):
                # Rollback akan terjadi secara otomatis
                return False
    return True

def cek_ketersediaan_stok(item_keranjang):
    """
    Memeriksa apakah semua item di keranjang memiliki stok yang cukup
    Mengembalikan tuple (bool, daftar item yang tidak tersedia)
    """
    item_tidak_tersedia = []
    
    for item in item_keranjang:
        model = Makanan if item['model'] == 'makanan' else Makanan2
        try:
            produk = model.objects.get(id=item['id'])
            if produk.stok < item['quantity']:
                item_tidak_tersedia.append({
                    'nama': produk.nama_menu if hasattr(produk, 'nama_menu') else produk.nama_category,
                    'tersedia': produk.stok,
                    'diminta': item['quantity']
                })
        except model.DoesNotExist:
            item_tidak_tersedia.append({
                'nama': item['name'],
                'error': 'Produk tidak ditemukan'
            })
    
    return (len(item_tidak_tersedia) == 0, item_tidak_tersedia)

def tambah_stok_item(data_item):
    """
    Menambah stok item dengan jumlah baru
    data_item: list dari dict dengan kunci 'id', 'model', dan 'quantity'
    """
    with transaction.atomic():
        for item in data_item:
            model = Makanan if item['model'] == 'makanan' else Makanan2
            try:
                produk = model.objects.get(id=item['id'])
                if item['quantity'] > 0:
                    produk.tambah_stok(item['quantity'])
            except model.DoesNotExist:
                continue

def kurangi_stok(request):
    if request.method == 'POST':
        data = json.loads(request.body)
        item_id = data.get('id')
        model_name = data.get('model')
        jumlah = data.get('jumlah')
        is_increment = data.get('is_increment')

        # Get the object based on the model
        if model_name == 'makanan2':
            item = Makanan2.objects.get(id=item_id)
        else:
            item = Makanan.objects.get(id=item_id)

        if not is_increment and item.stok >= jumlah:  # Decrease stock
            item.stok -= jumlah
            item.save()
            return JsonResponse({"success": True})

        if is_increment:  # Increase stock
            item.stok += jumlah
            item.save()
            return JsonResponse({"success": True})

        return JsonResponse({"success": False, "error": "Not enough stock"})
    return JsonResponse({"success": False, "error": "Invalid request"})

@receiver(user_logged_in)
def save_login_history(sender, request, user, **kwargs):
    # Create a new LoginHistory object when the user logs in
    ip_address = request.META.get('REMOTE_ADDR')  # Get the IP address from the request
    LoginHistory.objects.create(user=user, email=user.email, login_time=now(), ip_address=ip_address)


@login_required
def remove_from_cart(request, item_id):
    """Remove item from cart for authenticated user"""
    if 'cart' in request.session and str(request.user.id) in request.session['cart']:
        cart = request.session['cart'][str(request.user.id)]
        cart = [item for item in cart if item['id'] != item_id]
        request.session['cart'][str(request.user.id)] = cart
        request.session.modified = True
        messages.success(request, "Item removed from cart")
    return redirect('cart')

@login_required
def update_cart(request):
    """Update cart quantities for authenticated user"""
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            item_id = data.get('id')
            quantity = int(data.get('quantity', 1))
            
            if quantity < 1:
                return JsonResponse({'error': 'Invalid quantity'}, status=400)

            cart = request.session.get('cart', {}).get(str(request.user.id), [])
            for item in cart:
                if item['id'] == item_id:
                    model = Makanan if item['model'] == 'makanan' else Makanan2
                    product = model.objects.get(id=item_id)
                    
                    if product.stok < quantity:
                        return JsonResponse({
                            'error': 'Insufficient stock',
                            'available': product.stok
                        }, status=400)
                        
                    item['quantity'] = quantity
                    break
                    
            request.session['cart'][str(request.user.id)] = cart
            request.session.modified = True
            
            return JsonResponse({'success': True})
            
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=400)
            
    return JsonResponse({'error': 'Invalid method'}, status=405)