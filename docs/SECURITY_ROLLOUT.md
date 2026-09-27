# Security rollout — September 2026

Production uses Vercel and persistent PostgreSQL. Preview shares that database:
never run destructive tests or place synthetic orders there. Run tests and migration
rehearsals on an isolated PostgreSQL database, with a verified encrypted backup.

## Configuration

- Django is pinned to 5.2.17.
- `SECRET_KEY_NEXT` is the new random signing key. Keep the existing `SECRET_KEY`
  during the transition; set `SECRET_KEY_PREVIOUS_VALID_UNTIL` to a Unix timestamp
  13 hours after deployment (sessions last 12 hours). Existing sessions and carts
  can be verified with the old key, while new cookies use the new key. The deadline
  is checked when fallbacks are used, including in warm processes. After the transition, replace `SECRET_KEY`
  with the new value, remove the two transition variables, and redeploy for
  configuration cleanup. The old key expires even without that cleanup. Never log or commit either key.
- `FERNET_KEY` must remain unchanged: it decrypts existing customer records.
  `PII_HASH_KEY` is a separate, stable random secret (32+ characters) for exact
  CPF/phone lookup indexes. Changing it without rebuilding indexes breaks lookup.
- Protect backups and keys separately, outside Git. Vercel redacts secrets on
  export: `[SENSITIVE]` is not the actual value and cannot validate secret strength.

## Deployment order

1. Make a full PostgreSQL backup, encrypt it, and restore it into an isolated local
   PostgreSQL database. Rehearse forward and reverse data migrations there.
2. Configure `PII_HASH_KEY`, `SECRET_KEY_NEXT`, and the transition deadline on Vercel.
3. Apply only additive/compatible migrations against production, with a short
   PostgreSQL lock timeout: `migrate accounts 0006`, `migrate core 0008`,
   `migrate orders 0008`. Keep the existing production application running.
4. Build a production deployment with `vercel deploy --prod --skip-domain`.
   Validate health, catalog, product images, login, cart, security headers and logs.
5. Promote the verified deployment, then run `migrate accounts 0007` and
   `migrate orders 0009`. These row-locking migrations encrypt phone snapshots and
   clear legacy plaintext identity columns. New code reads legacy values during
   this transition and writes only encrypted identities plus HMAC indexes.
6. Verify raw legacy columns are empty, ciphertext actually decrypts, lookup
   indexes match, and checkout/payment/report tests pass. No live payment is
   necessary for these tests; do not fabricate a payment in production.

## Rollback

Before plaintext scrubbing, the old application can still read the schema.
After scrubbing, **do not simply promote the old deployment**. First coordinate
customer writes (maintenance window if necessary), reverse `orders` to `0008` and
`accounts` to `0006` using the same Fernet key, verify restored values, and only
then restore the old application. Reverting migrations restores plaintext and is
an emergency action, not the normal operating state. Keep additive columns.

## Controls and limits

- CPF and customer phone fields, including order/preorder snapshots, use Fernet
  authenticated encryption at rest. Exact searches use keyed HMAC-SHA256; partial
  CPF/phone search is intentionally unavailable. Authorized application views
  decrypt these fields; encryption is not a substitute for access control.
- Rate-limit counters live in PostgreSQL and use an atomic UPSERT across serverless
  workers. Login: 5 attempts/5 minutes. General traffic: 240 requests/minute/IP.
  Webhooks, health, static/media and authenticated cron are exempt. IP identifiers
  are HMAC-hashed; on Vercel only its trusted client-IP header is used. The existing
  daily exchange-rate cron cleans expired buckets. Database failure is fail-open
  for throttling to avoid adding a checkout outage; health reports DB failures.
- CSP blocks plugins, foreign base URLs and framing, and restricts external sources.
  `unsafe-inline` remains for existing scripts/styles/handlers. This is a compatible
  baseline, **not a strict nonce-based CSP**; tightening it needs a frontend refactor.
- `/health/` returns a generic status and checks DB connectivity, without exposing
  configuration or identities. Safe structured logs cover 5xx and slow requests.
- Optional `SENTRY_DSN` enables scrubbed error reporting. Request bodies, users,
  breadcrumbs, exception values and local variables are removed; tracing is off.
  Without a DSN, Sentry does not send events. Never claim alerts are delivered
  until the account's destination and feature entitlement have been verified.
- A Vercel project error-anomaly rule can notify account owners. It detects spikes,
  not every individual error; rule creation is not an end-to-end delivery test.
  As of this rollout the team is on Hobby; Vercel's documentation requires Pro or
  Enterprise with Observability Plus for alerts. The rule was accepted by the API,
  but notification delivery is not established. No paid plan was enabled. Connect
  an approved Sentry project or another external monitor to complete alert delivery.

No security score, certification, zero-risk guarantee or uninterrupted-availability
guarantee is implied by this hardening. Keep dependencies and keys maintained.
