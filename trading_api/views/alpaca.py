"""Alpaca connection views."""

import logging
from django.utils import timezone
from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated

from trading_api.services.alpaca_service import AlpacaService

logger = logging.getLogger(__name__)


class AlpacaConnectView(APIView):
    """Connect user's Alpaca account."""

    permission_classes = [IsAuthenticated]

    def post(self, request):
        """
        Connect Alpaca account with API credentials.

        Required fields:
        - api_key: Alpaca API key
        - secret_key: Alpaca secret key
        - paper: Boolean for paper trading (default True)
        """
        user = request.user
        api_key = request.data.get('api_key', '').strip()
        secret_key = request.data.get('secret_key', '').strip()
        paper = request.data.get('paper', True)

        if not api_key or not secret_key:
            return Response(
                {'error': 'API key and secret key are required'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Test the credentials
        try:
            service = AlpacaService(
                api_key=api_key,
                secret_key=secret_key,
                paper=paper
            )
            result = service.test_connection()

            if not result.get('connected'):
                return Response(
                    {'error': result.get('error', 'Failed to connect to Alpaca')},
                    status=status.HTTP_400_BAD_REQUEST
                )

            # Save credentials (secret key is encrypted)
            user.alpaca_api_key = api_key
            user.alpaca_secret_key = secret_key
            user.alpaca_account_id = result.get('account_id', '')
            user.alpaca_is_paper = paper
            user.alpaca_connected = True
            user.alpaca_connected_at = timezone.now()
            user.alpaca_last_error = ''
            user.save()

            logger.info(f"Alpaca connected for user {user.email} (paper={paper})")

            return Response({
                'success': True,
                'connected': True,
                'account_id': result.get('account_id'),
                'paper': paper,
                'message': 'Alpaca account connected successfully'
            })

        except Exception as e:
            logger.error(f"Failed to connect Alpaca for {user.email}: {e}")
            user.alpaca_last_error = str(e)
            user.save()
            return Response(
                {'error': f'Connection failed: {str(e)}'},
                status=status.HTTP_400_BAD_REQUEST
            )


class AlpacaDisconnectView(APIView):
    """Disconnect user's Alpaca account."""

    permission_classes = [IsAuthenticated]

    def post(self, request):
        """Disconnect Alpaca account and clear credentials."""
        user = request.user

        # Clear credentials
        user.alpaca_api_key = ''
        user.alpaca_secret_key = ''
        user.alpaca_account_id = ''
        user.alpaca_connected = False
        user.alpaca_connected_at = None
        user.alpaca_last_error = ''
        user.save()

        logger.info(f"Alpaca disconnected for user {user.email}")

        return Response({
            'success': True,
            'connected': False,
            'message': 'Alpaca account disconnected'
        })


class AlpacaStatusView(APIView):
    """Get Alpaca connection status."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        """Get current Alpaca connection status and account info."""
        user = request.user

        if not user.alpaca_connected:
            return Response({
                'connected': False,
                'paper': user.alpaca_is_paper,
                'last_error': user.alpaca_last_error,
            })

        # Test connection and get account info
        try:
            service = AlpacaService.from_user(user)
            if not service:
                return Response({
                    'connected': False,
                    'error': 'Missing credentials',
                })

            result = service.test_connection()

            if result.get('connected'):
                account = service.get_account()
                return Response({
                    'connected': True,
                    'paper': user.alpaca_is_paper,
                    'account_id': user.alpaca_account_id,
                    'masked_api_key': user.mask_api_key(),
                    'connected_at': user.alpaca_connected_at.isoformat() if user.alpaca_connected_at else None,
                    'account': {
                        'portfolio_value': account.get('portfolio_value'),
                        'cash': account.get('cash'),
                        'buying_power': account.get('buying_power'),
                        'equity': account.get('equity'),
                        'status': account.get('status'),
                    }
                })
            else:
                return Response({
                    'connected': False,
                    'error': result.get('error'),
                })

        except Exception as e:
            logger.error(f"Failed to get Alpaca status for {user.email}: {e}")
            return Response({
                'connected': False,
                'error': str(e),
            })
