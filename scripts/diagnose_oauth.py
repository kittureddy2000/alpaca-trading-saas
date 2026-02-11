import os
import django
import sys

# Setup Django environment
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "backend.settings.production")
django.setup()

from allauth.socialaccount.models import SocialApp
from django.contrib.sites.models import Site

def diagnose():
    print("--- Diagnostic Report ---")
    
    print(f"\n1. Sites ({Site.objects.count()} total):")
    for site in Site.objects.all():
        print(f"   ID: {site.id} | Domain: {site.domain} | Name: {site.name}")

    print(f"\n2. SocialApps ({SocialApp.objects.count()} total):")
    for app in SocialApp.objects.all():
        print(f"   ID: {app.id} | Provider: {app.provider} | Name: {app.name}")
        print(f"   Client ID: {app.client_id[:10]}...{app.client_id[-5:]}")
        print(f"   Linked Sites: {[s.domain for s in app.sites.all()]}")
        
    print("\n--- End Report ---")

if __name__ == "__main__":
    diagnose()
