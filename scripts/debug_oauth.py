#!/usr/bin/env python
"""Debug OAuth configuration - check SocialApp and Site entries."""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings.production')

import django
django.setup()

from django.contrib.sites.models import Site
from allauth.socialaccount.models import SocialApp

print("=" * 60)
print("OAuth Debug Information")
print("=" * 60)

print("\n1. Sites in database:")
for site in Site.objects.all():
    print(f"   - id={site.id}, domain={site.domain}, name={site.name}")

print(f"\nTotal Sites: {Site.objects.count()}")

print("\n2. SocialApps in database:")
for app in SocialApp.objects.all():
    sites = list(app.sites.values_list('id', 'domain'))
    print(f"   - id={app.id}, provider={app.provider}")
    print(f"     client_id={app.client_id[:20]}...")
    print(f"     linked sites: {sites}")

print(f"\nTotal SocialApps: {SocialApp.objects.count()}")
print(f"Google SocialApps: {SocialApp.objects.filter(provider='google').count()}")

print("\n3. Checking for duplicates:")
if SocialApp.objects.filter(provider='google').count() > 1:
    print("   ❌ MULTIPLE Google SocialApps found - this causes MultipleObjectsReturned!")
    print("   Deleting duplicates...")
    apps = SocialApp.objects.filter(provider='google')
    first = apps.first()
    deleted = apps.exclude(id=first.id).delete()
    print(f"   ✅ Deleted {deleted[0]} duplicate(s)")
else:
    print("   ✅ No duplicates found")

print("\n" + "=" * 60)
