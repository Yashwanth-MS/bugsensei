import streamlit as st

def render_bug_card(bug: dict, on_patch_click=None, index: int = 0):
    """
    Renders the Bug Report Card (PS section 05) with severity styling,
    originating line, tool, and remediation options.
    """
    severity = bug.get("severity", "medium").lower()
    color_map = {
        "critical": "🔴",
        "high": "🟠",
        "medium": "🟡",
        "low": "🔵",
        "info": "⚪"
    }
    badge = color_map.get(severity, "🟡")

    with st.container():
        st.markdown(
            f"""
            <div style="border: 1px solid #444; border-radius: 8px; padding: 12px; margin-bottom: 12px; background-color: #1e1e1e;">
                <div style="display: flex; justify-content: space-between; align-items: center;">
                    <h4 style="margin: 0; color: #f0f0f0;">{badge} [{bug.get('id', 'BUG')}] {bug.get('title', 'Unknown Issue')}</h4>
                    <span style="font-size: 12px; background: #333; padding: 2px 8px; border-radius: 4px; color: #ddd;">
                        {bug.get('source_tool', 'tool').upper()} | Line {bug.get('line_number', 'N/A')}
                    </span>
                </div>
                <p style="margin-top: 8px; color: #bbb; font-size: 14px;">{bug.get('description', '')}</p>
                {f'<p style="color: #4CAF50; font-size: 13px;"><strong>💡 Suggested Remedy:</strong> {bug.get("suggested_fix")}</p>' if bug.get("suggested_fix") else ''}
            </div>
            """,
            unsafe_allow_html=True
        )
        if on_patch_click:
            if st.button(f"Generate Patch for {bug.get('id')}", key=f"patch_btn_{index}"):
                on_patch_click(bug)
