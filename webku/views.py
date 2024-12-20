from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, authenticate, logout
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm
from django.contrib import messages
from .models import Makanan, Makanan2, LoginHistory, Profile, Address, Client, TopUpRequest
from django.http import HttpResponse, JsonResponse
from django.contrib.auth.models import User
from django.utils.timezone import now
import logging
from django.contrib.auth.decorators import login_required
from .forms import ProfileForm, UserUpdateForm
from .forms import AddressForm
from django.contrib import messages
from decimal import Decimal
from datetime import datetime


logger = logging.getLogger(__name__)

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

def checkout(request):
    cart = request.session.get("cart", [])
    return render(request, "checkout.html", {"cart": cart})

def address_view(request):
    return render(request, 'address.html')

@login_required
def add_to_cart(request):
    if request.method == "POST":
        item = request.POST
        cart = request.session.get("cart", [])
        cart.append({
            "name": item.get("name"),
            "price": float(item.get("price")),
            "image": item.get("image"),
        })
        request.session["cart"] = cart
        return JsonResponse({"success": True})
    else:
        # Jika user tidak login, redirect ke halaman signup
        return redirect('signup')  # Atau bisa juga 'login' jika ingin halaman login terlebih dahulu

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
        # Mendapatkan data username dan password dari form POST
        username = request.POST.get('username')
        password = request.POST.get('password')
        
        # Mencoba untuk mengautentikasi pengguna
        user = authenticate(request, username=username, password=password)
        
        if user is not None:
            # Jika autentikasi berhasil, login pengguna
            login(request, user)

            # Log keberhasilan login
            logger.info(f"User {username} berhasil login.")
            logger.info(f"Email: {user.email}, IP: {get_client_ip(request)}")

            # Simpan riwayat login ke database
            try:
                LoginHistory.objects.create(
                    user=user,
                    email=user.email,
                    login_time=now(),
                    ip_address=get_client_ip(request)
                )
                logger.info("Riwayat login berhasil disimpan.")
            except Exception as e:
                logger.error(f"Error saat menyimpan riwayat login: {str(e)}")

            # Redirect pengguna ke halaman 'next' atau halaman home
            next_url = request.GET.get('next', 'home')  # Jika tidak ada 'next', default ke 'home'
            return redirect(next_url)

        else:
            # Jika autentikasi gagal, log kegagalan login
            logger.warning(f"Login gagal untuk {username}.")
            messages.error(request, "Username atau password tidak valid.")
            return redirect('login')  # Kembali ke halaman login untuk mencoba lagi

    # Jika request menggunakan metode GET, tampilkan halaman login
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
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0]
    else:
        ip = request.META.get('REMOTE_ADDR')
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

    requests = TopUpRequest.objects.filter(status='Pending')  # Ambil permintaan yang statusnya Pending
    return render(request, 'admin_top_up_requests.html', {'requests': requests})

def approve_top_up(request, request_id):
    top_up_request = get_object_or_404(TopUpRequest, id=request_id)
    top_up_request.status = 'Approved'
    top_up_request.save()

    user = top_up_request.user
    if not hasattr(user, 'profile'):
        messages.error(request, f"User {user.username} tidak memiliki profile. Top-up gagal disetujui.")
        return redirect('admin_top_up_requests')

    # Pastikan saldo ditambah dengan tipe data Decimal
    top_up_amount = Decimal(top_up_request.amount)

    print(f"Saldo sebelum top-up: {user.profile.balance}")
    user.profile.balance += top_up_amount
    user.profile.save()
    print(f"Saldo sesudah top-up: {user.profile.balance}")

    messages.success(request, f"Top-up sebesar {top_up_amount} IDR disetujui untuk {user.username}.")
    return redirect('admin_top_up_requests')

def reject_top_up(request, request_id):
    top_up_request = TopUpRequest.objects.get(id=request_id)
    top_up_request.status = 'Rejected'
    top_up_request.save()

    messages.success(request, f"Permintaan top-up oleh {top_up_request.user.username} ditolak.")
    return redirect('admin_top_up_requests')