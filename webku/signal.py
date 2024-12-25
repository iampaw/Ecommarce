from django.contrib.auth.signals import user_logged_in
from django.dispatch import receiver
from .models import LoginHistory
from django.http import HttpRequest

@receiver(user_logged_in)
def log_user_login(sender, request: HttpRequest, user, **kwargs):
    # Mendapatkan alamat IP pengguna
    ip_address = request.META.get('REMOTE_ADDR')

    # Simpan informasi login ke dalam LoginHistory
    LoginHistory.objects.create(user=user, ip_address=ip_address)