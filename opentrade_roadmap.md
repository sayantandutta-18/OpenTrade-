# OpenTrade: Phase-by-Phase Roadmap

Each phase lists its steps and a **Done when** check. Build in order.

---

## Phase 0: Foundations

1. Seeded `RunConfig` so every run is reproducible.
2. Provenance labels: REAL, CALIBRATED, SYNTHETIC.
3. Config fingerprint (hash of the settings).
4. Saved results that record config, seed, provenance, and fingerprint.
5. Data loader with labeled fallback to simulation when yfinance fails.
6. Prototype banner and "not investment advice" note.
7. Demo mode (seeded, offline) and live mode (fresh data) defined as settings.

### Accounts (first thing to build)

1. Register with name, email, and password.
2. Password rules: minimum length, and reject common passwords.
3. Passwords stored only as salted hashes (Argon2 or bcrypt), never in plain text.
4. Email verification link before the account can save runs.
5. Login with email and password.
6. Login rate limiting and temporary lockout after repeated failures.
7. Logout, and logout from all devices.
8. Password reset by email, with single-use, expiring links.
9. Sessions stored as secure, HTTP-only cookies with an expiry time.
10. CSRF protection on all forms and state-changing requests.
11. Profile page: change name, email, and password.
12. Delete account, removing the user's saved runs and chat history.
13. Per-user data: saved runs, watchlists, comparison sets, and chat history are private to each user.
14. Store only the personal data needed, and show a short privacy note at sign-up.
15. Demo mode stays available without an account, but nothing is saved.
16. Optional sign-in with Google, added after the core login works.

**Done when:** a new user can register, verify email, log in, reset a forgotten password, and delete the account, and one user cannot see another user's saved data.

---

## Phase 1: Order Book and Matching Engine

1. Two sides, bids and asks, each mapping price to a FIFO queue.
2. Price-time priority: bids high to low, asks low to high.
3. Integer ticks to avoid floating-point price errors.
4. Order types: limit, market, IOC, FOK, cancel.
5. Matching: incoming orders fill against the best opposite price while they cross, and the remainder rests.
6. Lot sizes.
7. Stop orders.
8. Iceberg orders (only part of the size is visible).
9. Self-trade prevention.
10. Queue-position tracking for the user's own order.
11. Unit tests for priority, walking the book, FIFO, FOK/IOC, and cancel.

**Done when:** tests pass and a market order walks the book correctly.

---

## Phase 2: Synthetic Order Flow

1. Poisson arrivals for limit, market, and cancel events.
2. Placement distances follow a power law, not a fixed distribution.
3. Noise traders (random flow).
4. Momentum traders (follow recent price moves).
5. Informed traders (know the likely direction).
6. Tune arrival rates and placement so spread and depth fall in a realistic range.

**Done when:** spread and depth for a chosen stock fall in a realistic range.

---

## Phase 3: Impact Experiment and Simulator

1. Inject a market order of size Q into the book.
2. Measure slippage: average fill price against the mid at arrival.
3. Sweep Q (100, 1,000, 10,000, and beyond).
4. Plot slippage against size on log-log axes.
5. Fit the exponent and check for the square-root law.
6. Separate temporary impact (decays after the trade) from permanent impact (persists).
7. Plot the impact decay curve.
8. Simulator screen: live order book view, depth chart, book heatmap over time, and an inject-order button.
9. Impact lab screen: slippage curve, fitted exponent, confidence intervals.

**Done when:** the fitted exponent is near 0.5 and the decay curve is plotted.

---

## Phase 4: Stock Universe

1. Catalog of about 190 companies with sector, headquarters, and market cap.
2. Each catalog field stores its source and date.
3. Search by company name.
4. Preset baskets: Big Tech, Oil & Gas Giants, Emerging Markets Tech, Global Banks, EV & Auto, Healthcare Leaders.
5. Comparison set of up to six companies.

**Done when:** a user can search, pick a preset, and hold six companies in a comparison.

---

## Phase 5: Universe Map

1. Pins at each company's headquarters.
2. Pin size reflects market cap.
3. Pin color reflects sector.
4. Zoom into regions to see individual pins.
5. Click a pin to add the company to the comparison.
6. Sector legend.
7. Counter showing "N of 6 selected."

**Done when:** clicking pins on the map updates the comparison and the counter.

---

## Phase 6: Stock Profiles and Factor Radar

1. Liquidity profile per stock: tick size, typical spread, depth, arrival rates, volatility.
2. Calibrate profiles from yfinance data where possible.
3. Factor radar with six traits scored 0 to 100: profitability, growth, liquidity, leverage, valuation, momentum.
4. Radar comparison of selected companies, with removable chips.
5. Missing values shown as missing and labeled, never silently filled.

**Done when:** profiles for four to five real tickers appear side by side on the radar.

---

## Phase 7: Market Data Panel

1. Quote card: price, change, open, previous close, high, low.
2. 60-day price history chart.
3. Watchlist with a REAL or SIMULATED badge on every row.

**Done when:** each selected company shows a quote, a history chart, and a badge on every value.

---

## Phase 8: News Feed

1. Headlines tagged to the companies the user has selected.
2. Each headline shows its source and how long ago it was published.
3. Demo mode uses bundled headlines with no network calls.
4. Live mode fetches current headlines.
5. If the news source fails, show demo headlines and label them.

**Done when:** selecting a company filters headlines, and the mode is shown on screen.

---

## Phase 9: News Shocks

1. Scheduled or random shock events.
2. Shocks move the mid price or change order flow intensity for a few minutes.
3. News lab screen: set up shocks.
4. Compare slippage in calm periods against slippage after news, with confidence intervals.

**Done when:** a calm-versus-news slippage comparison is plotted with confidence intervals.

---

## Phase 10: Hawkes Flow

1. Replace Poisson arrivals with a self-exciting Hawkes process.
2. Each event raises the chance of more events shortly after.
3. Compare clustering against Phase 2.

**Done when:** inter-arrival times show the bursty pattern seen in real data.

---

## Phase 11: Endogenous Price

1. The mid price responds to order flow imbalance.
2. Net buying pushes the price up, and net selling pushes it down.
3. Keep the mean-reverting Ornstein–Uhlenbeck fit as a calibration target instead of an input.

**Done when:** net buying measurably pushes the price up.

---

## Phase 12: Market Maker

1. Avellaneda–Stoikov agent quoting both sides.
2. Inventory risk controls how far quotes skew.
3. Measure adverse selection against informed traders.
4. Split P&L into spread capture and adverse selection losses.
5. Show how adverse selection changes the spread.

**Done when:** the maker's P&L splits cleanly into the two components.

---

## Phase 13: Execution Lab

1. Single market order.
2. TWAP (time-weighted).
3. VWAP (volume-weighted).
4. Participation rate.
5. Almgren–Chriss optimal execution.
6. Rank strategies by implementation shortfall across several order sizes.
7. Check whether the square-root law changes the optimal schedule.
8. Execution screen: strategies side by side.

**Done when:** strategies are ranked by shortfall at several order sizes.

---

## Phase 14: Concentration, Correlation, and Diversification

1. Herfindahl index on depth across price levels.
2. Herfindahl index across agent types.
3. Track how concentration relates to slippage in the impact sweep.
4. Correlation overview: sector-by-sector heatmap on a -1 to +1 scale, with a color legend.
5. Diversification gauge with a verdict: well diversified, moderate, or concentrated.
6. Verdict uses average pairwise correlation and effective holdings (inverse Herfindahl of weights).
7. Concentration vs. count view: nominal holdings against effective holdings.
8. Detailed correlation matrix for the selected companies.

**Done when:** high-concentration books show larger impact, and the diversification verdict matches the correlation matrix.

---

## Phase 15: Multi-Asset Cross-Impact

1. Run several order books together.
2. Order flow in one stock moves prices in others (Bouchaud-style cross-impact).
3. Cross-impact screen: how flow in one stock moves the others.
4. Check whether the correlation matrix emerges from the flow itself rather than being imposed.

**Done when:** the simulated correlation matrix forms from flow alone and is shown on screen.

---

## Phase 16: AI Analyst

1. Four prompts: Correlation (sector concentration), Geography (cross-border diversification), Radar (compare selected companies), Risk (concentration vs. count).
2. Demo mode shows pre-generated answers with no API calls.
3. Live mode sends computed numbers to an LLM, which writes prose only.
4. Every answer shows its mode badge.

**Done when:** all four prompts work in both modes, and each answer shows its mode.

---

## Phase 17: Assistant Chat

1. Floating chat button on every screen.
2. Answers questions about the current run only.
3. Uses saved results only, and says so when a number isn't available.

**Done when:** the assistant answers from saved results and refuses to guess missing values.

---

## Phase 18: Validation

1. Load LOBSTER or Binance L2 data.
2. Check fat-tailed returns.
3. Check volatility clustering.
4. Check the spread distribution.
5. Check the signature plot (volatility against sampling interval).
6. Validation screen: pass or fail for each fact.

**Done when:** each stylized fact has a pass or fail result against real data.

---

## Phase 19: Performance

1. Event-driven core with a timestamped priority queue.
2. Latency between sending an order and its arrival at the book.
3. Latency arbitrage study (a faster trader picks off stale quotes).
4. Numba for the hot loop.

**Done when:** a million events run in reasonable time, and latency arbitrage shows a measurable effect.

---

## Phase 20: Interface, Tour, and Run History

1. Mobile-first layout: cards stack vertically, and charts scroll sideways when needed.
2. Home screen: hero section, prototype banner, "Take the tour," Learn, and About.
3. Guided tour with a "New here?" card: explore the map, read the correlation grid, compare companies.
4. Visualization dashboard: depth chart, book heatmap, live book animation.
5. Every chart shows its provenance label.
6. Run history screen: saved runs, settings, and provenance.
7. Replay mode: real historical data through the book, where message-level data exists.

**Done when:** a new user can complete the tour on a phone, and every chart carries its label.

---

## Phase 21: Narrative Summary

1. An LLM writes plain-language findings from the computed numbers.
2. The model receives numbers as data and writes prose only.
3. Every figure in the text is checked against the saved results.

**Done when:** every number in the summary matches the saved results file.

---

## Phase 22: AI Chatbot

Extends Phase 17 into a full assistant.

1. Chat panel available on every screen, with a floating button.
2. Streaming replies, so text appears as it is written.
3. Context from the current screen: selected companies, current run, and its provenance.
4. Answers grounded in saved results and labeled data. It cites which run or data source a number came from.
5. Explain mode: plain-language answers to terms like slippage, spread, and implementation shortfall, with a glossary.
6. Tool use: the chatbot can call app functions such as "run impact sweep" or "show profile for TSLA," with the user confirming any action that changes data.
7. Per-user chat history, saved in the account and deletable.
8. Guardrails: no personalized investment advice, a clear "not investment advice" note, and refusal of requests for trading recommendations on real money.
9. Refuses to invent numbers. If data is missing, it says so and points to the screen that would show it.
10. Rate limits per user and a daily usage cap, to control API cost.
11. Demo mode answers from a bundled set of questions with no API calls.
12. Fallback when the LLM is unavailable: show a short message and the relevant help text instead of an error.
13. Logging of errors and blocked requests, with personal data removed from the logs.
14. Accessibility: keyboard use, screen-reader labels, and a mobile-friendly layout.

**Done when:** a logged-in user can ask about the current run, get an answer that cites its source, trigger a tool action after confirming it, and see that refusals and missing-data notices work.

---

## Cross-Cutting Rules (apply in every phase)

- Login protects saved data only. Demo mode and the simulator work without an account.
- Passwords and session tokens are never written to logs or to saved results.

- Every output carries a REAL, CALIBRATED, or SYNTHETIC label.
- Every run is seeded and saved with its config and fingerprint.
- The engine never imports UI code.
- Missing data is shown as missing, never filled silently.
- Screenshots from Market Risk Radar are a reference for ideas only. OpenTrade uses its own style, copy, and code.
