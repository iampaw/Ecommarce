from django.apps import AppConfig

class WebkuConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'webku'

class AccountsConfig(AppConfig):
    name = 'accounts'

    def ready(self):
        import accounts.signals 
