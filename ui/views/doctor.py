from datetime import datetime

import pandas as pd
import streamlit as st

from app.tools.research_tools import research_disease
from ui import data
from ui.components import appointments_table, escape, visit_history
from ui.render import show_message

RESEARCH_FOCI = ["treatment", "diagnosis", "prevention", "causes"]
NOTE_LABELS = {"record": "Imported record", "memory": "Remembered"}


def render(doctor_id: str) -> None:
    doctor = next(d for d in data.list_doctors() if d.doctor_id == doctor_id)
    st.header(doctor.name)
    st.caption(doctor.specialty)

    schedule_tab, lookup_tab, research_tab = st.tabs(["My schedule", "Patient lookup", "Clinical research"])
    with schedule_tab:
        render_schedule(doctor_id)
    with lookup_tab:
        render_lookup()
    with research_tab:
        render_research()


def render_schedule(doctor_id: str) -> None:
    show_past = st.toggle("Include past appointments", value=False, key=f"past-{doctor_id}")
    rows = data.doctor_schedule(doctor_id, include_past=show_past)
    upcoming = [r for r in rows if r.when >= datetime.now()]

    first, second, third = st.columns(3)
    first.metric("Upcoming appointments", len(upcoming))
    if upcoming:
        next_up = upcoming[0].when
        second.metric(
            "Next appointment",
            f"{next_up:%b} {next_up.day}",
            delta=next_up.strftime("%I:%M %p").lstrip("0"),
            delta_color="off",
            delta_arrow="off",
        )
    else:
        second.metric("Next appointment", "None")
    third.metric("Patients", len({r.patient_id for r in upcoming}))

    if not rows:
        st.info("No appointments booked yet.")
        return

    table = pd.DataFrame(
        {
            "Date": [r.when.strftime("%a %b %d, %Y") for r in rows],
            "Time": [r.when.strftime("%I:%M %p").lstrip("0") for r in rows],
            "Patient": [r.patient_name for r in rows],
            "Patient ID": [r.patient_id for r in rows],
            "Concern": [r.concern or "-" for r in rows],
        }
    )
    st.dataframe(table, hide_index=True, width="stretch")

    st.subheader("Appointments by day")
    by_day = pd.Series([r.when.date() for r in rows]).value_counts().sort_index()
    st.bar_chart(by_day)


def render_lookup() -> None:
    patients = data.list_patients()
    labels = {p.patient_id: f"{p.name} ({p.patient_id})" for p in patients}
    patient_id = st.selectbox(
        "Patient",
        options=list(labels),
        format_func=labels.get,
        index=None,
        placeholder="Search by name or ID",
        key="lookup-patient",
    )
    if patient_id is None:
        st.info("Choose a patient to see their record.")
        return

    detail = data.patient_detail(patient_id)
    patient = detail.patient
    st.subheader(patient.name)

    age, gender, born, mrn = st.columns(4)
    age.metric("Age", data.patient_age(patient))
    gender.metric("Gender", patient.gender or "-")
    born.metric("Date of birth", f"{patient.dob:%b} {patient.dob.day}, {patient.dob.year}" if patient.dob else "-")
    mrn.metric("MRN", patient.mrn or "-")
    contact = [part for part in (patient.phone, patient.email, patient.address) if part]
    if contact:
        st.caption(" | ".join(contact))

    st.markdown("**Summary**")
    st.write(patient.summary or "No summary on file.")

    st.markdown("**Upcoming appointments**")
    appointments_table(detail.upcoming)

    st.markdown("**Visit history**")
    visit_history(detail.encounters, detailed=True)

    if detail.notes:
        with st.expander(f"Long-term memory notes ({len(detail.notes)})"):
            for kind, text in detail.notes:
                st.markdown(f"- *{NOTE_LABELS.get(kind, kind)}:* {escape(text)}")


def render_research() -> None:
    with st.form("research-form"):
        disease = st.text_input("Condition", placeholder="e.g. chronic kidney disease")
        focus = st.selectbox("Focus", RESEARCH_FOCI)
        submitted = st.form_submit_button("Research")

    if submitted and disease.strip():
        with st.spinner("Searching MedlinePlus, PubMed, and WHO..."):
            text = research_disease.invoke({"disease": disease.strip(), "focus": focus})
        st.session_state["research"] = {"disease": disease.strip(), "focus": focus, "text": text}
    elif submitted:
        st.warning("Enter a condition to research.")

    saved = st.session_state.get("research")
    if saved:
        st.subheader(f"{saved['disease'].title()} - {saved['focus']}")
        show_message(saved["text"], used_reference=True)
