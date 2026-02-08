#!/usr/bin/env python
"""
Setup Google OAuth provider in the database.

This script configures the allauth SocialApp for Google OAuth.
It should be run once during deployment to set up the OAuth provider.
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
    """Configure Google OAuth provider."""

    client_id = os.environ.get('GOOGLE_CLIENT_ID', '')
    client_secret = os.environ.get('GOOGLE_CLIENT_SECRET', '')

    if not client_id:
        print("⚠️ GOOGLE_CLIENT_ID not set, skipping OAuth setup")
        return False

    if not client_secret:
        print("⚠️ GOOGLE_CLIENT_SECRET not set, skipping OAuth setup")
        return False

    # Get or create the default site
    site, site_created = Site.objects.get_or_create(
        id=1,
        defaults={
            'domain': os.environ.get('ALLOWED_HOSTS', 'localhost').split(',')[0],
            'name': 'Alpaca Trading SaaS'
        }
    )

    if site_created:
        print(f"✅ Created site: {site.domain}")
    else:
        # Update site domain if needed
        allowed_hosts = os.environ.get('ALLOWED_HOSTS', '').split(',')
        if allowed_hosts and allowed_hosts[0] and site.domain != allowed_hosts[0]:
            site.domain = allowed_hosts[0]
            site.name = 'Alpaca Trading SaaS'
            site.save()
            print(f"✅ Updated site domain to: {site.domain}")

    # Check if Google provider already exists
    try:
        google_app = SocialApp.objects.get(provider='google')

        # Update existing app
        google_app.client_id = client_id
        google_app.secret = client_secret
        google_app.name = 'Google OAuth'
        google_app.save()

        # Ensure site is linked
        if not google_app.sites.filter(id=site.id).exists():
            google_app.sites.add(site)

        print(f"✅ Updated Google OAuth app (client_id: {client_id[:20]}...)")

    except SocialApp.DoesNotExist:
        # Create new Google app
        google_app = SocialApp.objects.create(
            provider='google',
            name='Google OAuth',
            client_id=client_id,
            secret=client_secret,
        )
        google_app.sites.add(site)

        print(f"✅ Created Google OAuth app (client_id: {client_id[:20]}...)")

    return True


if __name__ == '__main__':
    print("🔐 Setting up Google OAuth provider...")

    try:
        success = setup_google_oauth()
        if success:
            print("✅ Google OAuth setup complete!")
            sys.exit(0)
        else:
            print("⚠️ Google OAuth setup skipped (missing credentials)")
            sys.exit(0)  # Exit cleanly even if skipped
    except Exception as e:
        print(f"❌ Error setting up Google OAuth: {e}")
        sys.exit(1)
