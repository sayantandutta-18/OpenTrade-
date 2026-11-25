# Deployment

Version: 1.0

## 1. Environments

| Name | Purpose | Database | Live data | Email | Secrets |
|---|---|---|---|---|---|
| local | Development on a laptop | SQLite file in data/ | Off by default | Console output (printed link) | .env file |
| staging | Pre-release checks, QA | SQLite file on staging host | On, with low limits | Sandbox SMTP | Host secret store |
| production | Public app | SQLite on persistent volume (Postgres later) | On | Transactional SMTP | Host secret store |

## 2. Container

- Base image: python:3.11-slim.
- Multi-stage build: install dependencies in a builder stage, copy the virtual environment and app into a runtime stage.
- Runs as a non-root user.
- Exposes port 8501 (Streamlit) behind a reverse proxy.
- Health check: GET /_stcore/health returns 200.
- Volumes: /app/data (database and catalog), /app/results (optional).

## 3. Reverse proxy and TLS

- HTTPS only in staging and production. HTTP redirects to HTTPS.
- TLS certificates renew automatically.
- Proxy sets X-Forwarded-For, which the app trusts only from the proxy address.
- Request body limit 1 MB.

## 4. Release process

1. Work merges to main through pull requests that pass CI (see TESTING.md section 7).
2. Update CHANGELOG.md under Unreleased. Move entries to the new version heading.
3. Tag the commit: vMAJOR.MINOR.PATCH.
4. CI builds the image and tags it with the version and commit hash.
5. Deploy to staging. Run smoke tests:
   - Register a new account and verify the email link.
   - Log in and log out.
   - Run an impact sweep and save it.
   - Ask the chatbot one question and confirm one action.
   - Check the provenance badges appear.
6. If smoke tests pass, deploy the same image to production.
7. Watch error rate and login failure rate for 30 minutes.
8. Announce the release in CHANGELOG.md (already done) and close TASKS.md items.

## 5. Migrations in deployment

- Migrations run automatically at startup, before the app accepts traffic.
- Before a production deployment, a backup is taken.
- Migrations must be backward compatible for one release, so the previous image still runs against the new schema.
- A destructive migration (dropping a column) ships one release after the code stops using it.

## 6. Rollback

1. Redeploy the previous image tag.
2. If the new migration is additive, nothing else is needed.
3. If a migration must be undone, restore the pre-deployment backup and redeploy the previous image. Document the data window lost in CHANGELOG.md.

Target: rollback in under 10 minutes.

## 7. Backups

| What | How | Frequency | Retention | Restore test |
|---|---|---|---|---|
| SQLite database | Online backup API to a separate volume | Nightly, and before each deploy | 14 days | Quarterly |
| Catalog and profiles | In the git repository | On change | Git history | Not needed |
| Secrets | Host secret store, with a copy in a password manager | On change | Current only | Quarterly check |

## 8. Monitoring and alerts

| Signal | Alert when |
|---|---|
| Health check | Fails 3 times in a row |
| 5xx responses | More than 1 percent of requests in 5 minutes |
| Login failures | More than 50 per minute across all accounts |
| LLM errors | More than 10 percent of calls in 10 minutes |
| Disk space | Below 15 percent free |
| Certificate | Under 14 days to expiry |

Logs are structured JSON (TRD.md section 7). Personal data is removed before logs leave the host.

## 9. Scaling triggers

| Trigger | Action |
|---|---|
| More than 300 active accounts | Move the database to Postgres (new ADR) |
| Sweeps wait more than 30 seconds in the queue | Add a second worker |
| Chat latency above 5 seconds at p95 | Review LLM model and caching |

## 10. Post-release checklist

- Smoke tests passed on production.
- Error and login dashboards are normal for 30 minutes.
- Backup from before the deploy exists.
- CHANGELOG.md and TASKS.md are updated.
