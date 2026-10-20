"""MedQuery web app. Run from the repo root: streamlit run ui/app.py

A sidebar switch chooses between the patient view (chat assistant plus the
patient's own appointments and history) and the doctor view (schedule, patient
lookup, and clinical research)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import streamlit as st  # noqa: E402

from ui import data  # noqa: E402
from ui.views import doctor, patient  # noqa: E402

st.set_page_config(page_title="MedQuery", layout="wide")

VIEWS = ["Patient", "Doctor"]


def _initial_view() -> int:
    requested = st.query_params.get("view", "patient").capitalize()
    return VIEWS.index(requested) if requested in VIEWS else 0


def main() -> None:
    with st.sidebar:
        st.title("MedQuery")
        view = st.radio("View", VIEWS, index=_initial_view(), horizontal=True)
        st.query_params["view"] = view.lower()

        doctor_id = None
        if view == "Doctor":
            doctors = data.list_doctors()
            doctor_id = st.selectbox(
                "Signed in as",
                options=[d.doctor_id for d in doctors],
                format_func=lambda i: next(f"{d.name} - {d.specialty}" for d in doctors if d.doctor_id == i),
            )
        st.divider()

    if view == "Doctor":
        doctor.render(doctor_id)
    else:
        patient.render()


main()
