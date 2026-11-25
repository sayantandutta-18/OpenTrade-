# Security

Version: 1.0

## 1. Assets to protect

| Asset | Why it matters |
|---|---|
| User passwords | Reuse on other sites |
| Session cookies | Account takeover |
| Email addresses | Contact and reset flows |
| Saved runs and chat history | Personal learning data |
| API keys (market, news, LLM, email) | Cost and abuse |
| Server | Availability and integrity |

## 2. Threat model

| ID | Threat | Likelihood | Impact | Control | Test |
|---|---|---|---|---|---|
| T-1 | Stolen password database | Medium | High | Argon2id with library defaults, per-password salt | AC-3 |
| T-2 | Online password guessing | High | Medium | 5 failures lock account 15 min; IP rate limit 10/min | AC-4 |
| T-3 | Session theft via cookie | Medium | High | HttpOnly, Secure, SameSite=Lax; token stored as hash; 14-day expiry; logout-all | Auth tests |
| T-4 | Cross-site request forgery | Medium | High | Double-submit CSRF token on state changes | Middleware test |
| T-5 | Account enumeration | High | Low | Same response for forgot password; timing band | AC-8 |
| T-6 | Cross-user data access | Medium | High | Every query filters by user_id; 404 on mismatch | AC-7 |
| T-7 | Cross-site scripting via headlines or chat | High | High | Escape all text; no raw HTML rendering; CSP header | UI test |
| T-8 | Prompt injection via headlines or chat | High | Medium | Headlines and chat text passed as data in a separate field; model told to ignore instructions inside data; actions need confirmation | Guardrail tests |
| T-9 | SQL injection | Low | High | Parameter binding only; repositories.py is the only SQL location | Lint rule and test |
| T-10 | Secrets leaked in logs or repo | Medium | High | Log filter removes known secret fields; .env gitignored; secret scan in CI | CI scan |
| T-11 | LLM cost abuse | High | Medium | Per-user hourly and daily caps; demo mode; answer cache | AC-40 |
| T-12 | Brute-force reset tokens | Low | High | 256-bit random tokens, hashed storage, single use, expiry | AC-5 |
| T-13 | Clickjacking | Low | Low | X-Frame-Options: DENY; frame-ancestors 'none' | Header test |
| T-14 | Insecure transport | Medium | High | HTTPS only in production; HSTS | Deployment check |

## 3. Password rules

- Minimum 12 characters, maximum 128.
- Reject passwords on the bundled list of the 10,001 most common passwords.
- Reject passwords equal to the email or name.
- Hash with argon2-cffi default parameters (Argon2id).
- Never return the hash in any API response.
- No forced periodic rotation. Change only on user request or after a reset.

## 4. Session rules

- Token: 32 random bytes, base64url encoded. Cookie holds the raw token; database holds SHA-256 of it.
- Expiry: 14 days, extended on activity up to 30 days total.
- Logout deletes the session row. Password change or reset deletes all other sessions.
- Cookie flags: HttpOnly, Secure (production), SameSite=Lax, Path=/.

## 5. Tokens for email

- Verification and reset tokens: 32 random bytes; email contains the raw token; database holds SHA-256.
- Verify: 24 hours, single use. Reset: 30 minutes, single use.
- Creating a new token invalidates earlier unused tokens of the same purpose.

## 6. Headers

Set on every response:
- Content-Security-Policy: default-src 'self'; img-src 'self' data: https:; frame-ancestors 'none'
- X-Content-Type-Options: nosniff
- Referrer-Policy: strict-origin-when-cross-origin
- Strict-Transport-Security: max-age=31536000 (production)
- X-Frame-Options: DENY

## 7. Logging and privacy

- Logs never contain: passwords, session or reset tokens, email bodies, chat text, API keys.
- Logs use hashed user IDs in production dashboards.
- IP addresses are stored only as salted hashes (audit_log.ip_hash).
- Analytics are off by default.

## 8. Data handling

- Collect only name, email, password at sign-up.
- Account deletion removes user data within 30 days (immediately in the database; backups expire within 14 days).
- Export of own data (runs and chat history as JSON) is available from the profile page in a later phase.

## 9. Dependency and supply chain

- Pin all versions in the lock file.
- Run pip-audit in CI on every merge.
- Enable Dependabot or equivalent for weekly alerts.
- Review any new dependency in DECISIONS.md.

## 10. Security testing

- Automated tests for every AC marked security (AC-3 to AC-9, AC-37 to AC-41).
- OWASP ZAP baseline scan on staging before each release.
- A manual review of auth flows before v1 launch.

## 11. Reporting

Security issues are reported privately to the project maintainer by email. Do not open public issues for vulnerabilities. Expect acknowledgement within 3 working days.
