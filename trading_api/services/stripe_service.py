"""
Stripe Billing Service.
Handles subscription management, checkout, and webhooks.
"""

import logging
from typing import Optional, Dict, Any
from django.conf import settings
from django.utils import timezone

import stripe

logger = logging.getLogger(__name__)

# Initialize Stripe
stripe.api_key = settings.STRIPE_SECRET_KEY


class StripeService:
    """
    Stripe billing service for subscription management.
    """

    @staticmethod
    def create_customer(user) -> Optional[str]:
        """
        Create a Stripe customer for a user.

        Args:
            user: User model instance

        Returns:
            Stripe customer ID or None
        """
        try:
            customer = stripe.Customer.create(
                email=user.email,
                name=user.name or user.email,
                metadata={
                    'user_id': str(user.id),
                }
            )
            logger.info(f"Created Stripe customer {customer.id} for user {user.email}")
            return customer.id
        except stripe.error.StripeError as e:
            logger.error(f"Failed to create Stripe customer: {e}")
            return None

    @staticmethod
    def get_or_create_customer(user) -> Optional[str]:
        """Get existing Stripe customer or create new one."""
        try:
            subscription = user.subscription
            if subscription.stripe_customer_id:
                return subscription.stripe_customer_id
        except:
            pass

        # Create new customer
        customer_id = StripeService.create_customer(user)
        if customer_id:
            # Update subscription with customer ID
            from trading_api.models import UserSubscription
            subscription, _ = UserSubscription.objects.get_or_create(user=user)
            subscription.stripe_customer_id = customer_id
            subscription.save()

        return customer_id

    @staticmethod
    def create_checkout_session(
        user,
        price_id: str,
        success_url: str,
        cancel_url: str
    ) -> Optional[Dict[str, Any]]:
        """
        Create a Stripe Checkout session for subscription.

        Args:
            user: User model instance
            price_id: Stripe price ID for the subscription
            success_url: URL to redirect on success
            cancel_url: URL to redirect on cancel

        Returns:
            Checkout session info or None
        """
        try:
            customer_id = StripeService.get_or_create_customer(user)
            if not customer_id:
                return None

            session = stripe.checkout.Session.create(
                customer=customer_id,
                payment_method_types=['card'],
                line_items=[{
                    'price': price_id,
                    'quantity': 1,
                }],
                mode='subscription',
                success_url=success_url,
                cancel_url=cancel_url,
                metadata={
                    'user_id': str(user.id),
                }
            )

            logger.info(f"Created checkout session {session.id} for user {user.email}")

            return {
                'session_id': session.id,
                'url': session.url,
            }
        except stripe.error.StripeError as e:
            logger.error(f"Failed to create checkout session: {e}")
            return None

    @staticmethod
    def create_portal_session(user, return_url: str) -> Optional[str]:
        """
        Create a Stripe Customer Portal session.

        Args:
            user: User model instance
            return_url: URL to return to after portal

        Returns:
            Portal session URL or None
        """
        try:
            customer_id = StripeService.get_or_create_customer(user)
            if not customer_id:
                return None

            session = stripe.billing_portal.Session.create(
                customer=customer_id,
                return_url=return_url,
            )

            logger.info(f"Created portal session for user {user.email}")

            return session.url
        except stripe.error.StripeError as e:
            logger.error(f"Failed to create portal session: {e}")
            return None

    @staticmethod
    def cancel_subscription(subscription_id: str) -> bool:
        """
        Cancel a subscription at period end.

        Args:
            subscription_id: Stripe subscription ID

        Returns:
            True if successful
        """
        try:
            stripe.Subscription.modify(
                subscription_id,
                cancel_at_period_end=True
            )
            logger.info(f"Subscription {subscription_id} set to cancel at period end")
            return True
        except stripe.error.StripeError as e:
            logger.error(f"Failed to cancel subscription: {e}")
            return False

    @staticmethod
    def reactivate_subscription(subscription_id: str) -> bool:
        """
        Reactivate a subscription that was set to cancel.

        Args:
            subscription_id: Stripe subscription ID

        Returns:
            True if successful
        """
        try:
            stripe.Subscription.modify(
                subscription_id,
                cancel_at_period_end=False
            )
            logger.info(f"Subscription {subscription_id} reactivated")
            return True
        except stripe.error.StripeError as e:
            logger.error(f"Failed to reactivate subscription: {e}")
            return False

    @staticmethod
    def handle_webhook(payload: bytes, sig_header: str) -> Optional[Dict[str, Any]]:
        """
        Handle Stripe webhook event.

        Args:
            payload: Raw webhook payload
            sig_header: Stripe signature header

        Returns:
            Event data or None
        """
        try:
            event = stripe.Webhook.construct_event(
                payload,
                sig_header,
                settings.STRIPE_WEBHOOK_SECRET
            )

            logger.info(f"Received Stripe webhook: {event.type}")

            return {
                'type': event.type,
                'data': event.data.object,
            }
        except stripe.error.SignatureVerificationError as e:
            logger.error(f"Invalid webhook signature: {e}")
            return None
        except Exception as e:
            logger.error(f"Webhook processing error: {e}")
            return None

    @staticmethod
    def process_subscription_event(event_type: str, data: Dict[str, Any]) -> bool:
        """
        Process subscription-related webhook events.

        Args:
            event_type: Stripe event type
            data: Event data

        Returns:
            True if processed successfully
        """
        from trading_api.models import UserSubscription

        try:
            customer_id = data.get('customer')
            if not customer_id:
                return False

            # Find subscription by customer ID
            try:
                subscription = UserSubscription.objects.get(
                    stripe_customer_id=customer_id
                )
            except UserSubscription.DoesNotExist:
                logger.warning(f"No subscription found for customer {customer_id}")
                return False

            if event_type == 'customer.subscription.created':
                subscription.stripe_subscription_id = data.get('id')
                subscription.stripe_price_id = data.get('items', {}).get('data', [{}])[0].get('price', {}).get('id')
                subscription.status = 'active'
                subscription.tier = StripeService._get_tier_from_price(subscription.stripe_price_id)
                subscription.current_period_start = timezone.datetime.fromtimestamp(
                    data.get('current_period_start', 0),
                    tz=timezone.utc
                )
                subscription.current_period_end = timezone.datetime.fromtimestamp(
                    data.get('current_period_end', 0),
                    tz=timezone.utc
                )
                subscription.save()
                logger.info(f"Subscription created for user {subscription.user.email}")

            elif event_type == 'customer.subscription.updated':
                subscription.status = data.get('status', 'active')
                subscription.cancel_at_period_end = data.get('cancel_at_period_end', False)
                subscription.current_period_end = timezone.datetime.fromtimestamp(
                    data.get('current_period_end', 0),
                    tz=timezone.utc
                )
                subscription.save()
                logger.info(f"Subscription updated for user {subscription.user.email}")

            elif event_type == 'customer.subscription.deleted':
                subscription.status = 'canceled'
                subscription.tier = 'free'
                subscription.stripe_subscription_id = ''
                subscription.save()
                logger.info(f"Subscription canceled for user {subscription.user.email}")

            elif event_type == 'invoice.payment_succeeded':
                subscription.status = 'active'
                subscription.save()
                logger.info(f"Payment succeeded for user {subscription.user.email}")

            elif event_type == 'invoice.payment_failed':
                subscription.status = 'past_due'
                subscription.save()
                logger.warning(f"Payment failed for user {subscription.user.email}")

            return True

        except Exception as e:
            logger.error(f"Error processing subscription event: {e}")
            return False

    @staticmethod
    def _get_tier_from_price(price_id: str) -> str:
        """Map Stripe price ID to subscription tier."""
        if price_id == settings.STRIPE_PRICE_ID_PRO:
            return 'pro'
        elif price_id == settings.STRIPE_PRICE_ID_ENTERPRISE:
            return 'enterprise'
        else:
            return 'free'

    @staticmethod
    def get_subscription_status(user) -> Dict[str, Any]:
        """Get current subscription status for a user."""
        try:
            subscription = user.subscription
            return subscription.get_features()
        except:
            return {
                'tier': 'free',
                'status': 'active',
                'is_active': True,
                'max_watchlist_size': 5,
                'live_trading_enabled': False,
                'api_access_enabled': False,
                'advanced_indicators': False,
                'collar_calculator': False,
                'custom_settings': False,
            }
