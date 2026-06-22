"""Minimal manager UI. Install with ``pip install -e '.[ui]'`` and run via Streamlit."""

from pathlib import Path

import streamlit as st

from app.config import Settings
from app.container import build_copilot
from app.domain.models import ChatRequest

st.set_page_config(page_title="Driver Retention Copilot", layout="wide")
st.title("Driver Retention Copilot")
st.caption(
    "Recommendations only — monetary actions remain subject to operational execution checks."
)

if "conversation_id" not in st.session_state:
    st.session_state.conversation_id = None

copilot = build_copilot(
    Settings(data_dir=Path("data"), state_db_path=Path("var/copilot_state.sqlite3"))
)
driver_id = st.text_input("Driver ID", value="D-LON-001")
message = st.text_area(
    "Manager context",
    value="Maria waited 135 minutes for a 1.5km airport fare. What should we do?",
)
if st.button("Analyse", type="primary"):
    result = copilot.run(
        ChatRequest(
            message=message,
            driver_id=driver_id or None,
            conversation_id=st.session_state.conversation_id,
        )
    )
    st.session_state.conversation_id = result.conversation_id
    st.subheader(result.critic.decision.value)
    st.text(result.manager_message)
    with st.expander("Evidence and policy trace"):
        st.json(result.model_dump(mode="json"))
