"""Pieces shown in both the patient and doctor views."""
import pandas as pd
import streamlit as st

from ui.data import PatientAppointment


def escape(text: str) -> str:
    return text.replace("$", r"\$")  # a bare $ would start a math expression


def appointments_table(appointments: list[PatientAppointment]) -> None:
    if not appointments:
        st.caption("None scheduled.")
        return
    st.dataframe(
        pd.DataFrame(
            {
                "When": [a.when.strftime("%a %b %d, %Y %I:%M %p") for a in appointments],
                "Doctor": [a.doctor_name for a in appointments],
                "Specialty": [a.specialty for a in appointments],
            }
        ),
        hide_index=True,
        width="stretch",
    )


def visit_history(encounters: list, detailed: bool) -> None:
    """Past visits, newest first. detailed adds the exam findings."""
    if not encounters:
        st.caption("No past visits on file.")
        return
    for visit in encounters:
        code = f" ({visit.icd10_code})" if visit.icd10_code else ""
        title = f"{visit.visit_date} - {visit.diagnosis or visit.chief_complaint}{code}"
        if visit.provider:
            title += f" - {visit.provider}"
        sections = [("Complaint", visit.chief_complaint)]
        if detailed:
            sections += [("Subjective", visit.subjective), ("Objective", visit.objective)]
        sections += [("Assessment", visit.assessment), ("Plan", visit.plan)]
        with st.expander(title):
            for label, text in sections:
                if text:
                    st.markdown(f"**{label}.** {escape(text)}")
