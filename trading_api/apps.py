from django.apps import AppConfig


class TradingApiConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'trading_api'
    verbose_name = 'Trading API'

    def ready(self):
        # Import signals if any
        pass
