from datetime import datetime

import pandas as pd
import streamlit as st

from ui import data


def render(doctor_id: str) -> None:
    doctor = next(d for d in data.list_doctors() if d.doctor_id == doctor_id)
    st.header(doctor.name)
    st.caption(doctor.specialty)

    schedule_tab, lookup_tab, research_tab = st.tabs(["My schedule", "Patient lookup", "Clinical research"])
    with schedule_tab:
        render_schedule(doctor_id)
    with lookup_tab:
        st.info("Patient lookup will appear here.")
    with research_tab:
        st.info("Clinical research will appear here.")


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
