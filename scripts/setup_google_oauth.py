#!/usr/bin/env python
"""
Setup Google OAuth for allauth.
Creates/updates SocialApp in database and links to Site.

This is REQUIRED for allauth to work - settings-based APP config alone is NOT sufficient.
"""

import os
import sys
import django

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings.production')
django.setup()

from django.contrib.sites.models import Site
from allauth.socialaccount.models import SocialApp


def setup_google_oauth():
    """Configure Google OAuth with database SocialApp linked to Site."""
    print("🔐 Setting up Google OAuth...")

    # 1. Get site domain from ALLOWED_HOSTS
    allowed_hosts = os.environ.get('ALLOWED_HOSTS', '').split(',')
    site_domain = 'localhost'
    for host in allowed_hosts:
        host = host.strip()
        if host and host != '*':
            site_domain = host
            if '.run.app' in host:
                break  # Prefer Cloud Run URL

    # 2. Clean up duplicate Sites (keep only id=1)
    extra_sites = Site.objects.exclude(id=1)
    if extra_sites.exists():
        count = extra_sites.count()
        extra_sites.delete()
        print(f"⚠️ Deleted {count} duplicate Site(s)")

    # 3. Setup Site (id=1 required by allauth)
    site, created = Site.objects.get_or_create(
        id=1,
        defaults={'domain': site_domain, 'name': 'Alpaca Trading SaaS'}
    )
    if created:
        print(f"✅ Created Site: {site.domain}")
    elif site.domain != site_domain:
        site.domain = site_domain
        site.name = 'Alpaca Trading SaaS'
        site.save()
        print(f"✅ Updated Site domain to: {site.domain}")
    else:
        print(f"✅ Site already configured: {site.domain}")

    # 4. Get OAuth credentials from environment
    client_id = os.environ.get('GOOGLE_CLIENT_ID', '')
    client_secret = os.environ.get('GOOGLE_CLIENT_SECRET', '')

    if not client_id or not client_secret:
        print("⚠️ GOOGLE_CLIENT_ID or GOOGLE_CLIENT_SECRET not set in environment")
        print("   Skipping SocialApp setup - OAuth will not work until credentials are provided")
        return True

    # 5. Create or update SocialApp for Google
    apps = SocialApp.objects.filter(provider='google')
    if apps.exists():
        app = apps.first()
        app.client_id = client_id
        app.secret = client_secret
        app.name = 'Google Auth'
        app.save()
        print("✅ Updated existing SocialApp for Google")
    else:
        app = SocialApp.objects.create(
            provider='google',
            name='Google Auth',
            client_id=client_id,
            secret=client_secret,
        )
        print("✅ Created new SocialApp for Google")

    # 6. Link SocialApp to Site - CRITICAL for allauth to work!
    if site not in app.sites.all():
        app.sites.add(site)
        print(f"✅ Linked SocialApp to Site: {site.domain}")
    else:
        print(f"✅ SocialApp already linked to Site: {site.domain}")

    return True


if __name__ == '__main__':
    print("=" * 50)
    print("Google OAuth Setup Script")
    print("=" * 50)

    try:
        success = setup_google_oauth()
        if success:
            print("=" * 50)
            print("✅ Google OAuth setup complete!")
            print("=" * 50)
            sys.exit(0)
        else:
            print("⚠️ Setup completed with warnings")
            sys.exit(0)
    except Exception as e:
        print(f"❌ Error setting up Google OAuth: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
