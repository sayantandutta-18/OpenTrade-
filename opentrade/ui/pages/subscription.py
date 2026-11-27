"""INR Subscription & Billing Plans page (₹999 / ₹3,999 / ₹7,999)."""

import streamlit as st

from opentrade.services.errors import AppError
from opentrade.services.subscription_service import (
    activate_subscription_db_path,
    cancel_subscription_db_path,
    get_subscription_status_db_path,
    list_plans,
)
from opentrade.ui.state import (
    LOGIN_PAGE,
    TERMS_PAGE,
    USER_KEY,
    get_db_path,
    navigate_to,
)


def render_subscription_page() -> None:
    """Render current subscription status, 3-column INR pricing cards, and billing history."""
    st.title("Subscription & Billing (INR ₹)")
    st.caption(
        "Choose a Pro plan to unlock Live Market Data, AI Analyst & Chat, and unlimited saved runs."
    )

    user = st.session_state.get(USER_KEY)
    user_id = int(user["id"]) if isinstance(user, dict) and "id" in user else None
    db_path = get_db_path()
    status = get_subscription_status_db_path(db_path, user_id)

    if status["is_pro"] and status["active"]:
        active = status["active"]
        st.success(
            f"Active Plan: **{active['plan_name']}** (₹{active['amount_inr']:,}) | "
            f"Expires: `{active['expires_at'][:10]}` | "
            f"Days remaining: **{status['days_remaining']}**"
        )
        if user_id is not None and st.button("Cancel Active Plan", key="sub_cancel_btn"):
            cancel_subscription_db_path(db_path, user_id)
            st.warning("Subscription cancelled.")
            status = get_subscription_status_db_path(db_path, user_id)
    else:
        st.info("Current Plan: **Free / Demo** (upgrade to Pro below).")

    payment_ref = st.text_input(
        "Payment Gateway Reference (Optional Razorpay / Stripe Order ID)",
        key="sub_payment_ref",
        placeholder="Leave blank for Demo / Sandbox Checkout",
    )

    plans = list_plans()
    cols = st.columns(len(plans))
    for idx, plan in enumerate(plans):
        with cols[idx]:
            if plan.badge:
                st.markdown(f"**[{plan.badge}]**")
            st.subheader(plan.name)
            st.markdown(f"### ₹{plan.amount_inr:,}")
            st.caption(f"{plan.duration_days} days • {plan.savings_note}")
            for feat in plan.features:
                st.markdown(f"- {feat}")
            if st.button(f"Activate {plan.name}", key=f"sub_activate_{plan.code}", type="primary"):
                if user_id is None:
                    st.warning("Please log in first to activate a subscription.")
                    navigate_to(LOGIN_PAGE)
                else:
                    try:
                        activated = activate_subscription_db_path(
                            db_path=db_path,
                            user_id=user_id,
                            plan_code=plan.code,
                            payment_ref=payment_ref or None,
                        )
                        st.success(
                            f"Activated **{activated['plan_name']}** "
                            f"(Ref: `{activated['payment_ref']}`)."
                        )
                        status = get_subscription_status_db_path(db_path, user_id)
                    except AppError as exc:
                        st.error(exc.message)

    st.divider()
    st.subheader("Billing History")
    history = status.get("history", [])
    if history:
        st.dataframe(
            [
                {
                    "Plan": h["plan_name"],
                    "Amount (INR)": f"₹{h['amount_inr']:,}",
                    "Status": h["status"],
                    "Started": h["started_at"][:10],
                    "Expires": h["expires_at"][:10],
                    "Payment Ref": h["payment_ref"] or "-",
                }
                for h in history
            ],
            use_container_width=True,
        )
    else:
        st.caption("No subscription transactions yet.")

    st.button(
        "Read Terms & Conditions",
        key="sub_terms_btn",
        on_click=navigate_to,
        args=(TERMS_PAGE,),
    )
