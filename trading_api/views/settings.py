"""User settings views."""

import logging
from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated

from trading_api.models import UserSettings

logger = logging.getLogger(__name__)


class UserSettingsView(APIView):
    """User trading settings management."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        """Get user's trading settings."""
        user = request.user

        # Check if user can customize settings (Pro+)
        try:
            can_customize = user.subscription.custom_settings
        except:
            can_customize = False

        # Get or create settings
        settings_obj = UserSettings.get_or_create_for_user(user)

        return Response({
            'can_customize': can_customize,
            'settings': {
                'strategy': settings_obj.strategy,
                'analysis_interval_minutes': settings_obj.analysis_interval_minutes,
                'max_position_pct': settings_obj.max_position_pct,
                'max_daily_loss_pct': settings_obj.max_daily_loss_pct,
                'min_confidence': settings_obj.min_confidence,
                'stop_loss_pct': settings_obj.stop_loss_pct,
                'take_profit_pct': settings_obj.take_profit_pct,
                'email_daily_summary': settings_obj.email_daily_summary,
                'email_trade_alerts': settings_obj.email_trade_alerts,
                'email_weekly_report': settings_obj.email_weekly_report,
            }
        })

    def put(self, request):
        """Update user's trading settings."""
        user = request.user

        # Check if user can customize settings (Pro+)
        try:
            can_customize = user.subscription.custom_settings
        except:
            can_customize = False

        if not can_customize:
            return Response(
                {'error': 'Custom settings require Pro subscription'},
                status=status.HTTP_403_FORBIDDEN
            )

        settings_obj = UserSettings.get_or_create_for_user(user)

        # Update allowed fields
        allowed_fields = [
            'strategy',
            'analysis_interval_minutes',
            'max_position_pct',
            'max_daily_loss_pct',
            'min_confidence',
            'stop_loss_pct',
            'take_profit_pct',
            'email_daily_summary',
            'email_trade_alerts',
            'email_weekly_report',
        ]

        for field in allowed_fields:
            if field in request.data:
                value = request.data[field]

                # Validate strategy
                if field == 'strategy' and value not in ['momentum', 'mean_reversion', 'contrarian', 'balanced']:
                    continue

                # Validate percentages (0-1 range)
                if field in ['max_position_pct', 'max_daily_loss_pct', 'min_confidence', 'stop_loss_pct', 'take_profit_pct']:
                    try:
                        value = float(value)
                        if not 0 <= value <= 1:
                            continue
                    except (ValueError, TypeError):
                        continue

                # Validate interval
                if field == 'analysis_interval_minutes':
                    try:
                        value = int(value)
                        if not 1 <= value <= 1440:  # 1 min to 24 hours
                            continue
                    except (ValueError, TypeError):
                        continue

                setattr(settings_obj, field, value)

        settings_obj.save()

        logger.info(f"Settings updated for user {user.email}")

        return Response({
            'success': True,
            'settings': {
                'strategy': settings_obj.strategy,
                'analysis_interval_minutes': settings_obj.analysis_interval_minutes,
                'max_position_pct': settings_obj.max_position_pct,
                'max_daily_loss_pct': settings_obj.max_daily_loss_pct,
                'min_confidence': settings_obj.min_confidence,
                'stop_loss_pct': settings_obj.stop_loss_pct,
                'take_profit_pct': settings_obj.take_profit_pct,
                'email_daily_summary': settings_obj.email_daily_summary,
                'email_trade_alerts': settings_obj.email_trade_alerts,
                'email_weekly_report': settings_obj.email_weekly_report,
            }
        })
