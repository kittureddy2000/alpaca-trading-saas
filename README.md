# Alpaca Trading SaaS

AI-powered stock trading platform using Alpaca API, designed as a multi-tenant SaaS with Stripe billing.

## Features

- **Multi-Tenant Architecture**: Each user connects their own Alpaca account
- **Subscription Tiers**: Free, Pro ($29/mo), Enterprise ($99/mo)
- **AI-Powered Trading**: Google Gemini for market analysis and trade recommendations
- **Technical Indicators**: RSI, MACD, SMA, EMA, Bollinger Bands, VWAP, ATR
- **Options Calculator**: Option chain viewer and collar strategy calculator
- **Real-time Dashboard**: Portfolio tracking, positions, trade history

## Subscription Tiers

| Feature | Free | Pro | Enterprise |
|---------|------|-----|------------|
| Paper Trading | ✅ | ✅ | ✅ |
| Live Trading | ❌ | ✅ | ✅ |
| Watchlist Size | 5 | Unlimited | Unlimited |
| Basic Indicators | ✅ | ✅ | ✅ |
| Advanced Indicators | ❌ | ✅ | ✅ |
| Collar Calculator | ❌ | ✅ | ✅ |
| Custom Settings | ❌ | ✅ | ✅ |
| API Access | ❌ | ❌ | ✅ |

## Quick Start

### Prerequisites

- Python 3.11+
- Node.js 18+
- PostgreSQL (or SQLite for development)

### Local Development

1. **Clone and setup backend:**
```bash
cd alpaca-trading-saas
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
```

2. **Configure environment:**
```bash
cp .env.example .env
# Edit .env with your API keys
```

3. **Run migrations:**
```bash
python manage.py migrate
```

4. **Start backend:**
```bash
python manage.py runserver 8000
```

5. **Setup frontend:**
```bash
cd dashboard
npm install
npm run dev
```

### Required API Keys

| Service | Purpose | Get it from |
|---------|---------|-------------|
| Alpaca | Trading API | https://app.alpaca.markets/signup |
| Stripe | Billing | https://dashboard.stripe.com/register |
| Google | OAuth | https://console.cloud.google.com |
| Gemini | AI Analysis | https://aistudio.google.com/apikey |

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                     React Dashboard                          │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                   Django REST API                            │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐         │
│  │   Auth      │  │  Portfolio  │  │   Billing   │         │
│  │  (JWT)      │  │   Trades    │  │  (Stripe)   │         │
│  └─────────────┘  └─────────────┘  └─────────────┘         │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│              Per-User Alpaca Connection                      │
│                                                             │
│  User A ─→ Alpaca API ─→ User A's Account                  │
│  User B ─→ Alpaca API ─→ User B's Account                  │
│  User C ─→ Alpaca API ─→ User C's Account                  │
└─────────────────────────────────────────────────────────────┘
```

## API Endpoints

### Authentication
- `POST /auth/register` - Create account
- `POST /auth/login` - Login
- `GET /auth/me` - Current user
- `GET /auth/google` - Google OAuth

### Portfolio
- `GET /api/portfolio` - Portfolio overview
- `GET /api/positions` - Current positions
- `GET /api/trades` - Trade history
- `GET /api/watchlist` - Watchlist with quotes
- `POST /api/watchlist` - Add to watchlist
- `DELETE /api/watchlist` - Remove from watchlist

### Alpaca Connection
- `POST /api/alpaca/connect` - Connect Alpaca account
- `POST /api/alpaca/disconnect` - Disconnect
- `GET /api/alpaca/status` - Connection status

### Settings & Billing
- `GET /api/settings` - User settings
- `PUT /api/settings` - Update settings
- `GET /api/subscription` - Subscription info
- `POST /api/subscription/checkout` - Stripe checkout
- `POST /api/subscription/portal` - Manage subscription

### Options
- `GET /api/option-chain` - Option chain data
- `GET /api/collar-strategy` - Collar calculator

## Deployment

### Cloud Run

```bash
gcloud run deploy alpaca-trading-api \
  --source . \
  --region us-west1 \
  --allow-unauthenticated \
  --set-env-vars="DJANGO_SECRET_KEY=...,STRIPE_SECRET_KEY=..."
```

### Environment Variables

Set these in Cloud Run or your deployment platform:

```
DJANGO_SECRET_KEY=...
DB_NAME=...
DB_USER=...
DB_PASSWORD=...
DB_HOST=...
STRIPE_SECRET_KEY=...
STRIPE_WEBHOOK_SECRET=...
STRIPE_PRICE_ID_PRO=...
STRIPE_PRICE_ID_ENTERPRISE=...
GOOGLE_CLIENT_ID=...
GOOGLE_CLIENT_SECRET=...
GEMINI_API_KEY=...
ENCRYPTION_KEY=...
FRONTEND_URL=https://your-frontend.com
```

## Security

- API secrets are encrypted using Fernet before storage
- JWT tokens for stateless authentication
- CORS configured for specific origins only
- Stripe webhooks verified with signatures

## License

MIT
