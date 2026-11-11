# Private KAIROS integration

KAIROS is the public-facing name of the private travel Site. Existing technical integration identifiers, environment variables, API headers, and the Site URL intentionally retain the legacy Puente names to preserve compatibility.

The existing bot remains authoritative: searches, 300-day horizon, holidays,
family coverage, TT rules, learning, SQLite history, artifacts and SMTP email
are preserved. No new flight search or duplicate email is initiated by KAIROS.

## Activate
Set the repository Actions secret `PUENTE_SITE_TOKEN` to the private Site's
service credential. The Site holds only its SHA-256 as the runtime secret
`PUENTE_SERVICE_TOKEN_HASH`. Never put credentials in code, issues, workflow
inputs or logs. The connector for source changes cannot administer GitHub
secrets; activation needs the repository's settings interface or an authorized
secrets API connection. Do not make the Site public.

The workflow pulls dated weekend states before the existing bot. Its choices
and fare thresholds are shown in an escaped email appendix. Buying intent never
marks a reservation or suppresses searches. Only explicit dated calendar states
use the existing family-plan logic. A failed pull clears runtime feedback and
uses the original plan. Personal notes and runtime feedback are not committed.

After SMTP, a separate optional step publishes observations and historical
decisions. It calls the original Python functions for market context, booking
windows and TT; there is no second scoring model. All flight alternatives are
preserved, excluding only verbose raw scraping text. Fares remain distinct
from unknown all-in costs, baggage, flexibility, Avios and fuel data.

Both bridge steps use continue-on-error. A partial transfer cannot replace the
last complete snapshot: rows are staged by run ID and activated only after exact
trip and history counts match. Retrying a batch is idempotent. Existing database
and report backups remain always-on. No existing SQLite schema is changed.

## Validate and disable
Run `python -m unittest discover -s tests -q`. Verify the Site's timestamp and
feedback revision after the next scheduled execution. Initial backfill can use
the existing report and SQLite artifacts without resending email.
To pause synchronization, remove only `PUENTE_SITE_TOKEN`; the original bot
continues with its base family plan. Reverting the integration commit needs no
history or database migration.
