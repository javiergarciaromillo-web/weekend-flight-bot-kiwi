# weekend-flight-bot-kiwi (RapidAPI flights-scraper-real-time)

Sends a daily email with round-trip direct flight prices for:
- AMS ↔ BCN
- RTM ↔ BCN

Patterns:
- THU→SUN, THU→MON, FRI→SUN, FRI→MON

Constraints:
- Direct only (stops=0)
- Departure time window 16:00–23:00 (local times in response)
- Currency shown in EUR (uses price.priceEur.amount when available)

## Quota strategy (free plan)
The free plan has 120 requests/month.

Per full refresh:
- 3 weeks × 4 patterns × 2 origins = 24 requests

We run daily emails, but API refresh happens every 6 days by default:
- 24 * 5 = 120 requests/month

## Local run

1) Create and fill `.env` (see `.env.example`)
2) Export env vars (example for bash):
```bash
set -a
source .env
set +a
python -m src.main
