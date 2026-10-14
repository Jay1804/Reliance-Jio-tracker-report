# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Repository purpose

This is not a software project — it is a working directory holding a single automation script and the data it produces. The script logs into AuthBridge's internal "MIS Query Browser" web app (`https://mis.authbridge.com/export_query/`) and downloads a client-specific tracker report that would otherwise be exported manually through the browser UI (login → select Host/Database/Data Time Slab/Query → set From/To dates → click Export).

## Running the export

```
python export_mis_query.py
```

No dependencies beyond `requests` (stdlib `zipfile`/`io`/`datetime` otherwise). There is no build, lint, or test tooling in this repo — it's a standalone script.

The script writes two files into the working directory on each run:
- `Reliance Jio Infocomm Limited Tracker client_code 2435.csv.zip` — raw response from the server
- `Reliance Jio Infocomm Limited Tracker client_code 2435.csv` — extracted CSV (can be 100MB+; the full 2021-to-date range for this query produces ~150MB)

`TO_DATE` in the script is computed as `datetime.date.today()`, so every run exports up through the current date without edits.

## How the target site works (relevant if extending the script)

The MIS Query Browser (`export_query/home.php`) is a legacy PHP form with cascading, AJAX-populated dropdowns. To submit a new/different export, the same sequence of dependent requests must be resolved in order — you can't just guess IDs:

1. **Login**: `POST login.php` with `username`, `password`, `login` fields. A successful login redirects to `home.php`.
2. **Host → Database**: selecting a Host `<select name="hostname">` fires `GET host_ajax.php?host_id=<id>`, which returns the `<select name="database">` options valid for that host (values are internal DB names like `checkpoint_live`, not the display labels).
3. **Data Time Slab → Query**: selecting `<select name="access_time">` fires `GET time_ajax.php?access_time=<slab name>`, returning the `<select name="csv_query">` options (each option value is a numeric query ID, e.g. `1500` for the Reliance Jio tracker).
4. **Query → date fields**: selecting `csv_query` fires `GET ajax.php?query=<id>`, which returns the Query Level, Days Range, and the `date1`/`date2` text inputs for that query.
5. **Export**: the whole form is `POST`ed to `process.php` with `hostname`, `database`, `access_time`, `csv_query`, `query_days_range`, `date1`, `date2`. The response body is the export file directly (a zip containing one CSV) — not a redirect or a job you poll for.

Large date ranges can take several minutes server-side before `process.php` responds; the request has no async/progress endpoint, so the client just blocks on the POST (the script uses a 600s timeout).

To export a different query/client, find its numeric `csv_query` ID and the `database`/`access_time` values by walking the same AJAX chain (e.g. via browser devtools or by replaying steps 2–4 above), then swap the constants at the top of `export_mis_query.py`.

## Credentials

The AuthBridge MIS username/password are hardcoded as constants (`USERNAME`, `PASSWORD`) at the top of `export_mis_query.py`. This is an internal-only working directory, not a shared/public repo — if this script is ever moved into a shared repository, pull credentials out into environment variables first.
