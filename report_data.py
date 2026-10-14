"""Data access for the Reliance Jio tracker report.

The original query ran ~60 correlated subqueries per case against ec_case_checks /
ec_case_reports. Here the work is split into three set-based queries (cases, checks,
reports) that are all filtered by the same case predicate, then combined in pandas.
"""
import os

import pandas as pd
import pymysql
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env"))

CLIENT_ID = 171621

CASE_STATUS = {
    1: "New (Incomplete)", 2: "On Hold", 3: "Insufficient", 4: "Work in Progress",
    5: "Pending for report", 6: "Closed by Client", 7: "Completed",
    8: "Closed by Authbridge", 9: "Closed-Case Insufficient", 10: "HighlighterCase",
    11: "SignOff Pending", 12: "Pending For Duplicity", 13: "Duplicity", 14: "Scrap",
    15: "Excel Pending For Duplicity", 16: "Escalation Raised",
    17: "Escalation Received", 18: "Excel Duplicity",
}

DATA_SOURCE = {
    1: "Mcs", 2: "Bridge", 3: "Case", 4: "CandidateApp", 5: "Api", 6: "ExcelCase",
    7: "SingleCase", 9: "Mail", 10: "Link", 11: "HardCopy", 12: "ClientPortal",
    13: "Data Entry - Non PVT", 14: "iBridge", 15: "PVT Microservices",
}

CHECK_STATUS = {
    0: "Work in Progress", 1: "Work in Progress", 2: "On Hold", 3: "Insufficient",
    4: "Work in Progress", 5: "Work in Progress", 6: "Work in Progress",
    7: "Work in Progress", 8: "Completed", 9: "Disabled",
    10: "case closed by client", 11: "Closed with Insufficiency",
    12: "Closed-case Insufficient", 13: "Work in Progress",
}

# (check_id, column label, number of columns). Extra columns are labelled "label (n)".
CHECK_COLUMNS = [
    (50, "India Criminal Litigation Database Check", 2),
    (57, "Current Address Verification", 2),
    (41, "Previous Employment Verification", 4),
    (58, "Current Employment Verification", 1),
    (1, "Permanent Address Verification", 2),
    (144, "Education Verification Written", 2),
    (63, "India Credit Default Database Check", 1),
    (72, "National Identity Check", 2),
    (83, "Education Verification W", 5),
    (132, "India Court Record Database Check", 1),
    (133, "Global Regulatory Compliance and Debarment Database Verification", 1),
    (208, "Global Regulatory Compliance and Debarment Database Verification (208)", 1),
]

CASE_SQL = """
SELECT ecm.case_id,
       emc.company_name AS `Client Name`, ecp.process_name AS `Process`,
       ecm.case_ars_no AS `ARS Number`, '' AS `Email`,
       CONCAT(ecc.first_name,' ',ecc.middle_name,' ',ecc.last_name) AS `Candidate Name`,
       ecc.mobile_no AS `Mobile No`, emcl.office_name AS `Location`,
       ecm.received_date AS `Case Received Date`,
       ecf.case_flex_field1 AS `Employee ID`, ecf.case_flex_field2 AS `Designation`,
       ecf.case_flex_field3 AS `Recruiter`,
       DATE_FORMAT(ecm.case_expected_closure_date,'%%d-%%b-%%Y') AS `Delivery Date`,
       ecm.last_insuff_date AS `Latest CaseLevel InsuffRaised Date`,
       ecm.last_insuff_fulfill_date AS `Latest CaseLevel InsuffFulfilled Date`,
       ecm.case_status AS _case_status,
       ecf.case_flex_field4 AS `Report E-mail ID`, ecf.case_flex_field5 AS `API Request Id`,
       ecf.case_flex_field6 AS `Candidate ID`, ecf.case_flex_field7 AS `Vertical`,
       ecf.case_flex_field8 AS `For Future Use`, ecf.case_flex_field9 AS `Additional Checks`,
       ecf.case_flex_field10 AS `NHQ/ Geography`, ecf.case_flex_field11 AS `Region`,
       ecm.data_source AS _data_source
FROM ec_case_master ecm
LEFT JOIN ec_master_company emc ON ecm.client_id = emc.company_id
LEFT JOIN ec_client_process ecp ON ecm.process_id = ecp.process_id
LEFT JOIN ec_master_company_locations emcl ON ecm.client_office_id = emcl.office_id
LEFT JOIN ec_case_candidates ecc ON ecm.candidate_id = ecc.candidate_id
LEFT JOIN ec_case_fields ecf ON ecm.case_id = ecf.case_id
WHERE ecm.client_id = %s
  AND ecm.received_date >= %s AND ecm.received_date < %s
  AND ecm.case_status NOT IN (8, 14)
  AND ecc.first_name <> 'dummy' AND ecc.middle_name <> 'dummy' AND ecc.last_name <> 'dummy'
"""

CHECKS_SQL = """
SELECT c.case_id, c.case_check_id, c.check_id, c.check_name, c.check_status,
       c.check_severity, c.family_id, c.insuff_date, c.insuff_fulfill_date,
       c.go_ahead_date, c.reopen_date, c.insuff_remarks, c.closure_comments,
       CASE WHEN c.family_id = 5 THEN IFNULL(emc.company_name,'')
            ELSE IFNULL(emei.institute_name,'') END AS org_name
FROM ec_case_checks c
JOIN ec_case_master ecm ON ecm.case_id = c.case_id
LEFT JOIN ec_case_candidates ecc ON ecm.candidate_id = ecc.candidate_id
LEFT JOIN ec_case_check_verification_source eccvs ON c.case_check_id = eccvs.case_check_id
LEFT JOIN ec_master_company emc ON eccvs.org_id = emc.company_id
LEFT JOIN ec_master_educational_institute emei ON eccvs.org_id = emei.institute_id
WHERE ecm.client_id = %s
  AND ecm.received_date >= %s AND ecm.received_date < %s
  AND ecm.case_status NOT IN (8, 14)
  AND ecc.first_name <> 'dummy' AND ecc.middle_name <> 'dummy' AND ecc.last_name <> 'dummy'
"""

REPORTS_SQL = """
SELECT r.case_id, r.case_report_id, r.report_type, r.report_sent_on, r.report_severity
FROM ec_case_reports r
JOIN ec_case_master ecm ON ecm.case_id = r.case_id
LEFT JOIN ec_case_candidates ecc ON ecm.candidate_id = ecc.candidate_id
WHERE r.report_status = 5 AND r.report_type IN (0, 1, 2)
  AND ecm.client_id = %s
  AND ecm.received_date >= %s AND ecm.received_date < %s
  AND ecm.case_status NOT IN (8, 14)
  AND ecc.first_name <> 'dummy' AND ecc.middle_name <> 'dummy' AND ecc.last_name <> 'dummy'
"""


def _connect():
    return pymysql.connect(
        host=os.environ["DB_HOST"], user=os.environ["DB_USER"],
        password=os.environ["DB_PASSWORD"], database=os.environ["DB_NAME"],
        connect_timeout=30, read_timeout=600, charset="utf8mb4",
    )


def _query(conn, sql, params) -> pd.DataFrame:
    with conn.cursor() as cur:
        cur.execute(sql, params)
        cols = [d[0] for d in cur.description]
        return pd.DataFrame(cur.fetchall(), columns=cols)


def _fmt(series: pd.Series) -> pd.Series:
    return pd.to_datetime(series, errors="coerce").dt.strftime("%d-%b-%Y")


def _check_label(row) -> str:
    status = int(row["check_status"])
    if status in (8, 10, 11, 12):
        return row["check_severity"]
    return CHECK_STATUS.get(status)


def _concat(series: pd.Series) -> str | None:
    items = [s for s in series if s]
    return ",".join(items) if items else None


def _latest_date(checks: pd.DataFrame, col: str) -> pd.Series:
    dates = pd.to_datetime(checks[col], errors="coerce")
    return _fmt(dates.groupby(checks["case_id"]).max())


def build_report(from_date, to_date) -> pd.DataFrame:
    """Cases received on [from_date, to_date] inclusive (dates, not datetimes)."""
    end = pd.Timestamp(to_date) + pd.Timedelta(days=1)
    params = (CLIENT_ID, pd.Timestamp(from_date), end)

    conn = _connect()
    try:
        cases = _query(conn, CASE_SQL, params)
        checks = _query(conn, CHECKS_SQL, params)
        reports = _query(conn, REPORTS_SQL, params)
    finally:
        conn.close()

    if cases.empty:
        return cases

    cases["Case Status"] = cases.pop("_case_status").map(lambda v: CASE_STATUS.get(v if v is None else int(v)))
    cases["DATA_SOURCE"] = cases.pop("_data_source").map(lambda v: DATA_SOURCE.get(v if v is None else int(v)))
    cases = cases.set_index("case_id")

    # The join to verification sources can fan a check out into several rows; the
    # case-level aggregates below need one row per check where that matters.
    checks = checks.sort_values("case_check_id")
    checks_unique = checks.drop_duplicates("case_check_id")
    active = checks_unique[checks_unique["check_status"] != 9]

    # --- case-level check aggregates ---------------------------------------
    cases["Insuff_raise_date"] = _latest_date(active, "insuff_date")
    cases["LatestCheck InsuffFulfilled Date"] = _latest_date(checks_unique, "insuff_fulfill_date")
    cases["Go Ahead Date"] = _latest_date(checks_unique, "go_ahead_date")
    cases["Reopen Date"] = _latest_date(checks_unique, "reopen_date")

    def comments(frame):
        text = (frame["check_name"].astype(str) + " (" + frame["org_name"].fillna("") + ")  --> "
                + frame["insuff_remarks"].astype(str))
        return frame.assign(_t=text).groupby("case_id")["_t"].agg(_concat)

    open_insuff = checks[checks["check_status"] == 3]
    cases["Open_Insuff_Comments"] = comments(open_insuff)
    cases["Insuff Comments Open+Close"] = comments(checks[checks["insuff_remarks"].notna()])

    closure = checks_unique[
        checks_unique["check_status"].isin([8, 10, 11, 12])
        & checks_unique["check_severity"].isin(["Discrepant", "Minor Discrepant"])
        & checks_unique["closure_comments"].notna()
    ]
    cases["Closure Comments All"] = (
        (closure["check_name"] + "-->" + closure["closure_comments"])
        .groupby(closure["case_id"]).agg(_concat)
    )

    # --- reports: latest (highest case_report_id) per case and type ----------
    latest = reports.sort_values("case_report_id").drop_duplicates(["case_id", "report_type"], keep="last")
    for rtype, sent, sev in [
        (0, "Latest Interim Report Sent Date", "Latest Interim Report Severity"),
        (1, "Final Report Sent Date", "Final Report Severity"),
        (2, "Latest Additional Report SentDate", "Latest Additional Report Severity"),
    ]:
        sub = latest[latest["report_type"] == rtype].set_index("case_id")
        cases[sent] = _fmt(sub["report_sent_on"])
        cases[sev] = sub["report_severity"]
    cases["Latest Severity"] = cases["Latest Additional Report Severity"]

    # --- per-check pivot columns --------------------------------------------
    active = active.assign(_label=active.apply(_check_label, axis=1))
    for check_id, label, n in CHECK_COLUMNS:
        sub = active[active["check_id"] == check_id].copy()
        sub["_n"] = sub.groupby("case_id").cumcount()
        for i in range(n):
            name = label if i == 0 else f"{label} ({i})"
            cases[name] = sub[sub["_n"] == i].set_index("case_id")["_label"]

    # --- column order: matches the original query ---------------------------
    order = [
        "Client Name", "Process", "ARS Number", "Email", "Candidate Name", "Mobile No",
        "Location", "Case Received Date", "Employee ID", "Designation", "Recruiter",
        "Delivery Date", "Latest CaseLevel InsuffRaised Date",
        "Latest CaseLevel InsuffFulfilled Date", "Case Status", "Insuff_raise_date",
        "Open_Insuff_Comments", "LatestCheck InsuffFulfilled Date", "Go Ahead Date",
        "Reopen Date", "Latest Interim Report Sent Date", "Latest Interim Report Severity",
        "Final Report Sent Date", "Final Report Severity", "Latest Additional Report SentDate",
        "Latest Additional Report Severity", "Latest Severity", "Closure Comments All",
        "Insuff Comments Open+Close",
    ]
    check_cols = [c for c in cases.columns if any(c == l or c.startswith(l + " (") for _, l, _ in CHECK_COLUMNS)]
    tail = [
        "Report E-mail ID", "API Request Id", "Candidate ID", "Vertical", "For Future Use",
        "Additional Checks", "NHQ/ Geography", "Region", "DATA_SOURCE",
    ]
    # Original placed some check columns between the flex fields; keep the full set grouped.
    first_checks = [c for c in check_cols if not c.startswith(("India Credit", "National Identity",
                    "Education Verification W", "India Court", "Global Regulatory"))]
    later_checks = [c for c in check_cols if c not in first_checks]
    cols = order[:order.index("Closure Comments All") + 1] + ["Insuff Comments Open+Close"]
    cols += first_checks + tail[:6] + later_checks + tail[6:]
    return cases[cols].reset_index(drop=True)
