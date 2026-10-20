import streamlit as st

from app.orchestrator.flow import stream_turn
from ui import chat, data
from ui.components import appointments_table, escape, visit_history
from ui.render import show_message

CHAT_HEIGHT = 540
GREETING = (
    "Hi, I'm the MedQuery assistant. Tell me what you need, for yourself or a family member: "
    "booking a doctor, looking up a patient's history, or researching a condition."
)
EXAMPLES = {
    "Book for a parent, plus research": (
        "My 70-year-old father has chronic kidney disease. I want to book a nephrologist for "
        "him. Also, can you summarize latest treatment methods?"
    ),
    "Describe symptoms": "I've been extremely thirsty lately and I'm urinating a lot more than usual.",
    "See a doctor": "I'd like to see a doctor.",
}
STEP_NAMES = {"history": "Patient history", "research": "Condition research", "booking": "Booking"}


def render() -> None:
    chat_id = chat.current_chat_id()
    _sidebar_controls()

    st.header("Patient")
    assistant_tab, records_tab = st.tabs(["Assistant", "My appointments and history"])
    with assistant_tab:
        _render_chat(chat_id)

    # These read the conversation after this run's message has been handled.
    _sidebar_progress(chat_id)
    with records_tab:
        _render_records(chat_id)


def _queue_prompt(text: str) -> None:
    st.session_state["queued_prompt"] = text


def _sidebar_controls() -> None:
    with st.sidebar:
        st.button("New conversation", on_click=chat.start_new_chat, width="stretch")
        st.caption("Try an example")
        for label, text in EXAMPLES.items():
            st.button(label, key=f"example-{label}", on_click=_queue_prompt, args=(text,), width="stretch")


def _sidebar_progress(chat_id: str) -> None:
    state = chat.conversation_state(chat_id)
    with st.sidebar:
        st.divider()
        st.subheader("This conversation")
        if state.get("patient_name"):
            relationship = state.get("patient_relationship")
            suffix = f" (your {relationship})" if relationship and relationship != "self" else ""
            st.markdown(f"**Patient:** {state['patient_name']}{suffix}")
        else:
            st.caption("Patient not identified yet.")

        steps = state.get("plan") or []
        if not steps:
            st.caption("No plan yet. Tell the assistant what you need.")
        current_shown = False
        for step in steps:
            name = STEP_NAMES.get(step["agent"], step["agent"])
            if step["status"] == "done":
                st.markdown(f"- {name}: done")
            elif not current_shown:
                st.markdown(f"- **{name}: in progress**")
                current_shown = True
            else:
                st.markdown(f"- {name}: up next")


def _show(message: dict) -> None:
    with st.chat_message(message["role"]):
        if message["role"] == "assistant":
            show_message(message["text"], message["used_reference"])
        else:
            st.markdown(escape(message["text"]))


def _render_chat(chat_id: str) -> None:
    key = f"messages-{chat_id}"
    if key not in st.session_state:
        st.session_state[key] = chat.transcript(chat_id)
    messages = st.session_state[key]

    box = st.container(height=CHAT_HEIGHT)
    prompt = st.chat_input("Message MedQuery") or st.session_state.pop("queued_prompt", None)

    with box:
        if not messages and not prompt:
            with st.chat_message("assistant"):
                st.markdown(GREETING)
        for message in messages:
            _show(message)

        if prompt:
            user_message = {"role": "user", "text": prompt, "used_reference": False}
            messages.append(user_message)
            _show(user_message)
            _answer(chat_id, prompt, messages)


def _answer(chat_id: str, prompt: str, messages: list[dict]) -> None:
    with st.chat_message("assistant"):
        result = None
        try:
            with st.status("Working on it...", expanded=True) as status:
                for kind, payload in stream_turn(chat_id, prompt):
                    if kind == "start":
                        status.update(label=f"{payload}...")
                    elif kind == "done":
                        st.write(f"- {payload}")
                    else:
                        result = payload
                status.update(label="Done", state="complete", expanded=False)
        except Exception as exc:
            st.error(f"Something went wrong, please try again. ({exc})")
            return
        show_message(result.reply, result.used_reference)
    messages.append({"role": "assistant", "text": result.reply, "used_reference": result.used_reference})


def _render_records(chat_id: str) -> None:
    patient_id = chat.conversation_state(chat_id).get("patient_id")
    if not patient_id:
        st.info("Once the assistant knows who the patient is, their appointments and history appear here.")
        return

    detail = data.patient_detail(patient_id)
    st.subheader(detail.patient.name)

    st.markdown("**Upcoming appointments**")
    appointments_table(detail.upcoming)

    st.markdown("**Summary**")
    st.write(detail.patient.summary or "No summary on file yet.")

    st.markdown("**Past visits**")
    visit_history(detail.encounters, detailed=False)
