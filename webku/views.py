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

logger = logging.getLogger(__name__)

def checkout(request):
    return redirect('order_success')

def get_cart(request):
    cart = request.session.get('cart', [])
    return JsonResponse({'cart': cart})

@login_required
def order_status(request, order_id):
    try:
        order = Order.objects.get(id=order_id, user=request.user)
        return JsonResponse({'status': order.status})
    except Order.DoesNotExist:
        return JsonResponse({'error': 'Order not found'}, status=404)
    
@staff_member_required
def order_admin_detail(request, order_id):
    order = get_object_or_404(Order, id=order_id)
    context = {
        'order': order,
        'title': f'Order #{order.id} Details',  # For admin template
        'is_popup': False,  # For admin template
        'has_permission': True,  # For admin template
        'site_header': 'Administration',  # For admin template
        'site_title': 'Site Admin',  # For admin template
        'app_label': 'webku',
    }
    return render(request, 'admin/order_admin_detail.html', context)

@login_required
def order_success(request):
    order = Order.objects.filter(user=request.user).latest('created_at')
    order_items = order.items.all()
    user_balance = request.user.profile.balance
    total_price_scaled = order.total_price / Decimal(100)

    return render(request, 'order_success.html', {
        'order': order,
        'order_items': order_items,
        'total_price_scaled': total_price_scaled,
        'user_balance': user_balance,
        'order_status': order.status,
    })

def profile(request):
    return render(request, 'see_profil.html')

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
    if not hasattr(request.user, 'profile'):
        messages.error(request, "Silakan lengkapi profil Anda terlebih dahulu.")
        return redirect('profile')

    address = get_object_or_404(Address, user=request.user)

    if request.method == 'POST':
        cart = request.session.get('cart', {}).get(str(request.user.id), [])
        total_price_str = request.POST.get('total_price', '').replace("IDR", "").replace(",", "").replace(".", "").strip()

        try:
            total_price = Decimal(total_price_str)
        except InvalidOperation:
            messages.error(request, "Format total harga tidak valid.")
            return redirect('checkout')

        if request.user.profile.balance < total_price:
            messages.error(request, "Saldo Anda tidak mencukupi untuk melakukan pembayaran.")
            return redirect('profile')

        try:
            with transaction.atomic():
                # Proses pembayaran
                request.user.profile.balance -= total_price
                request.user.profile.save()
                TransactionHistory.objects.create(
                    user=request.user,
                    amount=total_price,
                    status='Approved',
                    description="Pembayaran untuk belanja"
                )

                # Buat Order
                new_order = Order.objects.create(
                    user=request.user,
                    status='Confirmed',
                    total_price=total_price,
                )

                insufficient_stock = []
                for item in cart:
                    if 'model' not in item:
                        insufficient_stock.append("Format data item di keranjang tidak valid (model tidak ada).")
                        continue

                    if item['model'] == 'makanan':
                        item_obj = Makanan
                    elif item['model'] == 'makanan2':
                        item_obj = Makanan2
                    else:
                        insufficient_stock.append(f"Model {item['model']} tidak valid.")
                        continue

                    try:
                        food = item_obj.objects.select_for_update().get(id=item['id'])

                        if food.stok < item['quantity']:
                            insufficient_stock.append(f"Stok untuk {food.nama_menu} tidak mencukupi. Tersedia: {food.stok}, Dibeli: {item['quantity']}")
                            continue

                        # Kurangi stok
                        food.stok -= item['quantity']
                        food.save()

                        OrderItem.objects.create(
                            order=new_order,
                            makanan=food,
                            quantity=item['quantity'],
                            harga_total=food.harga * item['quantity']
                        )

                    except item_obj.DoesNotExist:
                        insufficient_stock.append(f"Item dengan ID {item['id']} tidak ditemukan.")
                        continue

                if insufficient_stock:
                    messages.error(request, "Beberapa item dalam keranjang tidak dapat diproses: " + ", ".join(insufficient_stock))
                    return redirect('checkout')

                request.session['cart'] = {}
                messages.success(request, "Pesanan Anda berhasil diproses!")
                return redirect('order_success')

        except Exception as e:
            messages.error(request, "Terjadi kesalahan saat memproses pesanan. Silakan coba lagi.")
            return redirect('checkout')

    return render(request, 'checkout.html', {'address': address})

def get_makanan_by_id(item):
    """Fungsi pembantu untuk mendapatkan objek Makanan atau Makanan2."""
    if item["model"] == "makanan":
        return Makanan.objects.get(id=item["id"])
    elif item["model"] == "makanan2":
        return Makanan2.objects.get(id=item["id"])
    else:
        return None  # Model tidak valid


def address_view(request):
    return render(request, 'address.html')

@login_required
def add_to_cart(request):
    if request.method == "POST":
        data = json.loads(request.body)
        item_id = data.get('id')
        item_name = data.get('name')
        item_price = data.get('price')
        item_image = data.get('image')
        item_model = data.get('model')
        item_quantity = data.get('quantity')

        if not all([item_id, item_name, item_price, item_image, item_model, item_quantity]):
            return JsonResponse({'success': False, 'error': 'Data tidak lengkap'})

        try:
            item_quantity = int(item_quantity)
            if item_quantity <= 0:
                return JsonResponse({'success': False, 'error': 'Jumlah item harus lebih dari 0'})
        except ValueError:
            return JsonResponse({'success': False, 'error': 'Jumlah item harus berupa angka'})

        try:
            with transaction.atomic():
                if item_model == 'makanan':
                    item_obj = Makanan
                elif item_model == 'makanan2':
                    item_obj = Makanan2
                else:
                    return JsonResponse({'success': False, 'error': 'Model tidak valid'})

                food = item_obj.objects.select_for_update().get(id=item_id)

                # Check stock
                if food.stok <= 0:
                    return JsonResponse({'success': False, 'error': 'Item sudah terjual habis.'})

                # Check if item is already purchased by another user
                if food.stok == 1 and TransactionHistory.objects.filter(makanan=food, status='Approved').exclude(user=request.user).exists():
                    return JsonResponse({'success': False, 'error': 'Item ini sudah dibeli oleh pengguna lain.'})

        except item_obj.DoesNotExist:
            return JsonResponse({'success': False, 'error': 'Item tidak ditemukan.'})

        # Add item to cart
        cart = request.session.get('cart', {})
        user_cart = cart.get(str(request.user.id), [])

        # Ensure cart is isolated per user
        cart = request.session.get('cart', {})
        if not isinstance(cart, dict):
            cart = {}

        user_cart = cart.get(str(request.user.id), [])

        # Check if the item is already in the cart
        existing_item = next((item for item in user_cart if item['id'] == item_id), None)
        if existing_item:
            return JsonResponse({'success': False, 'error': 'Item ini sudah ada di keranjang Anda.'})

        user_cart.append({
            'id': item_id,
            'name': item_name,
            'price': item_price,
            'image': item_image,
            'model': item_model,
            'quantity': item_quantity,
        })

        cart[str(request.user.id)] = user_cart
        request.session['cart'] = cart  # Save back to session

        return JsonResponse({'success': True})

    return JsonResponse({'success': False, 'error': 'Invalid method'})


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
            ip_address = get_client_ip(request)  # Pastikan fungsi ini ada dan mengembalikan IP pengguna

            # Log login action
            HistoryLog.objects.create(
                user=user,
                action='login',  # Perbaiki 'create' menjadi 'login'
                new_data={
                    'login_time': now().isoformat(),
                    'ip_address': ip_address,
                    'email': user.email
                }
            )
            return redirect(request.GET.get('next', 'home'))  # Redirect ke halaman yang dituju setelah login

        messages.error(request, "Username atau password tidak valid")
        return redirect('login')

    return render(request, 'login.html')  # Pastikan 'login.html' ada

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

        # Periksa apakah profil sudah ada untuk pengguna tersebut
        if not hasattr(user, 'profile'):
            # Jika profil belum ada, buat form untuk input data
            if request.method == 'POST':
                form = ProfileForm(request.POST)
                if form.is_valid():
                    # Membuat profil baru berdasarkan data form
                    profile = form.save(commit=False)
                    profile.user = user  # Menetapkan pengguna yang terkait
                    profile.save()
                    return render(request, 'profile.html')
            else:
                form = ProfileForm()

            return render(request, 'profile.html', {'form': form, 'user': user})
        else:
            # Mengembalikan JsonResponse agar frontend tahu jika profil sudah ada
            return JsonResponse({'profile_exists': True})  # Profil sudah ada
    
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
    # Ambil IP asli dari header X-Forwarded-For atau fallback ke REMOTE_ADDR
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0]
    else:
        ip = request.META.get('REMOTE_ADDR')
    
    print(f"IP Address: {ip}")  # Debug log
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

def request_top_up(request):
    if request.method == 'POST':
        amount = request.POST.get('amount')
        
        try:
            amount = int(amount)
            formatted_amount = "IDR {:,.0f}".format(float(amount)).replace(",", ".")
            top_up_request = TopUpRequest.objects.create(user=request.user, amount=amount)
            messages.success(request, f"Permintaan top-up {formatted_amount} berhasil diajukan.")
            return redirect('profile')
        except ValueError:
            messages.error(request, "Jumlah yang dimasukkan tidak valid.")
        
    return render(request, 'request_top_up.html')

def admin_top_up_requests(request):
    if not request.user.is_superuser:
        messages.error(request, "Anda tidak memiliki izin untuk mengakses halaman ini.")
        return redirect('profile')
    
    requests = TopUpRequest.objects.all().order_by('-requested_at')  # Menggunakan requested_at
    return render(request, 'admin_top_up_requests.html', {'requests': requests})

def approve_top_up(request, request_id):
    top_up_request = get_object_or_404(TopUpRequest, id=request_id)

    top_up_request.status = 'Sukses'
    top_up_request.save()

    user = top_up_request.user
    top_up_amount = Decimal(top_up_request.amount)
    formatted_amount = "IDR {:,.0f}".format(float(top_up_amount)).replace(",", ".")
    user.profile.balance += top_up_amount
    user.profile.save()

    TransactionHistory.objects.create(
        user=user,
        amount=top_up_request.amount,
        status='Approved'
    )

    top_up_request.delete()

    messages.success(request, f"Top-up sebesar {formatted_amount} disetujui untuk {user.username}.")
    return redirect('admin_top_up_requests')

def reject_top_up(request, request_id):
    top_up_request = get_object_or_404(TopUpRequest, id=request_id)
    formatted_amount = "IDR {:,.0f}".format(float(top_up_request.amount)).replace(",", ".")

    TransactionHistory.objects.create(
        user=top_up_request.user,
        amount=top_up_request.amount,
        status='Rejected'
    )

    messages.success(request, f"Permintaan top-up {formatted_amount} oleh {top_up_request.user.username} ditolak.")
    top_up_request.delete()
    return redirect('admin_top_up_requests')


@login_required
def update_balance(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            new_balance = data.get('balance')

            # Pastikan saldo valid dan pengguna terautentikasi
            if new_balance is not None and new_balance >= 0:
                request.user.profile.balance = new_balance
                request.user.profile.save()

                return JsonResponse({'success': True})
            else:
                return JsonResponse({'success': False, 'error': 'Nilai saldo tidak valid'})
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)})
    return JsonResponse({'success': False, 'error': 'Metode request tidak valid'})


@staff_member_required
def update_order_status(request, order_id):
    if request.method == 'POST':
        order = get_object_or_404(Order, id=order_id)
        new_status = request.POST.get('status')
        if new_status in ['pending', 'approved', 'rejected']:
            order.status = new_status
            order.save()
            messages.success(request, f'Order #{order.id} status updated to {new_status}')
        return redirect('admin:admin_order_detail', order_id=order_id)

@staff_member_required
def update_order_status(request, order_id):
    if request.method == 'POST':
        order = get_object_or_404(Order, id=order_id)
        new_status = request.POST.get('status')
        if new_status in ['pending', 'approved', 'rejected']:
            order.status = new_status
            order.save()
            messages.success(request, f'Order #{order.id} status updated to {new_status}')
        return redirect('admin_order_detail', order_id=order_id)  # Remove 'admin:'

@staff_member_required
def approve_order(request, order_id):
    if request.method == 'POST':
        order = get_object_or_404(Order, id=order_id)
        order.status = 'approved'
        order.save()
        messages.success(request, f'Order #{order.id} has been approved')
        return redirect('admin_order_detail', order_id=order_id)  # Remove 'admin:'

@staff_member_required
def reject_order(request, order_id):
    if request.method == 'POST':
        order = get_object_or_404(Order, id=order_id)
        order.status = 'rejected'
        order.save()
        messages.success(request, f'Order #{order.id} has been rejected')
        return redirect('admin_order_detail', order_id=order_id)  # Remove 'admin:'

@staff_member_required
def set_pending(request, order_id):
    if request.method == 'POST':
        order = get_object_or_404(Order, id=order_id)
        order.status = 'pending'
        order.save()
        messages.success(request, f'Order #{order.id} has been set to pending')
        return redirect('admin_order_detail', order_id=order_id)  # Remove 'admin:'