"""Custom allauth adapters for OAuth authentication.

Handles Google OAuth callback to generate JWT tokens and redirect to frontend.
"""

import logging
from django.conf import settings
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
        user = request.user
        if user.is_authenticated:
            logger.debug(f"User is authenticated: {user.email}")
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
            logger.info(f"OAuth login success, redirecting to frontend: {user.email}")

            return redirect_url

        logger.debug("User NOT authenticated in get_login_redirect_url")
        return super().get_login_redirect_url(request)


class CustomSocialAccountAdapter(DefaultSocialAccountAdapter):
    """Custom social account adapter for Google OAuth."""

    def pre_social_login(self, request, sociallogin):
        """
        Invoked just after a user successfully authenticates via a social provider.
        Associates the social account with an existing user if email matches.
        """
        logger.info(f"pre_social_login triggered for provider: {sociallogin.account.provider}")

        # Check if email is already in use
        if sociallogin.is_existing:
            logger.info("Social login account already exists.")
            return

        email = sociallogin.user.email
        if not email:
            logger.warning("No email provided in social login.")
            return

        logger.info(f"Processing new social login for email: {email}")

        # Try to find existing user with this email
        from django.contrib.auth import get_user_model
        User = get_user_model()

        try:
            existing_user = User.objects.get(email=email.lower())
            # Connect this social login to the existing user
            sociallogin.connect(request, existing_user)
            logger.info(f"Connected Google account to existing user: {email}")
        except User.DoesNotExist:
            logger.info(f"No existing user found for {email}, proceeding to signup.")
        except Exception as e:
            logger.error(f"Error in pre_social_login for {email}: {str(e)}", exc_info=True)

    def authentication_error(self, request, provider_id, error=None, exception=None, extra_context=None):
        """
        Invoked when there is an error during social authentication.
        """
        logger.error(f"Social Account Authentication Error! Provider: {provider_id}, Error: {error}")
        if extra_context:
            logger.error(f"Extra Context: {extra_context}")

        try:
            logger.debug(f"Request path: {request.path}")
            logger.debug(f"GET params: {request.GET}")

            if hasattr(request, 'session'):
                logger.debug(f"Session ID: {request.session.session_key}")
                logger.debug(f"Session keys: {list(request.session.keys())}")
            else:
                logger.debug("Request has no session attribute")

            logger.debug(f"Cookies: {list(request.COOKIES.keys())}")
        except Exception as e:
            logger.debug(f"Error inspecting request: {e}")

    def save_user(self, request, sociallogin, form=None):
        """
        Save the newly signed up social user.
        """
        try:
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
                logger.info(f"Created new user from Google OAuth: {user.email}")
            except Exception as e:
                logger.error(f"Error creating user from Google OAuth {user.email}: {e}", exc_info=True)
                raise

            return user

        except Exception as e:
            email = 'unknown'
            if sociallogin and sociallogin.user:
                email = getattr(sociallogin.user, 'email', 'unknown')
            logger.error(f"CRITICAL: Google OAuth save_user failed for {email}: {str(e)}", exc_info=True)
            raise
