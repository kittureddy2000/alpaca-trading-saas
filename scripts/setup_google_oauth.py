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

    # Clean up any duplicate Sites first (keep only id=1)
    extra_sites = Site.objects.exclude(id=1)
    if extra_sites.exists():
        count = extra_sites.count()
        extra_sites.delete()
        print(f"⚠️ Deleted {count} duplicate Site(s)")

    # ALWAYS create the Site first (required by allauth even without OAuth)
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
        else:
            print(f"✅ Site already exists: {site.domain}")

    # Now check for OAuth credentials
    client_id = os.environ.get('GOOGLE_CLIENT_ID', '')
    client_secret = os.environ.get('GOOGLE_CLIENT_SECRET', '')

    if not client_id:
        print("⚠️ GOOGLE_CLIENT_ID not set, skipping OAuth app setup (Site created)")
        return True  # Return True since Site was created successfully

    if not client_secret:
        print("⚠️ GOOGLE_CLIENT_SECRET not set, skipping OAuth app setup (Site created)")
        return True  # Return True since Site was created successfully

    # Debug: Show all SocialApps in the database
    all_apps = SocialApp.objects.all()
    print(f"📋 All SocialApps in database: {list(all_apps.values_list('id', 'provider', 'name'))}")

    # Check if Google provider already exists - handle duplicates
    google_apps = SocialApp.objects.filter(provider='google')

    if google_apps.count() > 1:
        # Multiple apps exist - delete all but keep the first one
        print(f"⚠️ Found {google_apps.count()} Google OAuth apps, cleaning up duplicates...")
        first_app = google_apps.first()
        google_apps.exclude(pk=first_app.pk).delete()
        google_app = first_app
        print("✅ Cleaned up duplicate OAuth apps")
    elif google_apps.exists():
        google_app = google_apps.first()
    else:
        google_app = None

    if google_app:
        # Update existing app
        google_app.client_id = client_id
        google_app.secret = client_secret
        google_app.name = 'Google OAuth'
        google_app.save()

        # Debug: show current site associations
        current_sites = list(google_app.sites.values_list('id', flat=True))
        print(f"📋 Current site associations for OAuth app: {current_sites}")

        # Clear all site links and add only Site id=1 to avoid duplicates
        google_app.sites.clear()
        google_app.sites.add(site)

        # Verify cleanup
        final_sites = list(google_app.sites.values_list('id', flat=True))
        print(f"📋 After cleanup, site associations: {final_sites}")

        print(f"✅ Updated Google OAuth app (client_id: {client_id[:20]}...)")
    else:
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
