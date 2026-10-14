import datetime
import io

import pandas as pd
import streamlit as st
from openpyxl.styles import Font, PatternFill

from report_data import build_report

st.set_page_config(page_title="Reliance Jio Tracker Report", layout="wide")
st.title("Reliance Jio Infocomm Limited – Tracker Report")

col1, col2 = st.columns(2)
from_date = col1.date_input("Case received from", datetime.date(2026, 1, 1))
to_date = col2.date_input("Case received to", datetime.date.today())

if from_date > to_date:
    st.error("'From' date must not be after 'To' date.")
    st.stop()

if st.button("Generate report", type="primary"):
    with st.spinner("Querying database..."):
        try:
            st.session_state["df"] = build_report(from_date, to_date)
            st.session_state["range"] = f"{from_date:%Y%m%d}_{to_date:%Y%m%d}"
        except Exception as exc:  # surface DB/connection problems to the user
            st.session_state.pop("df", None)
            st.error(f"Failed to generate report: {exc}")

df = st.session_state.get("df")
if df is not None:
    if df.empty:
        st.warning("No cases found for the selected range.")
    else:
        st.success(f"{len(df):,} cases")
        st.dataframe(df.head(200), use_container_width=True)
        stem = f"Reliance_Jio_Tracker_{st.session_state['range']}"
        d1, d2 = st.columns(2)
        d1.download_button("Download CSV", df.to_csv(index=False).encode("utf-8-sig"),
                           f"{stem}.csv", "text/csv")
        buf = io.BytesIO()
        with pd.ExcelWriter(buf, engine="openpyxl") as writer:
            df.to_excel(writer, index=False, sheet_name="Tracker")
            header_fill = PatternFill("solid", start_color="D9D9D9", end_color="D9D9D9")
            for cell in writer.sheets["Tracker"][1]:
                cell.font = Font(bold=True)
                cell.fill = header_fill
        d2.download_button("Download Excel", buf.getvalue(), f"{stem}.xlsx",
                           "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
