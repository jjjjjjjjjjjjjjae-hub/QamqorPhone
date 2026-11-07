# QamqorPhone Worker workflow — implementation draft

This branch contains a reviewed backend implementation draft. It is NOT deployed.

## Existing bindings reused
- CHAT_ID
- TELEGRAM_BOT_TOKEN
- TELEGRAM_CLIENT_SECRET
- QAMQOR_PHONE_DATA

No secret values are stored in source.

## Routes
- GET /health
- GET /auth/url
- POST /auth/exchange
- POST /request
- POST /estimate?id=QP-...
- POST /estimate/decision
- POST /telegram/webhook

## Telegram bot setup required before deployment
Configure the existing bot webhook to:
https://qamqorphone-auth.<workers-subdomain>.workers.dev/telegram/webhook

Suppliers start the bot with /start. They can quote with:
 /price QP-YYYYMMDD-XXXXXXXX Part_name 8000

Admin commands in the configured CHAT_ID:
 /approve QP-YYYYMMDD-XXXXXXXX PART DELIVERY LABOR
 /cancel QP-YYYYMMDD-XXXXXXXX

The customer estimate is hidden until /approve succeeds.

## Important implementation boundary
The current frontend still submits the legacy payload shape. This draft preserves that shape and extracts the WhatsApp number and map link from the existing details field. The next frontend change must add the customer estimate view and accept/decline controls.

## Before production
1. Review webhook configuration and set Telegram webhook.
2. Confirm supplier index population (KV key suppliers:index, JSON array of Telegram chat IDs) or add an admin supplier enrollment workflow.
3. Add a cryptographically strong client-facing estimate access token before exposing public estimate URLs. The current estimate route is an ID lookup and must not be considered private enough for production.
4. Add rate limiting / abuse controls and idempotency.
5. Run integration tests with a test Telegram chat before production deployment.
