# Product Requirements Document

Version: 1.0
Status: Ready for build

## 1. Goals

1. Show how order size affects execution price, using a reproducible simulated order book.
2. Make every result traceable to its data source, settings, and seed.
3. Let users compare liquidity, diversification, and news exposure across real listed companies.
4. Give a clear, honest answer to "how much will this trade cost?" for simulated markets.

## 2. Users

| Persona | Need | Main screens |
|---|---|---|
| Learner (student) | Understand impact and the square-root law | Simulator, Impact lab, Chatbot |
| Curious investor | See how liquidity and diversification differ across stocks | Universe map, Compare, Correlation |
| Researcher or developer | Reproduce and extend experiments | Run history, Execution lab, Validation |

## 3. Feature list by priority

### Must have (v1)
- F1 Accounts: register, verify email, log in, reset password, delete account.
- F2 Seeded order book simulator with limit, market, IOC, FOK, and cancel orders.
- F3 Order injection and slippage display.
- F4 Impact sweep across order sizes with a log-log fit and confidence interval.
- F5 Provenance labels on every number, chart, and sentence.
- F6 Demo mode that works offline with no API calls.
- F7 Company catalog with search and six-company comparison limit.
- F8 Universe map with pins by headquarters.
- F9 Quote, 60-day history, and watchlist with REAL or SIMULATED badges.
- F10 Saved runs with config, seed, fingerprint, and provenance.
- F11 Prototype banner and "not investment advice" note on every page.

### Should have (v1 if time allows)
- F12 Factor radar for up to six companies.
- F13 Correlation overview and diversification verdict.
- F14 News feed with demo and live modes.
- F15 AI analyst with four fixed prompts (demo and live).
- F16 Basic assistant chat.

### Later (v2 and beyond)
- F17 News shock lab.
- F18 Hawkes order flow.
- F19 Endogenous price and market maker.
- F20 Execution lab.
- F21 Multi-asset cross-impact.
- F22 Validation against LOBSTER or Binance data.
- F23 Full chatbot with tool actions.
- F24 Narrative summary.

## 4. Out of scope

- Real order routing, brokerage connections, or any real money.
- Options, futures, crypto derivatives, and FX.
- Public sharing of runs or social features.
- Personalized financial advice.
- Mobile native apps (the web app must work on phones; native apps are not planned).

## 5. Success measures

| Measure | Target |
|---|---|
| Time from home screen to first impact result | Under 5 minutes for a new user |
| Default-profile impact exponent | Between 0.4 and 0.6 |
| Displayed numbers with a provenance label | 100 percent (tested) |
| Reproducibility | Same seed and config give identical output (tested) |
| Account security | Zero plain-text passwords; all auth tests pass |

## 6. Risks and mitigations

| Risk | Mitigation |
|---|---|
| Users read simulation as prediction | Labels, banner, "not investment advice," tour explains synthetic data |
| Free data sources are rate-limited or stop working | Labeled fallback, caching, demo mode |
| LLM cost grows with users | Per-user limits, daily caps, demo mode, cache of analyst answers |
| LLM invents numbers | Numbers come from computed results only; citations required; tests check |
| Account data leaks between users | Every query filtered by user; cross-user tests |

## 7. Assumptions

- Users have a modern browser and a phone or laptop with internet access.
- yfinance remains usable for daily quotes and history for v1.
- A single SQLite database handles v1 usage (up to a few hundred active accounts).
