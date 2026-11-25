# API Specification

Version: 1.0
Base path: /api/v1
Format: JSON request and response bodies. Timestamps are ISO 8601 UTC.

## 1. Conventions

### Authentication
- Login sets cookie `ot_session`: HttpOnly, Secure (in production), SameSite=Lax, Path=/.
- Protected endpoints return 401 UNAUTHENTICATED without a valid session.
- Endpoints marked [verified] also require a verified email (403 EMAIL_NOT_VERIFIED otherwise).

### CSRF
- A CSRF token is returned by GET /api/v1/auth/csrf and stored in cookie `ot_csrf`.
- Every POST, PATCH, PUT, DELETE must send header `X-CSRF-Token` equal to the cookie value. Otherwise 403 CSRF_FAILED.

### Errors
Every error response has this shape:
```json
{ "error": { "code": "STRING_CODE", "message": "Plain-language message", "request_id": "uuid" } }
```

### Standard error codes
| Code | HTTP | Meaning |
|---|---|---|
| VALIDATION_FAILED | 422 | Input did not pass rules; includes field list |
| WEAK_PASSWORD | 422 | Password rule failed |
| UNAUTHENTICATED | 401 | No valid session |
| CSRF_FAILED | 403 | Missing or wrong CSRF token |
| EMAIL_NOT_VERIFIED | 403 | Action needs verified email |
| NOT_FOUND | 404 | Missing, or belongs to another user |
| ACCOUNT_LOCKED | 423 | Too many failed logins |
| TOKEN_INVALID | 400 | Reset or verify token invalid, used, or expired |
| COMPARE_LIMIT | 409 | More than six companies in a comparison |
| DAILY_LIMIT | 429 | Chat or analyst daily cap reached |
| RATE_LIMITED | 429 | Short-window rate limit |
| UPSTREAM_UNAVAILABLE | 503 | External source failed and no fallback allowed |
| INTERNAL | 500 | Unexpected error; details in logs only |

## 2. Auth endpoints

| Method | Path | Body | Success | Notes |
|---|---|---|---|---|
| GET | /auth/csrf | none | 200 {token} | Sets ot_csrf cookie |
| POST | /auth/register | {name, email, password} | 201 {message, user: {name, email, verified}} | Sends verification email. Returns 201 with the same body for existing emails. The email owner is notified separately (T0.6). |
| POST | /auth/verify | {token} | 200 {verified: true} | Single use, 24 h |
| POST | /auth/resend-verification | {} | 202 | [auth] Rate limit 3 per hour |
| POST | /auth/login | {email, password} | 200 {user} | Lockout rules apply |
| POST | /auth/logout | {} | 204 | Ends current session |
| POST | /auth/logout-all | {} | 204 | Ends all sessions |
| POST | /auth/password/forgot | {email} | 202 {message} | Same reply for all emails |
| POST | /auth/password/reset | {token, new_password} | 204 | Single use, 30 min; ends all sessions |
| GET | /me | none | 200 {user} | [auth] |
| PATCH | /me | {name?, email?} | 200 {user} | [auth]; email change needs re-verification |
| POST | /me/password | {current_password, new_password} | 204 | [auth]; ends other sessions |
| DELETE | /me | {password} | 204 | [auth]; deletes all user data |

## 3. Runs endpoints

| Method | Path | Body | Success |
|---|---|---|---|
| POST | /runs | {name, seed, profile_id, sizes[], book_depth?} | 201 {run} |
| GET | /runs | query: limit (max 50), cursor | 200 {items[], next_cursor} |
| GET | /runs/{id} | none | 200 {run} |
| DELETE | /runs/{id} | none | 204 |

POST /runs without login is allowed in demo mode, but returns the run without saving (saved: false). With login and verification, it saves and returns saved: true.

A run object:
```json
{
  "id": "uuid",
  "name": "string",
  "seed": 42,
  "fingerprint": "a1b2c3d4e5f6",
  "provenance": "SYNTHETIC",
  "schema_version": 1,
  "created_at": "2026-11-24T17:23:00Z",
  "config": {},
  "results": {
    "impact": [{"size": 100, "slippage_bps": 1.2, "fill_price": 100.01, "mid": 100.00}],
    "fit": {"exponent": 0.51, "ci95": [0.46, 0.56]},
    "event_log_sha256": "string"
  }
}
```

## 4. Market and catalog endpoints

| Method | Path | Success | Notes |
|---|---|---|---|
| GET | /companies?q=&sector= | 200 {items[]} | Max 20 |
| GET | /companies/presets | 200 {presets[]} | Each preset lists symbols |
| GET | /companies/map | 200 {pins[]} | symbol, name, sector, lat, lon, market_cap |
| GET | /companies/{symbol}/profile | 200 {profile, label} | Liquidity profile |
| GET | /companies/{symbol}/radar | 200 {traits, label} | Missing traits are null |
| GET | /market/quote?symbol= | 200 {symbol, price, change, change_pct, open, prev_close, high, low, label, source, as_of} | label is REAL or SIMULATED |
| GET | /market/history?symbol=&days=60 | 200 {symbol, points[], label} | |
| GET | /watchlist | 200 {items[]} | [auth] |
| PUT | /watchlist/{symbol} | 204 | [auth] |
| DELETE | /watchlist/{symbol} | 204 | [auth] |

## 5. News endpoint

| Method | Path | Success |
|---|---|---|
| GET | /news?symbols=AAPL,JPM&mode=demo\|live | 200 {mode, items[]} |

Each item: {title, source, url, published_at, symbols[], label}.

## 6. Analysis endpoints

| Method | Path | Success |
|---|---|---|
| POST | /analysis/correlation | 200 {matrix, verdict, avg_correlation, effective_holdings, nominal_holdings, label} |
| POST | /analysis/impact | 200 {run} (same as POST /runs without saving) |

## 7. Analyst endpoints

| Method | Path | Success |
|---|---|---|
| POST | /analyst/{prompt} | 200 {prompt, mode, text, generated_at, inputs_hash} |

prompt is one of: correlation, geography, radar, risk. Body: {mode: "demo" or "live", symbols[]}.

## 8. Chat endpoints

| Method | Path | Success | Notes |
|---|---|---|---|
| POST | /chat/messages | 200 text/event-stream | Streams tokens; final event contains citations |
| GET | /chat/messages?cursor= | 200 {items[], next_cursor} | [auth] |
| DELETE | /chat/messages | 204 | [auth]; soft delete |
| POST | /chat/actions/{action_id}/confirm | 200 {status: CONFIRMED, result} | [auth, verified] |
| POST | /chat/actions/{action_id}/cancel | 204 | [auth] |

Stream events: `token` {text}, `citation` {run_id or source, label}, `action` {action_id, description}, `done` {}, `error` {code, message}.

## 9. Rate limits

| Scope | Limit | Response |
|---|---|---|
| Auth endpoints per IP | 10 per minute | 429 RATE_LIMITED |
| Forgot password per email | 3 per hour | 202 (no reveal), no email sent |
| Chat per user | 30 messages per hour | 429 RATE_LIMITED |
| Chat per user per day | 50 messages (CHAT_DAILY_LIMIT) | 429 DAILY_LIMIT |
| Analyst live per user per day | 20 calls | 429 DAILY_LIMIT |
| Run creation per user per day | 100 | 429 DAILY_LIMIT |

## 10. Versioning

Breaking changes move to /api/v2. Adding optional fields or endpoints does not change the version.
