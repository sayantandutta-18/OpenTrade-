# Software Requirements Specification

Version: 1.0

Requirements are numbered and testable. Each one traces to a user story (US) and an acceptance criterion (AC) where relevant. Priority: M = must, S = should, L = later.

## 1. Accounts

| ID | Requirement | Priority |
|---|---|---|
| FR-1 | A visitor can register with name, email, and password. Email is stored lowercase and must be unique. | M |
| FR-2 | Passwords are at least 12 characters, are not on a bundled list of the 10,001 most common passwords, and are stored only as Argon2id hashes. | M |
| FR-2A | Registration responses are identical whether or not the email already exists. | M |
| FR-3 | After registration, an email verification link is sent. Until verified, the account cannot save runs. Links are single-use and expire after 24 hours. | M |
| FR-4 | Login with email and password creates a session. | M |
| FR-5 | After 5 failed logins within 10 minutes, the account is locked for 15 minutes. The lock message does not reveal whether the password was correct. | M |
| FR-6 | Logout ends the current session. "Log out everywhere" ends all sessions for the user. | M |
| FR-7 | Password reset: the reset form is requested by email. The response is the same whether or not the email exists. Links are single-use and expire after 30 minutes. | M |
| FR-8 | A user can change name, email (requires re-verification), and password (requires current password). | M |
| FR-9 | A user can delete their account after typing their password. All their runs, watchlists, and chat messages are deleted. | M |
| FR-10 | Optional: sign in with Google. | L |

## 2. Simulator and order book

| ID | Requirement | Priority |
|---|---|---|
| FR-11 | The book keeps, for each side, a FIFO queue at each price level. Bids are sorted high to low; asks low to high. | M |
| FR-12 | Prices are integer ticks. Conversion to currency happens only for display. | M |
| FR-13 | Supported orders: limit (GTC), market, IOC, FOK, and cancel. | M |
| FR-14 | Matching is price-time priority. An incoming order fills against the best opposite price while prices cross. Any unfilled GTC remainder rests on the book. | M |
| FR-15 | Every run takes an integer seed. The same seed and config produce identical trade logs. | M |
| FR-16 | Order flow generator: Poisson arrivals for limit, market, and cancel events. | M |
| FR-17 | Placement distance of limit orders follows a power-law distribution, with parameters in the profile. | S |
| FR-18 | Three trader types: noise (random), momentum (follows recent moves), informed (knows the next move direction with a set accuracy). | S |
| FR-19 | Lot sizes, stop orders, iceberg orders, and self-trade prevention. | S |
| FR-20 | The user's own order's queue position is shown. | S |
| FR-21 | Hawkes arrivals replace Poisson arrivals as an option. | L |

## 3. Impact and analysis

| ID | Requirement | Priority |
|---|---|---|
| FR-22 | The user injects a market order of chosen size into the simulated book and sees fill price, mid at arrival, and slippage. | M |
| FR-23 | The impact sweep runs at least 6 sizes, spanning 100 to 10,000 units or the book's range. | M |
| FR-24 | Slippage is fitted to a power law on log-log axes. The exponent is shown with a 95 percent confidence interval. | M |
| FR-25 | Temporary impact (price after the trade decays) and permanent impact (price stays) are measured and shown. | S |
| FR-26 | Concentration of depth is measured with a Herfindahl index. | S |
| FR-27 | Each run is saved with config, seed, fingerprint, provenance, and a result schema version. | M |

## 4. Stocks, data, and news

| ID | Requirement | Priority |
|---|---|---|
| FR-28 | A company catalog with at least 190 companies: symbol, name, sector, headquarters city and country, coordinates, and market cap. Each field stores its source and date. | M |
| FR-29 | Search matches partial company names, case-insensitive, and returns up to 20 results. | M |
| FR-30 | Preset baskets: Big Tech, Oil & Gas Giants, Emerging Markets Tech, Global Banks, EV & Auto, Healthcare Leaders. | M |
| FR-31 | A comparison set holds at most six companies. Adding a seventh shows a message and does nothing else. | M |
| FR-32 | The universe map shows one pin per company, sized by market cap and colored by sector. Clicking a pin adds or removes the company from the comparison set. | S |
| FR-33 | Quote card: price, change, change percent, open, previous close, day high, day low. | M |
| FR-34 | 60-day closing price history chart. | M |
| FR-35 | Watchlist: each row shows symbol, REAL or SIMULATED badge, price, and change. | M |
| FR-36 | If a live source fails or does not cover a symbol, the app shows SIMULATED data with a visible notice. It never shows stale data as current without a timestamp. | M |
| FR-37 | Liquidity profile per company: tick size, typical spread, depth, arrival rates, and volatility. Calibrated where data allows, else SYNTHETIC. | S |
| FR-38 | Factor radar: six traits scored 0 to 100 (profitability, growth, liquidity, leverage, valuation, momentum). Missing inputs are shown as "missing," never filled. | S |
| FR-39 | News feed: headlines tagged to selected companies, each with source name and time since publication. | S |
| FR-40 | Demo and live toggle for news. Demo uses bundled headlines with no network calls. | S |

## 5. Diversification and correlation

| ID | Requirement | Priority |
|---|---|---|
| FR-41 | A correlation matrix for selected companies (or sector averages for the overview) computed from daily returns over the same window. | S |
| FR-42 | Diversification verdict: "well diversified," "moderate," or "concentrated," from average pairwise correlation and effective holdings. | S |
| FR-43 | Effective holdings = 1 / sum of squared weights (inverse Herfindahl). Shown next to nominal holdings. | S |

## 6. AI features

| ID | Requirement | Priority |
|---|---|---|
| FR-44 | The AI analyst offers four fixed prompts: Correlation, Geography, Radar, Risk. | S |
| FR-45 | Demo mode returns bundled answers with no network call. | S |
| FR-46 | Live mode sends the computed numbers as structured data to the LLM and returns its prose. The LLM is told not to introduce numbers. | S |
| FR-47 | Every analyst answer shows its mode (DEMO or LIVE) and the time it was produced. | S |
| FR-48 | The chat assistant answers questions about the user's current screen and saved runs only. It cites the run ID or data source for any number. | S |
| FR-49 | The chat assistant refuses personalized investment advice and says so in one sentence. | S |
| FR-50 | Any chat action that changes data (save run, delete run, add company) requires an explicit confirm click. | S |
| FR-51 | Chat history is per user, can be cleared, and is deleted with the account. | S |

## 7. Trust and labels

| ID | Requirement | Priority |
|---|---|---|
| FR-52 | Every number, chart, and generated sentence carries a provenance label: REAL, CALIBRATED, or SYNTHETIC. Demo and live content also carry DEMO or LIVE. | M |
| FR-53 | A prototype banner ("Prototype. Not investment advice.") appears on every page. | M |

## 8. Non-functional requirements

| ID | Category | Requirement |
|---|---|---|
| NFR-1 | Performance | An impact sweep of 20 sizes completes in under 30 seconds on a 4-core laptop. A single order injection completes in under 10 ms. |
| NFR-2 | Performance | Pages render first content in under 3 seconds on a mid-range phone over 4G. |
| NFR-3 | Reproducibility | Same seed, config, and code version give byte-identical saved results. |
| NFR-4 | Security | Passwords, session tokens, reset tokens, and API keys never appear in logs, saved results, or error messages. See SECURITY.md. |
| NFR-5 | Privacy | Only name, email, and password are collected at sign-up. |
| NFR-6 | Accessibility | Core screens meet WCAG 2.1 AA. See UI_UX_GUIDELINES.md. |
| NFR-7 | Responsiveness | Usable from 360 px wide up. No horizontal page scroll. |
| NFR-8 | Availability | Demo mode and the simulator work with no internet connection. |
| NFR-9 | Cost control | LLM calls are capped per user per day. Demo mode makes zero LLM calls. |
| NFR-10 | Maintainability | Engine has no UI imports. Test coverage 85 percent for the engine. |
| NFR-11 | Portability | Runs on Windows, macOS, and Linux with Python 3.11 or later. |

## 9. Constraints

- Python 3.11 or later for all server and engine code.
- SQLite for storage in v1.
- No real money, no broker connections.
- External APIs are optional. The app must run with none of them configured.
