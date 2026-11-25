# Idea

## The problem

Large orders move prices. A trader who buys 10,000 shares does not pay the price shown on screen. Each unit they buy pushes the price up a little, so the average price they pay is worse. This cost is called market impact or slippage, and it is one of the least intuitive parts of trading.

Most people learn about it from formulas or from losing money. Students of finance see the square-root law in papers but rarely see it happen. Retail investors have no way to test how much a trade will cost before making it.

## The solution

OpenTrade is a simulator and teaching tool. The user:

1. Picks one or more companies.
2. Runs a simulated limit order book that behaves like a real exchange.
3. Injects a market order of a size they choose.
4. Sees the slippage: the gap between the price they paid and the mid price at the moment they traded.
5. Repeats for many sizes and sees how impact grows.

The app also shows how news, liquidity, and diversification change these results.

## The core promise

Every output says where it came from.

- REAL: taken from a live or stored market data source, with the source and time shown.
- CALIBRATED: a simulation whose parameters were fitted to real data, with the data source and fit date shown.
- SYNTHETIC: a simulation with hand-set or random parameters. It is not a prediction.

Simulated data is never presented as real. This rule is more important than any feature.

## Who it is for

- **Finance students** learning market microstructure, who want to see the square-root law with their own eyes.
- **Retail investors** who want a rough sense of trading costs before a trade.
- **Developers and researchers** who want a reproducible market sandbox with seeded, saved runs.

## What it is not

- Not investment advice. The app never recommends buying or selling anything.
- Not a trading platform. It cannot place real orders with any broker.
- Not a forecast. Simulated results show how a model behaves, not what the market will do.

## Why it matters

Understanding market impact makes people better at reading their own trading costs and at spotting when a market is fragile. The product turns a difficult theory into something a user can run, change, and question.
