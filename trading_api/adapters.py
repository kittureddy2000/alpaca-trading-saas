"""Custom allauth adapters for OAuth authentication.

Handles Google OAuth callback to generate JWT tokens and redirect to frontend.
"""

import logging
from django.conf import settings
from django.shortcuts import redirect
from django.http import HttpResponseRedirect
from allauth.socialaccount.adapter import DefaultSocialAccountAdapter
from allauth.account.adapter import DefaultAccountAdapter
from rest_framework_simplejwt.tokens import RefreshToken
from urllib.parse import urlencode

logger = logging.getLogger(__name__)


class CustomAccountAdapter(DefaultAccountAdapter):
    """Custom account adapter for OAuth redirects."""

    def get_login_redirect_url(self, request):
        """
        Redirect to frontend with JWT tokens after successful login.
        """
        print("DEBUG: CustomAccountAdapter.get_login_redirect_url called")  # DEBUG
        user = request.user
        if user.is_authenticated:
            print(f"DEBUG: User is authenticated: {user.email}")  # DEBUG
            # Generate JWT tokens
            refresh = RefreshToken.for_user(user)
            tokens = {
                'access': str(refresh.access_token),
                'refresh': str(refresh),
            }

            # Build redirect URL with tokens and user info
            # The frontend will extract these from URL params
            frontend_url = getattr(settings, 'FRONTEND_URL', 'http://localhost:5173')

            # Build callback URL
            base_url = f"{frontend_url.rstrip('/')}/auth/callback"

            params = {
                'access': tokens['access'],
                'refresh': tokens['refresh'],
                'email': user.email,
                'name': getattr(user, 'name', '') or user.email.split('@')[0],
            }

            if hasattr(user, 'picture_url') and user.picture_url:
                params['picture'] = user.picture_url

            redirect_url = f"{base_url}?{urlencode(params)}"
            print(f"DEBUG: Redirecting to: {redirect_url}")  # DEBUG
            logger.info(f"OAuth login success, redirecting to frontend: {user.email}")

            return redirect_url

        print("DEBUG: User NOT authenticated in get_login_redirect_url")  # DEBUG
        return super().get_login_redirect_url(request)


class CustomSocialAccountAdapter(DefaultSocialAccountAdapter):
    """Custom social account adapter for Google OAuth."""

    def pre_social_login(self, request, sociallogin):
        """
        Invoked just after a user successfully authenticates via a social provider.
        Associates the social account with an existing user if email matches.
        """
        print("DEBUG: pre_social_login called")  # DEBUG
        logger.info(f"pre_social_login triggered for provider: {sociallogin.account.provider}")
        
        # Check if email is already in use
        if sociallogin.is_existing:
            print("DEBUG: Social login account already exists")  # DEBUG
            logger.info("Social login account already exists.")
            return

        email = sociallogin.user.email
        if not email:
            print("DEBUG: No email provided")  # DEBUG
            logger.warning("No email provided in social login.")
            return

        print(f"DEBUG: Processing email: {email}")  # DEBUG
        logger.info(f"Processing new social login for email: {email}")

        # Try to find existing user with this email
        from django.contrib.auth import get_user_model
        User = get_user_model()

        try:
            print("DEBUG: Looking up existing user...")  # DEBUG
            existing_user = User.objects.get(email=email.lower())
            print(f"DEBUG: Found existing user: {existing_user}")  # DEBUG
            # Connect this social login to the existing user
            sociallogin.connect(request, existing_user)
            print("DEBUG: Connected social account")  # DEBUG
            logger.info(f"Connected Google account to existing user: {email}")
        except User.DoesNotExist:
            print("DEBUG: User.DoesNotExist caught")  # DEBUG
            logger.info(f"No existing user found for {email}, proceeding to signup.")
        except Exception as e:
            print(f"DEBUG: Exception in pre_social_login: {e}")  # DEBUG
            logger.error(f"Error in pre_social_login for {email}: {str(e)}", exc_info=True)

    def authentication_error(self, request, provider_id, error=None, exception=None, extra_context=None):
        """
        Invoked when there is an error during social authentication.
        """
        print(f"DEBUG: authentication_error called: {error}")  # DEBUG
        logger.error(f"Social Account Authentication Error! Provider: {provider_id}")
        logger.error(f"Error: {error}")
        logger.error(f"Exception: {exception}")
        if extra_context:
            logger.error(f"Extra Context: {extra_context}")
            
        # DefaultSocialAccountAdapter does not have an authentication_error method,
        # so we just log the error and return (implicit None, or handle as needed).
        return

    def save_user(self, request, sociallogin, form=None):
        """
        Save the newly signed up social user.
        """
        try:
            print("DEBUG: save_user called")  # DEBUG
            logger.info("Attempting to save new social user...")
            user = super().save_user(request, sociallogin, form)

            # Update user with Google profile data
            extra_data = sociallogin.account.extra_data
            logger.debug(f"Extra data from provider: {extra_data}")

            if not user.name and extra_data.get('name'):
                user.name = extra_data.get('name', '')

            if not user.picture_url and extra_data.get('picture'):
                user.picture_url = extra_data.get('picture', '')

            user.auth_provider = 'google'
            user.email_verified = True

            try:
                user.save()
                print(f"DEBUG: User saved: {user.email}")  # DEBUG
                logger.info(f"Created new user from Google OAuth: {user.email}")
            except Exception as e:
                print(f"DEBUG: Error saving user: {e}")  # DEBUG
                logger.error(f"Error creating user from Google OAuth {user.email}: {e}", exc_info=True)
                raise

            return user

        except Exception as e:
            # Catch errors from super().save_user() or anywhere else
            email = 'unknown'
            if sociallogin and sociallogin.user:
                email = getattr(sociallogin.user, 'email', 'unknown')
            print(f"DEBUG: Critical save_user error: {e}")  # DEBUG
            logger.error(f"CRITICAL: Google OAuth save_user failed for {email}: {str(e)}", exc_info=True)
            raise
