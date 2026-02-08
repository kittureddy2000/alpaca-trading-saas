"""Billing views for Stripe integration."""

import logging
from django.conf import settings
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny

from trading_api.services.stripe_service import StripeService
from trading_api.models import UserSubscription

logger = logging.getLogger(__name__)


class SubscriptionView(APIView):
    """Get current subscription status."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        """Get user's subscription status and features."""
        user = request.user

        subscription_info = StripeService.get_subscription_status(user)

        # Add pricing info for upgrade
        subscription_info['prices'] = {
            'pro': {
                'price_id': settings.STRIPE_PRICE_ID_PRO,
                'amount': 2900,  # $29.00
                'currency': 'usd',
                'interval': 'month',
            },
            'enterprise': {
                'price_id': settings.STRIPE_PRICE_ID_ENTERPRISE,
                'amount': 9900,  # $99.00
                'currency': 'usd',
                'interval': 'month',
            },
        }

        return Response(subscription_info)


class CheckoutView(APIView):
    """Create Stripe checkout session."""

    permission_classes = [IsAuthenticated]

    def post(self, request):
        """
        Create a checkout session for subscription upgrade.

        Required fields:
        - tier: 'pro' or 'enterprise'
        """
        user = request.user
        tier = request.data.get('tier', '').lower()

        if tier not in ['pro', 'enterprise']:
            return Response(
                {'error': 'Invalid tier. Must be "pro" or "enterprise"'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Get price ID for tier
        if tier == 'pro':
            price_id = settings.STRIPE_PRICE_ID_PRO
        else:
            price_id = settings.STRIPE_PRICE_ID_ENTERPRISE

        if not price_id:
            return Response(
                {'error': 'Stripe price not configured'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

        # Create checkout session
        frontend_url = settings.FRONTEND_URL
        success_url = f"{frontend_url}/billing?success=true"
        cancel_url = f"{frontend_url}/billing?canceled=true"

        result = StripeService.create_checkout_session(
            user=user,
            price_id=price_id,
            success_url=success_url,
            cancel_url=cancel_url
        )

        if not result:
            return Response(
                {'error': 'Failed to create checkout session'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

        logger.info(f"Checkout session created for user {user.email} (tier={tier})")

        return Response({
            'session_id': result['session_id'],
            'url': result['url'],
        })


class PortalView(APIView):
    """Create Stripe customer portal session."""

    permission_classes = [IsAuthenticated]

    def post(self, request):
        """Create a customer portal session for managing subscription."""
        user = request.user

        frontend_url = settings.FRONTEND_URL
        return_url = f"{frontend_url}/billing"

        portal_url = StripeService.create_portal_session(user, return_url)

        if not portal_url:
            return Response(
                {'error': 'Failed to create portal session'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

        logger.info(f"Portal session created for user {user.email}")

        return Response({
            'url': portal_url,
        })


@method_decorator(csrf_exempt, name='dispatch')
class WebhookView(APIView):
    """Handle Stripe webhooks."""

    permission_classes = [AllowAny]

    def post(self, request):
        """Process Stripe webhook events."""
        payload = request.body
        sig_header = request.META.get('HTTP_STRIPE_SIGNATURE', '')

        if not sig_header:
            return Response(
                {'error': 'Missing signature'},
                status=status.HTTP_400_BAD_REQUEST
            )

        event = StripeService.handle_webhook(payload, sig_header)

        if not event:
            return Response(
                {'error': 'Invalid webhook'},
                status=status.HTTP_400_BAD_REQUEST
            )

        event_type = event['type']
        data = event['data']

        # Process subscription events
        subscription_events = [
            'customer.subscription.created',
            'customer.subscription.updated',
            'customer.subscription.deleted',
            'invoice.payment_succeeded',
            'invoice.payment_failed',
        ]

        if event_type in subscription_events:
            StripeService.process_subscription_event(event_type, data)

        return Response({'received': True})
