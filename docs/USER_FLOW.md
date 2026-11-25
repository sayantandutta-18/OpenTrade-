# User Flow

Version: 1.0
Each flow lists the steps, the screen shown, and the user's possible outcomes. Screen names match UI_UX_GUIDELINES.md and PROJECT_STRUCTURE.md (ui/pages/).

## Flow 1: First visit (demo mode)

1. Home screen. Hero text, prototype banner, buttons: "Take the tour", "Start in demo mode", "Log in", "Register".
2. Tap "Start in demo mode". Simulator opens with seed 42 preloaded.
3. A tour card explains three steps: explore the map, read correlations, compare companies. Tour can be skipped and reopened from the About menu.
4. Outcome: user is on the simulator. A banner says "Demo mode. Runs are not saved. Create an account to keep them."

## Flow 2: Register and verify

1. Home -> Register.
2. Form: name, email, password, confirm password. Password rules shown under the field (12 characters, not a common password).
3. Privacy note shown above the submit button: "We store your name, email, and password (hashed). Nothing else."
4. Submit. Errors show next to the field (for example "Password must be at least 12 characters").
5. Success screen: "Check your inbox. We sent a link to {email}." Button: "Resend link" (available after 60 seconds).
6. User clicks the email link. Verify screen: "Your email is confirmed." Button: "Continue".
7. Outcome: user is logged in and verified. Saving is enabled.
- Edge: link expired -> screen offers "Send a new link."
- Edge: user never receives email -> check spam is shown; resend is limited to 3 per hour.

## Flow 3: Log in

1. Home -> Log in.
2. Enter email and password. Submit.
3. Success: go to the page the user came from, or Simulator.
4. Failure: "Email or password is incorrect." (same text for both cases).
5. Fifth failure in 10 minutes: "Too many attempts. Try again in 15 minutes." Form disabled with a countdown.
- Edge: unverified account can log in but sees a banner "Verify your email to save runs" with a resend button.

## Flow 4: Forgot password

1. Log in screen -> "Forgot password?".
2. Enter email. Submit.
3. Always shows: "If an account exists for that email, we sent a reset link."
4. User opens the link -> enter new password (same rules) -> success screen.
5. Outcome: all sessions end; user logs in again.
- Edge: expired link -> "This link has expired. Request a new one."

## Flow 5: Explore companies (universe)

1. Universe map screen. Pins are shown. Zoom with buttons or pinch.
2. Tap a pin: company is added to comparison. Counter shows "3 of 6 selected."
3. At six, tapping another pin shows "You can compare up to six companies. Remove one to add another."
4. Correlation overview and compare screens update when the set changes.
5. Search box above the map: type "bank" to see matches; tapping a result adds it.
6. Preset chips: tapping "Global Banks" replaces the set with the preset (confirm if the set already has companies).

## Flow 6: Run an impact experiment

1. Simulator screen. Choose a stock profile (from the comparison set or a single company) and a seed.
2. Inject market order: choose size and side. Tap "Inject." The book view updates.
3. Result card shows: fill price, mid at arrival, slippage in basis points, label SYNTHETIC or CALIBRATED.
4. Tap "Open impact lab." Size list is pre-filled (100, 300, 1,000, 3,000, 10,000). Tap "Run sweep."
5. Progress shows. Result: log-log chart, fitted exponent, confidence interval, one-sentence explanation, provenance label.
6. Tap "Save run." If not logged in: login screen with a message "Log in to save this run." Return to the same screen afterwards.
7. Outcome: run is in Run history with its fingerprint.
- Edge: book too shallow for largest size -> chart shows the largest achievable size and a note explaining why.

## Flow 7: Market data and news

1. Market data panel for selected companies: quote card, 60-day chart, watchlist.
2. Each value has REAL or SIMULATED. Tapping the badge explains the source and time.
3. News panel: toggle Demo / Live. Demo shows bundled headlines with a DEMO tag.
4. Live shows current headlines with source and age. If live fails, panel shows "Live news is unavailable right now. Showing demo headlines." with a DEMO tag.

## Flow 8: Diversification and AI analyst

1. Correlation overview: gauge with verdict and one-line explanation.
2. Concentration vs. count: nominal holdings and effective holdings side by side with a short explanation.
3. AI analyst: choose one of four prompts. Answer shows mode badge (DEMO or LIVE) and time.
4. Live answers are cached for 24 hours for the same inputs. The cache is noted on screen.

## Flow 9: Chat assistant

1. Floating chat button on every screen. Tap to open the panel.
2. Ask a question. Answer streams in. Numbers have citations such as "(run 3f9a..., SYNTHETIC)."
3. Ask for advice: refusal, one sentence, plus an offer to explain the metric instead.
4. Ask to save or delete a run: a confirmation card appears with the action and a "Confirm" and "Cancel" button. Nothing happens until Confirm.
5. Confirmation expires after 10 minutes; expired cards show "This request expired. Ask again."
6. Clear history: confirm dialog, then history is hidden (soft delete).

## Flow 10: Run history

1. Account menu -> Run history. List shows name, date, provenance, fingerprint.
2. Tap a run: details show config, seed, results, and label.
3. Actions: "Re-run with same seed" (creates a new saved run and checks it matches the original fingerprint), "Delete run" (confirm dialog).

## Flow 11: Profile and account deletion

1. Account menu -> Profile: change name, email, password. Email change sends a new verification link.
2. Account menu -> Delete account: enter password. Dialog lists what will be deleted: runs, watchlist, chat history, sessions.
3. Confirm: account is deleted and the user is logged out with a confirmation message.

## Global error paths

| Situation | What the user sees |
|---|---|
| No internet | Demo data, banner "Offline. Showing saved and demo data." |
| Market data source down | SIMULATED badges and note |
| LLM down | Analyst and chat show "The assistant is unavailable. Try again later." Simulator still works |
| Session expired | Login screen with "Please log in again." Returns to the same page after login |
| Server error | "Something went wrong. Reference: {request_id}." No technical details |
