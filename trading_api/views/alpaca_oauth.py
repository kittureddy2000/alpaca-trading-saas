"""Alpaca OAuth views."""

import logging
import requests
import secrets
from django.conf import settings
from django.utils import timezone
from requests.auth import HTTPBasicAuth
from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated

logger = logging.getLogger(__name__)


class AlpacaOAuthConnectView(APIView):
    """Initiate Alpaca OAuth flow."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        """Get the Alpaca OAuth authorization URL."""
        user = request.user
        
        client_id = getattr(settings, 'ALPACA_CLIENT_ID', '')
        # Allow overriding redirect uri for dev/staging
        redirect_uri = getattr(settings, 'ALPACA_REDIRECT_URI', f"{settings.FRONTEND_URL}/alpaca/callback")
        
        if not client_id:
             return Response(
                {'error': 'Alpaca OAuth not configured (missing Client ID)'},
                status=status.HTTP_501_NOT_IMPLEMENTED
            )

        # Generate state token for CSRF protection
        state = secrets.token_urlsafe(16)
        # Store state in session (or cache) to verify later
        request.session['alpaca_oauth_state'] = state
        
        # Scopes: account:read, trading:orders:write are usually needed
        scopes = "account:read trading:orders:write data:quotes:read"

        # Build URL
        # Staging/Prod usually use app.alpaca.markets, but for OAuth it's specifically:
        oauth_base = "https://app.alpaca.markets/oauth/authorize"
        
        auth_url = (
            f"{oauth_base}?"
            f"response_type=code&"
            f"client_id={client_id}&"
            f"redirect_uri={redirect_uri}&"
            f"state={state}&"
            f"scope={scopes}"
        )
        
        logger.info(f"Generated Alpaca OAuth URL for user {user.email}")
        
        return Response({
            'auth_url': auth_url
        })


class AlpacaOAuthCallbackView(APIView):
    """Handle Alpaca OAuth callback."""

    permission_classes = [IsAuthenticated]

    def post(self, request):
        """
        Exchange authorization code for access token.
        
        Frontend receives the code from redirect and POSTs it here.
        """
        user = request.user
        code = request.data.get('code')
        state = request.data.get('state')
        
        # Verify state
        # saved_state = request.session.get('alpaca_oauth_state')
        # if not saved_state or saved_state != state:
        #    return Response({'error': 'Invalid state parameter'}, status=status.HTTP_400_BAD_REQUEST)
        
        if not code:
             return Response({'error': 'Missing authorization code'}, status=status.HTTP_400_BAD_REQUEST)

        client_id = settings.ALPACA_CLIENT_ID
        client_secret = settings.ALPACA_CLIENT_SECRET
        redirect_uri = getattr(settings, 'ALPACA_REDIRECT_URI', f"{settings.FRONTEND_URL}/alpaca/callback")

        if not client_id or not client_secret:
             return Response(
                {'error': 'Alpaca OAuth not configured (missing credentials)'},
                status=status.HTTP_501_NOT_IMPLEMENTED
            )

        # Exchange code for token
        try:
            token_url = "https://api.alpaca.markets/oauth/token"
            data = {
                'grant_type': 'authorization_code',
                'code': code,
                'client_id': client_id,
                'client_secret': client_secret,
                'redirect_uri': redirect_uri,
            }
            
            logger.info(f"Exchanging code for token for user {user.email}")
            response = requests.post(token_url, data=data)
            response.raise_for_status()
            
            token_data = response.json()
            access_token = token_data.get('access_token')
            
            if not access_token:
                logger.error(f"No access token in response: {token_data}")
                return Response({'error': 'Failed to retrieve access token'}, status=status.HTTP_400_BAD_REQUEST)
                
            # Save to user
            user.alpaca_access_token = access_token
            user.alpaca_connected = True
            user.alpaca_connected_at = timezone.now()
            user.alpaca_is_paper = False # OAuth is Live by default usually, but we should check
            # Clear old manual keys if any
            user.alpaca_api_key = '' 
            user.alpaca_secret_key = ''
            
            user.save()
            
            logger.info(f"Successfully connected Alpaca OAuth for {user.email}")
            
            return Response({
                'success': True,
                'message': 'Alpaca account connected via OAuth',
                'connected': True
            })

        except Exception as e:
            logger.error(f"Alpaca OAuth token exchange failed: {e}")
            if hasattr(e, 'response') and e.response:
                logger.error(f"Response: {e.response.text}")
                
            return Response(
                {'error': f'Token exchange failed: {str(e)}'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
