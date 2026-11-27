"""Terms & Conditions and Educational Simulation Disclaimer page."""

import streamlit as st

from opentrade.ui.state import HOME_PAGE, REGISTER_PAGE, SUBSCRIPTION_PAGE, navigate_to


def render_terms_page() -> None:
    """Render structured Terms & Conditions tailored to OpenTrade."""
    st.title("Terms & Conditions")
    st.caption("Effective for all OpenTrade accounts, simulations, and INR Pro subscriptions.")

    st.markdown("""
### 1. Educational & Research Use Only
OpenTrade is a quantitative market microstructure workbench built strictly for educational,
academic, and software engineering research.

### 2. Not Financial or Investment Advice
Nothing displayed in OpenTrade—including order-book simulations, market-impact curves,
factor radar scores, news comparisons, or AI Analyst / Chat responses—constitutes
investment, legal, or tax advice, nor a recommendation to buy or sell any security.

### 3. Synthetic vs. Live Data & AI Disclaimers
- **SYNTHETIC / DEMO** outputs are generated deterministically by internal models and fixtures.
- **CALIBRATED** parameters are fitted to historical market regimes and may differ from live data.
- **REAL / LIVE** market data and news feeds are provided as-is from external providers.
- AI Analyst and Assistant outputs are strictly grounded in displayed simulation metrics and refuse
  personalized trade recommendations.

### 4. Subscription & Refund Terms (INR ₹)
- Paid Pro plans (**Pro Monthly ₹999 / 30 days**, **Pro 6-Month ₹3,999 / 180 days**, and
  **Pro Annual ₹7,999 / 365 days**) unlock Live Market Data, AI Analyst & Chat, and unlimited
  saved simulation runs.
- Upgrading immediately activates the new plan and supersedes any prior active plan.
- Subscriptions may be cancelled at any time; cancellation stops future renewals and ends active
  Pro access immediately unless otherwise required by applicable law.

### 5. Account Security
You are responsible for safeguarding your credentials and session. OpenTrade enforces Argon2id
password hashing, brute-force lockouts, and per-user data isolation.

### 6. Limitation of Liability
To the maximum extent permitted by law, OpenTrade and its contributors are not liable for any
direct, indirect, incidental, or consequential losses arising from use of this prototype.
""")

    col1, col2, col3 = st.columns(3)
    with col1:
        st.button("Back to Home", key="terms_home_btn", on_click=navigate_to, args=(HOME_PAGE,))
    with col2:
        st.button(
            "View Pro Plans",
            key="terms_sub_btn",
            on_click=navigate_to,
            args=(SUBSCRIPTION_PAGE,),
        )
    with col3:
        st.button(
            "Register",
            key="terms_reg_btn",
            on_click=navigate_to,
            args=(REGISTER_PAGE,),
        )
