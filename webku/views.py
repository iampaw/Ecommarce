from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, authenticate, logout
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm
from django.contrib import messages
from .models import Makanan, Makanan2, LoginHistory, Profile, Address, Client, TopUpRequest, TransactionHistory, OrderItem, Order, transaction
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


logger = logging.getLogger(__name__)

def checkout(request):
    return redirect('order_success')

def get_cart(request):
    cart = request.session.get('cart', [])
    return JsonResponse({'cart': cart})

@login_required
def order_success(request):
    # Ambil order terakhir berdasarkan user yang sedang login
    order = Order.objects.filter(user=request.user).latest('created_at')

    # Ambil item dari order yang baru saja dibuat
    order_items = order.items.all()

    # Ambil saldo pengguna setelah transaksi
    user_balance = request.user.profile.balance

    # Mengirim data ke template
    return render(request, 'order_success.html', {
        'order': order,
        'order_items': order_items,
        'user_balance': user_balance
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
    return render(request, 'home.html', {
        'user_authenticated': request.user.is_authenticated
    })  # Pastikan Anda memiliki template 'home.html'

@login_required
def menu(request):
    makanan_list = Makanan.objects.all().values('id', 'nama_menu', 'harga', 'gambar', 'stok', 'model')
    for item in makanan_list:
        item['model'] = 'makanan'

    makanan2_list = Makanan2.objects.all().values('id', 'nama_category', 'harga', 'gambar', 'stok', 'category')
    for item in makanan2_list:
        item['model'] = 'makanan2'

    # Gabungkan kedua queryset
    combined_makanan_list = list(makanan_list)  # Menyimpan daftar makanan
    combined_makanan2_list = list(makanan2_list)  # Menyimpan daftar makanan2

    return render(request, "menu.html", {
        "makanan_list": combined_makanan_list,
        "makanan2_list": combined_makanan2_list,
    })



@login_required
def checkout(request):
    # Validasi keberadaan profile
    if not hasattr(request.user, 'profile'):
        messages.error(request, "Silakan lengkapi profil Anda terlebih dahulu.")
        return redirect('profile')

    # Validasi keberadaan address
    try:
        address = Address.objects.get(user=request.user)
    except Address.DoesNotExist:
        messages.error(request, "Alamat Anda belum lengkap. Silakan lengkapi alamat terlebih dahulu.")
        return redirect('address')

    if request.method == 'POST':
        # Ambil data keranjang dari sesi
        cart = request.session.get('cart', [])
        total_price_str = request.POST.get('total_price')  # Total harga dari form
        
        # Validasi format total harga
        total_price_str = total_price_str.replace("Rp.", "").replace(",", "").strip()
        try:
            total_price = Decimal(total_price_str)
        except InvalidOperation:
            messages.error(request, "Format total harga tidak valid.")
            return redirect('checkout')

        # Cek saldo pengguna
        if request.user.profile.balance >= total_price:
            try:
                # Mulai transaksi untuk memastikan integritas data
                with transaction.atomic():
                    # Proses pembayaran dan pembaruan saldo
                    request.user.profile.balance -= total_price
                    request.user.profile.save()

                    # Simpan riwayat transaksi
                    TransactionHistory.objects.create(
                        user=request.user,
                        amount=total_price,
                        status='Approved',
                        description="Pembayaran untuk belanja"
                    )

                    # Buat Order
                    new_order = Order.objects.create(
                        user=request.user,
                        status='Confirmed',  # Status diubah menjadi 'Confirmed' setelah pembayaran berhasil
                        total_price=total_price,  # Menyimpan total harga order
                    )

                    insufficient_stock = []  # Menampung item dengan stok tidak cukup
                    # Menambahkan item ke dalam OrderItem
                    for item in cart:
                        item_obj = Makanan if item['model'] == 'makanan' else Makanan2
                        try:
                            # Ambil item makanan berdasarkan model
                            food = item_obj.objects.get(id=item['id'])
                            
                            # Cek stok makanan
                            if food.stok < item['quantity']:
                                insufficient_stock.append(f"Stok untuk {food.nama_menu} tidak mencukupi.")
                                continue

                            # Mengurangi stok makanan dan menyimpan perubahan
                            food.stok -= item['quantity']
                            food.save()

                            # Menambahkan item pesanan ke OrderItem
                            OrderItem.objects.create(
                                order=new_order,
                                makanan=food,
                                quantity=item['quantity'],
                                harga_total=food.harga * item['quantity']
                            )

                        except item_obj.DoesNotExist:
                            insufficient_stock.append(f"Item dengan ID {item['id']} tidak ditemukan.")
                            continue

                    # Jika ada item dengan stok tidak cukup, tampilkan pesan error
                    if insufficient_stock:
                        messages.error(request, "Beberapa item dalam keranjang tidak dapat diproses: " + ", ".join(insufficient_stock))
                        return redirect('checkout')

                    # Bersihkan keranjang setelah pesanan dibuat
                    request.session['cart'] = []

                    messages.success(request, "Pesanan Anda berhasil diproses!")
                    return redirect('order_success')

            except Exception as e:
                messages.error(request, "Terjadi kesalahan saat memproses pesanan. Silakan coba lagi.")
                logger.error(f"Error processing order for user {request.user.id}: {str(e)}")
                return redirect('checkout')

        else:
            # Saldo tidak mencukupi
            messages.error(request, "Saldo Anda tidak mencukupi untuk melakukan pembayaran.")
            return redirect('profile')

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

# Menambahkan item ke dalam keranjang
def add_to_cart(request):
    if request.method == "POST":
        data = json.loads(request.body)
        item_id = data.get('id')
        item_name = data.get('name')
        item_price = data.get('price')
        item_image = data.get('image')
        item_model = data.get('model')

        # Mengambil keranjang dari sesi berdasarkan pengguna yang sedang login
        cart = request.session.get('cart', {})

        # Menambahkan item baru ke dalam keranjang
        user_cart = cart.get(str(request.user.id), [])
        user_cart.append({
            'id': item_id,
            'name': item_name,
            'price': item_price,
            'image': item_image,
            'model': item_model
        })

        cart[str(request.user.id)] = user_cart
        request.session['cart'] = cart  # Menyimpan kembali ke sesi

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
            return redirect('signup')  # Kembali ke form login di halaman yang sama
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
            logger.info(f"User {username} berhasil login.")
            logger.info(f"Email: {user.email}, IP: {get_client_ip(request)}")

            ip_address = get_client_ip(request)
            logger.info(f"IP Address sebelum menyimpan: {ip_address}")

            # Menyimpan riwayat login
            try:
                login_history = LoginHistory.objects.create(
                    user=user,
                    email=user.email,
                    login_time=now(),
                    ip_address=ip_address
                )
                logger.info(f"Riwayat login berhasil disimpan: {login_history}")
            except Exception as e:
                logger.error(f"Error saat menyimpan riwayat login: {str(e)}")
            
            next_url = request.GET.get('next', 'home')  # Default ke 'home'
            return redirect(next_url)
        else:
            logger.warning(f"Login gagal untuk {username}.")
            messages.error(request, "Username atau password tidak valid.")
            return redirect('login')

    return render(request, 'signup.html')

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
        return redirect('profile')  # Atau halaman lain yang sesuai
    
    if request.method == 'POST':
        client_id = request.POST.get('client_id')
        nominal = request.POST.get('nominal')

        try:
            user = User.objects.get(id=client_id)  # Mendapatkan user berdasarkan ID
            user.profile.balance += int(nominal)  # Menambahkan saldo
            user.profile.save()  # Menyimpan perubahan saldo
            messages.success(request, f"Saldo untuk {user.username} berhasil di-top up sebesar {nominal} IDR.")
        except User.DoesNotExist:
            messages.error(request, "User tidak ditemukan.")
        except ValueError:
            messages.error(request, "Nominal tidak valid.")
        
        return redirect('top_up_balance')  # Redirect kembali ke halaman top-up

    # Mengambil semua user yang ada
    users = User.objects.all()
    return render(request, 'topup.html', {'users': users})

def request_top_up(request):
    if request.method == 'POST':
        amount = request.POST.get('amount')
        
        try:
            amount = int(amount)
            # Membuat record permintaan top-up
            top_up_request = TopUpRequest.objects.create(user=request.user, amount=amount)
            messages.success(request, "Permintaan top-up berhasil diajukan.")
            return redirect('profile')  # Kembali ke halaman profil pengguna
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

    # Perbarui status dan tambah saldo pengguna
    top_up_request.status = 'Sukses'
    top_up_request.save()

    user = top_up_request.user
    top_up_amount = Decimal(top_up_request.amount)
    user.profile.balance += top_up_amount
    user.profile.save()

    # Simpan ke riwayat transaksi
    TransactionHistory.objects.create(
        user=user,
        amount=top_up_request.amount,
        status='Approved'
    )

    # Hapus permintaan top-up setelah disetujui (opsional)
    top_up_request.delete()

    messages.success(request, f"Top-up sebesar {top_up_amount} IDR disetujui untuk {user.username}.")
    return redirect('admin_top_up_requests')

def reject_top_up(request, request_id):
    top_up_request = get_object_or_404(TopUpRequest, id=request_id)

    # Simpan ke riwayat transaksi
    TransactionHistory.objects.create(
        user=top_up_request.user,
        amount=top_up_request.amount,
        status='Rejected'
    )

    # Hapus permintaan top-up
    top_up_request.delete()

    messages.success(request, f"Permintaan top-up oleh {top_up_request.user.username} ditolak.")
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
