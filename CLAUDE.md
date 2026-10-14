# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Repository purpose

A small Streamlit app that builds the **Reliance Jio Infocomm Limited Tracker** report (client ID `171621`) by querying the **live AuthBridge MySQL database directly**. It replaces the old manual flow through the internal "MIS Query Browser" (`mis.authbridge.com/export_query/`), which is no longer used or scripted here. The report mirrors the old query's columns and column order.

## Files

- `reliance_app.py` — Streamlit UI: pick "Case received from/to" dates, click **Generate report**, preview the first 200 rows, download CSV or Excel (Excel header row is bold on light gray).
- `report_data.py` — data access and report assembly (`build_report(from_date, to_date)` returns a DataFrame).
- `requirements.txt` — `requests`, `streamlit`, `pandas`, `pymysql`, `python-dotenv`, `openpyxl`.
- `.env` — credentials (git-ignored, never commit). Keys: `DB_HOST`, `DB_NAME`, `DB_USER`, `DB_PASSWORD`, plus `SMTP_HOST`, `SMTP_PORT`, `EMAIL_SENDER`, `EMAIL_PASSWORD` (SMTP keys are not currently used by the code).

## Running

```
pip install -r requirements.txt
python -m streamlit run reliance_app.py --server.port 8502
```

Use a port other than the default 8501 (8502 is what has been used here). There is no build, lint, or test tooling; to check the data layer without the UI:

```
python -c "import datetime; from report_data import build_report; print(build_report(datetime.date(2026,10,1), datetime.date(2026,10,14)).shape)"
```

## How `report_data.py` works

- Connects with `pymysql` using the `.env` credentials (30s connect timeout, 600s read timeout).
- The original query ran ~60 correlated subqueries per case. It is now split into three set-based queries, all filtered by the same case predicate, then combined in pandas:
  - `CASE_SQL` — one row per case from `ec_case_master` joined to company, process, location, candidate and flex fields.
  - `CHECKS_SQL` — rows from `ec_case_checks`, joined to verification sources (this can fan a check out into several rows, so `case_check_id` is de-duplicated where it matters).
  - `REPORTS_SQL` — sent reports (`report_status = 5`, `report_type` 0/1/2) from `ec_case_reports`; the highest `case_report_id` per case and type is the latest.
- Case filter: `client_id = 171621`, `received_date` in `[from, to + 1 day)`, `case_status NOT IN (8, 14)`, and candidates not named `dummy`.
- Lookup dicts (`CASE_STATUS`, `DATA_SOURCE`, `CHECK_STATUS`) translate numeric codes to labels. `CHECK_COLUMNS` defines the per-check pivot columns (check ID, label, number of columns); extra columns are labelled `label (n)`.
- Date aggregation (`_latest_date`) converts columns to datetime with `errors="coerce"` before taking the max — the DB returns mixed types (dates, strings, zero-dates) in these object columns and a plain `max` fails.

## Extending

- To change the client, edit `CLIENT_ID` in `report_data.py`.
- To add or remove check columns, edit `CHECK_COLUMNS`, then check the column ordering at the end of `build_report`.
- Large date ranges can take a while because the queries run synchronously; the UI shows a spinner.

## Credentials

Credentials live only in `.env` (git-ignored). Do not hardcode them or commit them. The repo is pushed to https://github.com/Jay1804/Reliance-Jio-tracker-report.
