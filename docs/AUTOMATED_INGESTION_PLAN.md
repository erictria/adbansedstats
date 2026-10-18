# Future automated ingestion plan

This plan extends the current [PBA ingestion workflow](../repos/ingestion/README.md)
when regular updates justify automation. The [deployment runbook](DEPLOYMENT.md)
already schedules `--prepare-pba`: it refreshes the published Final-game pages
and review files, but does not write DuckDB. Keep that safe boundary until the
remaining identity and source-data checks can be made reliable.

## When to implement it

Automate more of the workflow when new games arrive often enough that manual
imports are a burden, when the published player/team directories can be obtained
reliably, and when most new observations can be matched to established identities
without guessing. A scheduled job should still stop and request review for a new
or conflicting person, team, or roster interval. Scheduling is not evidence that
the data is correct.

Start within `repos/ingestion`; it already owns retrieval, normalization, and
storage. Do not create a separate ingestion service solely to run a timer. Add
separate source adapters and per-tournament configuration there as new leagues
arrive. Reconsider a separate orchestration platform only when the number of
sources, dependencies, backfills, and operators warrants it.

## Target workflow

```text
timer / manual trigger
  -> discover Final games and refresh changed source pages
  -> parse and validate cached records
  -> match against saved, reviewed identities
  -> if uncertain: write review report, alert, stop before database write
  -> if complete: back up database, pause Banse, import one transaction
  -> restart Banse, check API and counts, record run result, alert on failure
```

The local work directory remains durable across runs. Keep `identities.json`,
the cached source pages, match evidence, and run reports with the database
backups. A refresh must preserve confirmed UUIDs and manual corrections.

## Implementation phases

1. **Define a machine-checkable preflight.** Add a non-writing validation mode
   to the ingestion CLI. It should verify that the selected games are Final,
   each expected source page parsed, all team and player observations have
   confirmed mappings, no person resolves twice in one game, and roster changes
   have an explicit handling rule. Emit a structured report with source IDs,
   counts, unresolved observations, warnings, and a clear pass/fail result.
   The current `--match-pba` proposes only conservative matches;
   `--import-pba` currently writes `unresolved.json` when it discovers missing
   identities. Neither is a complete non-writing preflight today.

2. **Make retrieval incremental.** Compare discovered Final game IDs with the
   saved work directory and the last successful import. Fetch new pages and
   refresh recently changed games; allow an explicit full refresh/backfill mode.
   Preserve source URL, retrieval time, and raw response for review. Keep
   bounded retries and delays for transient HTTP failures, but fail the run if
   a page is blocked, empty, or no longer has the expected box score. The
   current `--prepare-pba --refresh` refetches all selected Final pages.

3. **Handle directory data explicitly.** Until player/team directory retrieval
   works reliably, keep refreshed `players.html` and `teams.html` as an operator
   input. Record when each snapshot was captured and reject an unexpectedly old
   snapshot. Do not automate CAPTCHA or clearance-cookie reuse. When an API or
   stable HTML source becomes available, add it as a source adapter and compare
   its IDs and names with the saved catalogs before trusting it.

4. **Add the review gate.** Run the matcher and preflight after preparation.
   Known, unchanged matches may proceed under an explicit policy; new IDs,
   ambiguous names, jersey conflicts, and multi-team players go to a review
   queue or report. Require a person to update and confirm `identities.json`
   before retrying the import. Record the evidence and approver outside the
   generated match suggestion so a later refresh cannot silently approve it.
   Make the command resumable after review without refetching every page.

5. **Build a guarded import runner.** Use one lock for all work-directory
   mutations and imports so scheduled and manual runs cannot overlap; human
   review can happen after the preparation command releases the lock. At import
   time, acquire the lock again and recheck that the reviewed inputs have not
   changed. Stop Banse, create a dated, verified database backup, run
   `--import-pba` against the configured file, and restart Banse even when the
   import fails. Keep the existing transactional import and stable source
   mappings so a retry updates the same games instead of creating duplicates.
   Do not let another reader hold the database open during the write window;
   the current DuckDB file-access rules require this coordination.
   [DuckDB concurrency](https://duckdb.org/docs/current/connect/concurrency)

6. **Verify and observe every run.** Compare selected Final game IDs with
   imported external IDs, check expected player and team-stat row coverage,
   detect implausible drops in counts, and query Banse's `/api/tournaments` plus
   representative game endpoints after restart. Record start/end times, source
   and tournament, counts added/updated, review status, error, and backup path.
   Send an alert for retrieval failure, unresolved identities, failed import,
   failed restart, failed backup, or a stale last-success timestamp. Keep a
   simple manual rerun and restore command in the deployment runbook.

7. **Schedule gradually.** On the single VM, add a `systemd` oneshot service
   and timer for the guarded pipeline only after the preflight and recovery
   behavior pass tests. Begin with a manual run, then a scheduled prepare and
   review notification, then unattended imports of fully resolved batches.
   Choose a time after games normally become Final and document the timezone.
   `OnCalendar` and `Persistent=true` can cover daily scheduling and catch-up
   after downtime. [systemd timer manual](https://man7.org/linux/man-pages/man5/systemd.timer.5.html)

## Tests and rollout checks

- Repeat the same batch twice and confirm stable UUIDs, row counts, and source
  mappings; no duplicate games or statistics should appear.
- Introduce an unknown player, ambiguous name, changed jersey, blocked page,
  and incomplete box score in fixtures; each must stop before database writes
  and leave reviewable evidence.
- Simulate an import failure and confirm the transaction rolls back, Banse
  restarts, and the backup remains available. Test an actual restore on a copy.
- Confirm the timer cannot overlap a manual run and that a missed timer run does
  not import stale or partially prepared files without preflight.
- Reconcile the published Final-game list with the database after every run;
  investigate differences rather than silently marking the run successful.

Airflow can replace the timer and provide task-level scheduling and monitoring
once there are many source pipelines or backfills to coordinate. It does not
remove identity review or DuckDB's writer/readers constraint, and it brings a
scheduler, DAG processor, API server, and metadata database to operate.
[Airflow architecture](https://airflow.apache.org/docs/apache-airflow/stable/core-concepts/overview.html)
