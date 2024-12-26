from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login
from django.contrib.auth.forms import AuthenticationForm
from .forms import SignupForm

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

def login_view(request):
    if request.method == 'POST':
        form = AuthenticationForm(data=request.POST)
        if form.is_valid():
            user = form.get_user()
            login(request, user)
            return redirect('/')  # Redirect ke halaman utama
    else:
        form = AuthenticationForm()
    return render(request, 'login.html', {'form': form})
