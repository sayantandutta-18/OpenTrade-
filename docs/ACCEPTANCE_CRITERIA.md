# Acceptance Criteria

Each criterion is pass or fail. An automated test must exist for every criterion marked [auto]. Criteria marked [manual] are checked by a person before release.

## Accounts (US-1 to US-7)

- **AC-1** [auto] Registering with a valid email and a 12+ character password that is not on the common list creates a user row with email_verified_at = NULL. Response status is 201.
- **AC-2** [auto] Registering with a password under 12 characters, or one on the common list, returns 422 with error code WEAK_PASSWORD and creates no row.
- **AC-3** [auto] The users table contains no column that holds a password in plain text. The stored hash starts with "$argon2id$". A test inserts a known password and verifies the hash differs from it.
- **AC-4** [auto] After 5 failed logins within 10 minutes, a sixth attempt within 15 minutes returns 423 with error code ACCOUNT_LOCKED, even if the password is correct. The lock message does not say whether the password was right.
- **AC-5** [auto] A password reset token works once. A second use returns 400. A token used 31 minutes after creation returns 400.
- **AC-6** [auto] After account deletion, a query for that user_id in every table returns zero rows.
- **AC-7** [auto] With two accounts A and B, a request authenticated as A for B's run ID returns 404 (not 403, so existence is not revealed).
- **AC-8** [auto] Forgot-password for an unknown email returns the same status code, body, and response time band (within 200 ms of a known email) as for a known email.
- **AC-9** [auto] Logging out everywhere ends every session row for the user.
- **AC-10** [manual] The sign-up page shows the privacy note and the password rules before submission.
- **AC-43** [auto] A registration with an email that already exists returns the same status code, body shape, and message as a new registration, and the users row count does not change.

## Simulator (US-8 to US-11)

- **AC-11** [auto] Bids are sorted high to low and asks low to high after any sequence of 1,000 random inserts and cancels (property test).
- **AC-12** [auto] Book has asks at 101 (qty 100) and 102 (qty 200), bid at 99 (qty 150). A market buy of 150 fills 100 at 101 then 50 at 102.
- **AC-13** [auto] At one price level, two resting orders fill in arrival order (FIFO).
- **AC-14** [auto] A FOK order that cannot fill entirely returns no fills and leaves the book unchanged.
- **AC-15** [auto] An IOC order fills what it can and does not rest.
- **AC-16** [auto] Two runs with the same seed and config produce identical trade logs (compare SHA-256 of the log).
- **AC-17** [auto] The best bid is never greater than or equal to the best ask after any operation (no crossed book at rest).

## Impact (US-12 to US-14)

- **AC-18** [auto] The impact sweep produces at least 6 sizes, with the smallest at or below 100 and the largest at or above 10,000 units, or the book's maximum depth if smaller (then the UI says so).
- **AC-19** [auto] The fit reports an exponent and a 95 percent confidence interval. The interval contains the point estimate.
- **AC-20** [auto] For the default profile with seed 42, the exponent is between 0.4 and 0.6.
- **AC-21** [auto] A saved run file contains: config, seed, fingerprint, provenance, schema_version, and results. The fingerprint equals the hash of the config.
- **AC-22** [manual] The impact chart axes are labeled, and a plain-language sentence explains the exponent.

## Stocks and map (US-15 to US-19)

- **AC-23** [auto] Searching "micro" returns companies whose names contain "micro" in any case, up to 20 results.
- **AC-24** [auto] Adding a seventh company to a comparison set is refused with error code COMPARE_LIMIT and the set stays at six.
- **AC-25** [auto] Each map pin has a company name, sector, and market cap in its data.
- **AC-26** [auto] Each preset basket resolves to symbols that exist in the catalog. No preset contains an unknown symbol.
- **AC-27** [manual] The radar shows "missing" for any trait with no input, rather than a zero or an average.

## Market data and news (US-20 to US-23)

- **AC-28** [auto] When the quote source raises an error or returns no data, the quote card shows the badge SIMULATED and no value labeled REAL.
- **AC-29** [auto] Every watchlist row contains exactly one badge, either REAL or SIMULATED.
- **AC-30** [auto] Each headline object includes source name and published_at. The UI shows the relative age ("2h ago").
- **AC-31** [auto] Demo news mode makes zero outbound HTTP calls (verified with a network-blocking fixture).

## Diversification (US-24, US-25)

- **AC-32** [auto] The verdict is "well diversified" when average pairwise correlation is below 0.3, "moderate" from 0.3 to 0.6, and "concentrated" above 0.6. Boundary values are tested.
- **AC-33** [auto] Effective holdings equals 1 / sum(w_i squared) to within 0.01 for given weights.

## AI (US-26 to US-30)

- **AC-34** [auto] With demo mode selected, the analyst makes zero network calls (network-blocking fixture).
- **AC-35** [auto] Every analyst answer object includes mode and generated_at.
- **AC-36** [auto] In live mode, the prompt sent to the LLM contains the computed numbers in a JSON block and an instruction not to add numbers. A test checks that every number in the reply appears in the input JSON; any new number fails the test.
- **AC-37** [auto] A chat reply that contains a number includes a citation to a run ID or data source label.
- **AC-38** [auto] A chat request for "what should I buy" returns the refusal text and no stock recommendation (tested with a fixed set of 20 phrasings).
- **AC-39** [auto] A chat tool action (save, delete, add) returns status PENDING_CONFIRMATION and does not change data until a confirm call is made.
- **AC-40** [auto] A user above the daily chat limit receives 429 with error code DAILY_LIMIT.

## Trust (US-31)

- **AC-41** [auto] A render test walks every page and fails if any numeric value lacks an adjacent provenance badge. Known exceptions (axis tick labels) are listed in an allowlist.
- **AC-42** [auto] The prototype banner text appears on every page in the test suite.
