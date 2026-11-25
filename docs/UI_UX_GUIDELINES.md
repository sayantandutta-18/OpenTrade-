# UI and UX Guidelines

Version: 1.0
Applies to every screen. Streamlit is the v1 front end, so these rules are written so they can be met with Streamlit containers, columns, tabs, and custom CSS.

## 1. Principles

1. Label everything. Every number, chart, and generated sentence carries a provenance badge: REAL, CALIBRATED, SYNTHETIC, plus DEMO or LIVE where relevant.
2. Mobile first. Design for 360 px width, then widen. Test at 360, 768, and 1280 px.
3. Explain once, in place. Each term gets a one-line explanation the first time it appears, with a "?" tooltip.
4. Never hide missing data. Write "not available" and the reason.
5. Calm by default. One main action per screen. Secondary actions are plain text links.

## 2. Layout

- Max content width 720 px on desktop; full width on mobile.
- Vertical stack of cards on mobile. Two columns only from 768 px up.
- Each card: a small uppercase section label (for example "03 COMPARE COMPANIES"), a title, a one-line description, then content.
- Charts sit inside a horizontally scrollable container (overflow-x: auto). The page itself never scrolls sideways.
- Sticky top bar: app name, current mode badge, account button.
- Chat button fixed bottom right, 56 px, clear of content and the phone's gesture bar (add 24 px safe-area padding).
- Prototype banner at the top of every page, one line, muted color: "Prototype. Not investment advice."

## 3. Visual style

| Token | Dark theme (default) | Light theme |
|---|---|---|
| Background | #0B0F17 | #F7F8FA |
| Card | #111827 | #FFFFFF |
| Border | #1F2937 | #E5E7EB |
| Text primary | #E5E7EB | #111827 |
| Text secondary | #9CA3AF | #4B5563 |
| Accent (actions) | #E8A33D | #B45309 |
| Positive | #34D399 | #047857 |
| Negative | #F87171 | #B91C1C |
| Info (labels) | #5EEAD4 | #0F766E |

Sector colors (fixed, used on map and legends): Tech #E8A33D, Financials #2DD4BF, Auto #60A5FA, Energy #F87171, Healthcare #A78BFA, Consumer #4ADE80, Industrials #94A3B8, Telecom #F472B6, Retail #A3E635, Materials #C08457.

Typography:
- Numbers and labels: monospace (JetBrains Mono or system monospace), 14 px body, 12 px labels.
- Body text: system sans-serif, 16 px, line height 1.5.
- Headings: monospace, bold. H1 28 px, H2 22 px, H3 18 px on mobile.

Spacing: 8 px grid. Card padding 16 px mobile, 24 px desktop.

## 4. Components

| Component | Behavior |
|---|---|
| Provenance badge | Outlined tag, uppercase text, color from Info token. Text always present; color is never the only signal |
| Mode toggle | Two-segment control: DEMO / LIVE. Selected segment filled with accent |
| Stat card | Label above, value large, change below with arrow and sign |
| Limit chip | "N of 6 selected" with a removable chip per company |
| Confirmation dialog | Title, what will happen, Confirm (primary), Cancel (secondary). Used for delete and chat actions |
| Empty state | One sentence explaining why it is empty and one next action |
| Toast | Bottom, 4 seconds, for success only. Errors stay on screen until fixed |

Gains and losses always show an arrow (▲ or ▼) and a sign (+ or −), so color is never the only signal.

## 5. Accessibility

- WCAG 2.1 AA: text contrast at least 4.5:1, large text at least 3:1, non-text UI at least 3:1.
- Every control reachable by keyboard in logical order. Visible focus ring: 2 px accent outline.
- Touch targets at least 44 by 44 px.
- Charts include a text summary below (one sentence) and a data table toggle.
- Images and icons have alt text or aria-labels. Decorative icons are hidden from screen readers.
- No information conveyed by color alone.
- Respect the reduced-motion setting: no animated transitions when it is on.

## 6. Forms

- Labels above fields, never placeholder-only.
- Errors appear under the field in plain language and are announced to screen readers.
- Password field has a show/hide toggle and shows the rules before typing.
- Submit button disabled only while submitting; never disabled for validation alone.

## 7. Copy rules

- Button labels are verbs: "Inject order", "Run sweep", "Save run", "Confirm delete".
- Errors say what happened and what to do next. Example: "That email is already registered. Log in instead?"
- No jargon without a tooltip. "Slippage" gets: "Extra cost compared with the mid price, in basis points."
- Never say "guaranteed," "will rise," or "should buy." Use "in this simulation" or "the model shows."

## 8. Motion

- Transitions 150 to 250 ms, ease-out.
- No autoplay. Live charts update in place without flashing.

## 9. Testing this document

- Each screen is checked at 360, 768, and 1280 px widths (Playwright screenshots, see TESTING.md).
- Accessibility scan with axe on each page; zero critical violations required.
