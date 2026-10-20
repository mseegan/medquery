import streamlit as st


def render(doctor_id: str) -> None:
    st.header("Doctor")
    st.info(f"Schedule, patient lookup, and research for {doctor_id} will appear here.")
