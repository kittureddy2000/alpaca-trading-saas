"""Authentication views.

Supports email/password and Google OAuth authentication.
"""

import os
import re
import logging
from django.conf import settings
from django.contrib.auth import login, logout
from django.shortcuts import redirect
from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework_simplejwt.tokens import RefreshToken
from google.oauth2 import id_token
from google.auth.transport import requests as google_requests

from trading_api.models import User, UserSettings, UserSubscription

logger = logging.getLogger(__name__)


def validate_email(email: str) -> bool:
    """Validate email format."""
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return re.match(pattern, email) is not None


def validate_password(password: str) -> tuple:
    """Validate password strength."""
    if len(password) < 8:
        return False, "Password must be at least 8 characters"
    if not re.search(r'[A-Z]', password):
        return False, "Password must contain at least one uppercase letter"
    if not re.search(r'[a-z]', password):
        return False, "Password must contain at least one lowercase letter"
    if not re.search(r'[0-9]', password):
        return False, "Password must contain at least one number"
    return True, ""


def get_tokens_for_user(user):
    """Generate JWT tokens for a user."""
    refresh = RefreshToken.for_user(user)
    return {
        'refresh': str(refresh),
        'access': str(refresh.access_token),
    }


class RegisterView(APIView):
    """Register a new user with email and password."""

    permission_classes = [AllowAny]

    def post(self, request):
        try:
            email = request.data.get('email', '').strip().lower()
            password = request.data.get('password', '')
            name = request.data.get('name', '').strip()

            # Validate email
            if not email or not validate_email(email):
                return Response(
                    {'error': 'Invalid email address'},
                    status=status.HTTP_400_BAD_REQUEST
                )

            # Validate password
            valid, message = validate_password(password)
            if not valid:
                return Response(
                    {'error': message},
                    status=status.HTTP_400_BAD_REQUEST
                )

            # Check if user exists
            if User.objects.filter(email=email).exists():
                return Response(
                    {'error': 'Email already registered'},
                    status=status.HTTP_409_CONFLICT
                )

            # Create user
            user = User.objects.create_user(
                email=email,
                password=password,
                name=name or email.split('@')[0],
                auth_provider='local',
                is_active=True,
                email_verified=False
            )

            # Create default settings and subscription
            UserSettings.objects.create(user=user)
            UserSubscription.objects.create(user=user, tier='free', status='active')

            # Generate tokens
            tokens = get_tokens_for_user(user)

            logger.info(f"New user registered: {email}")

            return Response({
                'success': True,
                'message': 'Registration successful',
                'user': {
                    'email': user.email,
                    'name': user.name,
                    'authenticated': True,
                },
                'tokens': tokens,
            }, status=status.HTTP_201_CREATED)

        except Exception as e:
            logger.error(f"Registration error: {e}")
            return Response(
                {'error': 'Registration failed. Please try again.'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class LoginView(APIView):
    """User login endpoint."""

    permission_classes = [AllowAny]

    def post(self, request):
        email = request.data.get('email', '').strip().lower()
        password = request.data.get('password', '')

        if not email or not password:
            return Response(
                {'error': 'Email and password are required'},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            return Response(
                {'error': 'Invalid email or password'},
                status=status.HTTP_401_UNAUTHORIZED
            )

        if not user.check_password(password):
            return Response(
                {'error': 'Invalid email or password'},
                status=status.HTTP_401_UNAUTHORIZED
            )

        # Generate tokens
        refresh = RefreshToken.for_user(user)

        logger.info(f"User logged in: {email}")

        return Response({
            'authenticated': True,
            'email': user.email,
            'name': user.name,
            'picture': user.picture,
            'tokens': {
                'access': str(refresh.access_token),
                'refresh': str(refresh),
            }
        })


class LogoutView(APIView):
    """User logout endpoint."""

    permission_classes = [AllowAny]

    def post(self, request):
        refresh_token = request.data.get('refresh')
        if refresh_token:
            try:
                token = RefreshToken(refresh_token)
                token.blacklist()
            except:
                pass

        logout(request)

        return Response({'success': True})

    def get(self, request):
        """Handle GET logout - redirect to frontend."""
        logout(request)
        frontend_url = settings.FRONTEND_URL
        return redirect(frontend_url)


class CurrentUserView(APIView):
    """Get current authenticated user."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user

        # Get subscription info
        try:
            subscription = user.subscription.get_features()
        except:
            subscription = {'tier': 'free'}

        return Response({
            'authenticated': True,
            'email': user.email,
            'name': user.name,
            'picture': user.picture,
            'alpaca_connected': user.alpaca_connected,
            'alpaca_is_paper': user.alpaca_is_paper,
            'subscription': subscription,
        })


class GoogleCallbackView(APIView):
    """Handle Google OAuth callback from allauth redirect flow."""

    permission_classes = [AllowAny]

    def get(self, request):
        """
        After Google OAuth, allauth creates/logs in the user.
        We generate JWT tokens and redirect to frontend.
        """
        user = request.user

        if not user.is_authenticated:
            # Redirect to login if not authenticated
            return redirect(f"{settings.FRONTEND_URL}?error=auth_failed")

        # Ensure settings and subscription exist
        UserSettings.objects.get_or_create(user=user)
        UserSubscription.objects.get_or_create(
            user=user,
            defaults={'tier': 'free', 'status': 'active'}
        )

        # Generate tokens
        refresh = RefreshToken.for_user(user)

        logger.info(f"Google OAuth callback for user: {user.email}")

        # Redirect to frontend with tokens
        frontend_url = settings.FRONTEND_URL
        return redirect(
            f"{frontend_url}/auth/callback"
            f"?access={refresh.access_token}"
            f"&refresh={refresh}"
        )


class GoogleLoginCallbackView(APIView):
    """Handle frontend-driven Google OAuth token verification.

    This endpoint receives a Google ID token from the frontend,
    verifies it with Google, and creates/updates the user.
    """

    permission_classes = [AllowAny]

    def post(self, request):
        token = request.data.get('token')

        if not token:
            return Response(
                {'error': 'Token is required'},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            # Get Google client ID - try env var first, then database SocialApp
            client_id = os.environ.get('GOOGLE_CLIENT_ID', '')

            if not client_id:
                try:
                    from allauth.socialaccount.models import SocialApp
                    app = SocialApp.objects.filter(provider='google').first()
                    if app:
                        client_id = app.client_id
                except Exception:
                    pass

            if not client_id:
                logger.error("Google client ID not configured in env or database")
                return Response(
                    {'error': 'Google OAuth not configured'},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR
                )

            # Verify the token with Google
            id_info = id_token.verify_oauth2_token(
                token,
                google_requests.Request(),
                client_id
            )

            # Extract user info from token
            email = id_info.get('email', '').lower()
            name = id_info.get('name', '')
            picture = id_info.get('picture', '')
            google_id = id_info.get('sub', '')

            if not email:
                return Response(
                    {'error': 'Email not provided by Google'},
                    status=status.HTTP_400_BAD_REQUEST
                )

            # Get or create user
            user, created = User.objects.get_or_create(
                email=email,
                defaults={
                    'name': name or email.split('@')[0],
                    'picture_url': picture,
                    'google_id': google_id,
                    'auth_provider': 'google',
                    'email_verified': True,
                    'is_active': True,
                }
            )

            if not created:
                # Update existing user with Google info
                if not user.name and name:
                    user.name = name
                if not user.picture_url and picture:
                    user.picture_url = picture
                if not user.google_id:
                    user.google_id = google_id
                if user.auth_provider == 'local':
                    user.auth_provider = 'both'
                user.email_verified = True
                user.save()

            # Ensure settings and subscription exist
            UserSettings.objects.get_or_create(user=user)
            UserSubscription.objects.get_or_create(
                user=user,
                defaults={'tier': 'free', 'status': 'active'}
            )

            # Update last login
            user.update_last_login()

            # Generate JWT tokens
            refresh = RefreshToken.for_user(user)

            logger.info(f"Google login {'created' if created else 'updated'} user: {email}")

            return Response({
                'success': True,
                'authenticated': True,
                'email': user.email,
                'name': user.name,
                'picture': user.picture_url,
                'tokens': {
                    'access': str(refresh.access_token),
                    'refresh': str(refresh),
                }
            })

        except ValueError as e:
            logger.error(f"Invalid Google token: {e}")
            return Response(
                {'error': 'Invalid Google token'},
                status=status.HTTP_401_UNAUTHORIZED
            )
        except Exception as e:
            logger.error(f"Google login error: {e}")
            return Response(
                {'error': 'Authentication failed. Please try again.'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
