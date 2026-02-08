"""Authentication views."""

import logging
from django.conf import settings
from django.contrib.auth import login, logout
from django.shortcuts import redirect
from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework_simplejwt.tokens import RefreshToken

from trading_api.models import User, UserSettings, UserSubscription

logger = logging.getLogger(__name__)


class RegisterView(APIView):
    """User registration endpoint."""

    permission_classes = [AllowAny]

    def post(self, request):
        email = request.data.get('email', '').strip().lower()
        password = request.data.get('password', '')
        name = request.data.get('name', '').strip()

        if not email or not password:
            return Response(
                {'error': 'Email and password are required'},
                status=status.HTTP_400_BAD_REQUEST
            )

        if User.objects.filter(email=email).exists():
            return Response(
                {'error': 'Email already registered'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Create user
        user = User.objects.create_user(email=email, password=password, name=name)

        # Create default settings and subscription
        UserSettings.objects.create(user=user)
        UserSubscription.objects.create(user=user, tier='free', status='active')

        # Generate tokens
        refresh = RefreshToken.for_user(user)

        logger.info(f"User registered: {email}")

        return Response({
            'success': True,
            'user': {
                'email': user.email,
                'name': user.name,
            },
            'tokens': {
                'access': str(refresh.access_token),
                'refresh': str(refresh),
            }
        }, status=status.HTTP_201_CREATED)


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
    """Handle Google OAuth callback."""

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
