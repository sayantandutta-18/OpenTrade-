# OpenTrade Documentation

OpenTrade is a web app for exploring how markets absorb large orders. A user picks stocks, runs a simulated limit order book, injects a trade of a chosen size, and sees how much the price moves. Every number is labeled REAL, CALIBRATED, or SYNTHETIC. Simulated data is never shown as real.

This folder is the complete specification. It is written so that an AI coding agent (such as Google Antigravity) can build the app phase by phase from these documents alone.

## Document index

| File | Purpose |
|---|---|
| IDEA.md | Why the product exists, who it serves, what it is not |
| PRD.md | Product requirements: goals, features, scope, success measures |
| SRS.md | Software requirements: functional (FR) and non-functional (NFR) |
| USER_STORIES.md | What users need, written as stories (US) |
| ACCEPTANCE_CRITERIA.md | Pass or fail tests for each story (AC) |
| TRD.md | Technology choices, performance targets, technical constraints |
| SYSTEM_ARCHITECTURE.md | Layers, components, and how data moves through them |
| DATABASE.md | Tables, columns, relationships, and migration rules |
| API_SPEC.md | Every endpoint with request and response shapes |
| USER_FLOW.md | Step-by-step user journeys and error paths |
| UI_UX_GUIDELINES.md | Screen rules, components, accessibility, and copy |
| PROJECT_STRUCTURE.md | Exact folder and file layout to create |
| SECURITY.md | Threat model and the controls for each threat |
| TESTING.md | Test levels, tools, and what must be tested in each phase |
| DEPLOYMENT.md | Environments, release steps, rollback, backups |
| ENVIRONMENT.md | Every environment variable and setup commands |
| CODING_STANDARDS.md | Code style, engine rules, security and provenance rules |
| AGENTS.md | Rules and working method for AI coding agents |
| TASKS.md | Ordered task list mapped to roadmap phases, with status |
| DECISIONS.md | Architecture decision records (ADRs) |
| CHANGELOG.md | Version history |

## How to use this with Antigravity

1. Read AGENTS.md first. It sets the rules the agent must follow.
2. Work through TASKS.md in order. Give the agent one task ID at a time.
3. For each task, the agent reads the linked spec section and the acceptance criteria it must pass.
4. A task is DONE only when its acceptance criteria pass and its tests run green.

## Reading order for humans

IDEA, PRD, USER_FLOW, SYSTEM_ARCHITECTURE, CODING_STANDARDS, TASKS.

## Status

Specification complete. No code written yet. Build starts at Phase 0, task T0.1.
