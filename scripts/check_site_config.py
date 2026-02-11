import os
import sys
import django

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings.production')
django.setup()

from django.contrib.sites.models import Site
from allauth.socialaccount.models import SocialApp

print("--- Site Configuration ---")
for site in Site.objects.all():
    print(f"ID: {site.id}, Domain: {site.domain}, Name: {site.name}")

print("\n--- SocialApp Configuration ---")
for app in SocialApp.objects.all():
    print(f"ID: {app.id}, Name: {app.name}, Provider: {app.provider}")
    print(f"Client ID: {app.client_id}")
    if app.secret:
        print(f"Client Secret (Masked): {app.secret[:3]}...{app.secret[-3:]}")
    else:
        print("Client Secret: NOT SET")
    print(f"Sites: {[s.domain for s in app.sites.all()]}")
