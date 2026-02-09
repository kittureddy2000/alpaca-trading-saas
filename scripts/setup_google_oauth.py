#!/usr/bin/env python
"""
Setup Django Site for allauth.

OAuth credentials are now configured in settings via SOCIALACCOUNT_PROVIDERS['google']['APP']
This script only sets up the required Site and cleans up any old database OAuth apps.
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


def setup_site():
    """Configure Django Site for allauth."""

    # Clean up any duplicate Sites first (keep only id=1)
    extra_sites = Site.objects.exclude(id=1)
    if extra_sites.exists():
        count = extra_sites.count()
        extra_sites.delete()
        print(f"⚠️ Deleted {count} duplicate Site(s)")

    # Get the Cloud Run service URL from ALLOWED_HOSTS
    allowed_hosts = os.environ.get('ALLOWED_HOSTS', '').split(',')
    # Find the first .run.app domain or use the first host
    site_domain = 'localhost'
    for host in allowed_hosts:
        host = host.strip()
        if host and host != '*':
            site_domain = host
            if '.run.app' in host:
                break  # Prefer Cloud Run URL

    # ALWAYS create the Site first (required by allauth)
    site, site_created = Site.objects.get_or_create(
        id=1,
        defaults={
            'domain': site_domain,
            'name': 'Alpaca Trading SaaS'
        }
    )

    if site_created:
        print(f"✅ Created site: {site.domain}")
    else:
        # Update site domain if it changed
        if site.domain != site_domain:
            site.domain = site_domain
            site.name = 'Alpaca Trading SaaS'
            site.save()
            print(f"✅ Updated site domain to: {site.domain}")
        else:
            print(f"✅ Site already exists: {site.domain}")

    # IMPORTANT: Remove any database OAuth apps to avoid conflicts with settings-based APP
    # OAuth credentials are now in SOCIALACCOUNT_PROVIDERS['google']['APP'] in settings
    db_apps = SocialApp.objects.filter(provider='google')
    if db_apps.exists():
        count = db_apps.count()
        db_apps.delete()
        print(f"⚠️ Removed {count} database OAuth app(s) - using settings-based APP config")
    else:
        print("✅ No database OAuth apps (using settings-based APP config)")

    return True


if __name__ == '__main__':
    print("🔐 Setting up Django Site for allauth...")

    try:
        success = setup_site()
        if success:
            print("✅ Site setup complete!")
            print("📝 Note: OAuth credentials configured in settings via SOCIALACCOUNT_PROVIDERS")
            sys.exit(0)
        else:
            print("⚠️ Site setup failed")
            sys.exit(1)
    except Exception as e:
        print(f"❌ Error setting up Site: {e}")
        sys.exit(1)
