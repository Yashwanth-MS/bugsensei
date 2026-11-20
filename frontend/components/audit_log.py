import streamlit as st

def render_audit_log_panel(audit_logs: list):
    """
    Renders audit logs and change history panel.
    """
    st.subheader("📜 Audit Log & Change History")

    if not audit_logs:
        st.info("No audit entries recorded yet.")
        return

    for entry in audit_logs:
        timestamp = entry.get("timestamp", "N/A")
        project = entry.get("project_or_file", "General")
        action = entry.get("action", "Action")
        details = entry.get("details", {})

        with st.expander(f"🕒 {timestamp} - {action.upper()} ({project})"):
            st.json(details)
