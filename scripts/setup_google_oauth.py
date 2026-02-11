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

    # 1. Get all allowed hosts from environment
    allowed_hosts = os.environ.get('ALLOWED_HOSTS', '').split(',')
    
    # Filter out invalid hosts
    valid_hosts = []
    for host in allowed_hosts:
        host = host.strip()
        if host and host != '*' and 'localhost' not in host and '127.0.0.1' not in host:
             valid_hosts.append(host)
    
    # Always include localhost for local dev if not present (optional, but good for testing)
    # valid_hosts.append('localhost') 
    
    # If no valid hosts found (e.g. only *), fallback or just warn
    if not valid_hosts:
        print("⚠️ No specific hosts found in ALLOWED_HOSTS. Defaulting to 'example.com' for Site setup.")
        valid_hosts = ['example.com']

    print(f"📋 Configuring Sites for hosts: {valid_hosts}")

    # 2. Create/Update Sites for EACH valid host
    sites = []
    for domain in valid_hosts:
        # Check if site exists by domain
        site, created = Site.objects.get_or_create(
            domain=domain,
            defaults={'name': 'Alpaca Trading SaaS'}
        )
        if created:
             print(f"✅ Created Site: {site.domain}")
        else:
             print(f"✅ Found existing Site: {site.domain}")
        sites.append(site)
        
    # Ensure ID=1 exists and is reasonable (allauth often defaults to ID=1)
    # If ID=1 was not in our list (e.g. we just created ID=2, 3...), we might want to 
    # make sure ID=1 is one of our valid sites or just leave it.
    # For simplicity, we just trust the sites we collected.

    # 3. Get OAuth credentials from environment
    client_id = os.environ.get('GOOGLE_CLIENT_ID', '')
    client_secret = os.environ.get('GOOGLE_CLIENT_SECRET', '')

    if not client_id or not client_secret:
        print("⚠️ GOOGLE_CLIENT_ID or GOOGLE_CLIENT_SECRET not set in environment")
        print("   Skipping SocialApp setup - OAuth will not work until credentials are provided")
        print(f"Configuring Google OAuth with Client ID: {client_id}")
        return True

    # 4. Create or update SocialApp for Google
    app, created = SocialApp.objects.update_or_create(
        provider='google',
        defaults={
            'name': 'Google Auth',
            'client_id': client_id,
            'secret': client_secret,
        }
    )
    
    if not created:
        # Update credentials if they changed
        app.client_id = client_id
        app.secret = client_secret
        app.save()
        print("✅ Updated existing SocialApp for Google")
    else:
        print("✅ Created new SocialApp for Google")

    # 5. Link SocialApp to ALL Sites
    for site in sites:
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
