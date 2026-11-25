# User Stories

Format: As a [role], I want [goal], so that [reason]. Each story lists its acceptance criteria (AC) in ACCEPTANCE_CRITERIA.md and its requirement IDs (FR, NFR) in SRS.md.

## Epic A: Accounts

- **US-1** As a new visitor, I want to register with email and a password, so that my runs are saved to me. (FR-1, FR-2, FR-3)
- **US-2** As a registered user, I want to verify my email, so that my account is confirmed before I save anything. (FR-3)
- **US-3** As a user, I want to log in and stay logged in on my device, so that I can return to my runs. (FR-4)
- **US-4** As a user who locked out after failed logins, I want a clear message and a wait time, so that I know what to do. (FR-5)
- **US-5** As a user who forgot my password, I want to reset it by email, so that I can regain access. (FR-7)
- **US-6** As a user, I want to change my name, email, or password, so that my account stays current. (FR-8)
- **US-7** As a user, I want to delete my account and my data, so that I control what is stored. (FR-9)

## Epic B: Simulator

- **US-8** As a learner, I want to see a live order book with bids and asks, so that I understand how liquidity is arranged. (FR-11, FR-12)
- **US-9** As a learner, I want to inject a market order of a size I choose, so that I can see what it costs me. (FR-22)
- **US-10** As a learner, I want the same seed to give the same result every time, so that I can trust and repeat an experiment. (FR-15, NFR-3)
- **US-11** As a learner, I want to see my own order's place in the queue, so that I understand why limit orders may not fill. (FR-20)

## Epic C: Impact

- **US-12** As a learner, I want a chart of slippage against order size, so that I can see how cost grows. (FR-23)
- **US-13** As a learner, I want the fitted exponent explained in plain language, so that I understand the square-root law. (FR-24)
- **US-14** As a researcher, I want to save an experiment with its settings, so that I can reproduce it. (FR-27)

## Epic D: Companies

- **US-15** As a user, I want to search companies by name, so that I find them quickly. (FR-29)
- **US-16** As a user, I want preset baskets, so that I can compare common groups in one tap. (FR-30)
- **US-17** As a user, I want to pick companies from a world map, so that I can explore by region. (FR-32)
- **US-18** As a user, I want to compare up to six companies at once, so that the comparison stays readable. (FR-31)
- **US-19** As a user, I want a factor radar for my selection, so that I can compare business traits at a glance. (FR-38)

## Epic E: Market data and news

- **US-20** As a user, I want a quote and 60-day chart for each company, so that I see recent behavior. (FR-33, FR-34)
- **US-21** As a user, I want a watchlist where every price shows whether it is real or simulated, so that I never confuse them. (FR-35, FR-36)
- **US-22** As a user, I want headlines for my selected companies with their source and age, so that I can judge what may move prices. (FR-39)
- **US-23** As a user, I want to switch news between demo and live, so that I can use the app offline or with live data. (FR-40)

## Epic F: Diversification

- **US-24** As a user, I want a verdict on whether my picks move together, so that I know if I am diversified. (FR-41, FR-42)
- **US-25** As a user, I want nominal and effective holdings shown side by side, so that I see when ten stocks behave like three. (FR-43)

## Epic G: AI

- **US-26** As a user, I want four fixed analyst questions answered, so that I get quick explanations without writing prompts. (FR-44, FR-46)
- **US-27** As a user, I want to know whether an analyst answer came from demo text or a live model, so that I can judge it. (FR-47)
- **US-28** As a user, I want to ask the chat assistant about my current screen and saved runs, so that I understand the numbers. (FR-48)
- **US-29** As a user, I want the assistant to refuse to tell me what to buy, so that I know it is not advice. (FR-49)
- **US-30** As a user, I want to confirm before the assistant changes anything, so that I stay in control. (FR-50)

## Epic H: Trust

- **US-31** As any user, I want every number labeled REAL, CALIBRATED, or SYNTHETIC, so that I never mistake a simulation for market data. (FR-52, FR-53)
