import streamlit as st

def render_diff_viewer(diff_text: str, original_code: str, patched_code: str):
    """
    Renders unified diff and side-by-side comparison.
    """
    st.subheader("🔍 Code Patch Inspection")

    tab_diff, tab_side_by_side = st.tabs(["Unified Diff", "Side-by-Side Comparison"])

    with tab_diff:
        if diff_text.strip():
            st.code(diff_text, language="diff")
        else:
            st.info("No modifications detected in diff.")

    with tab_side_by_side:
        col1, col2 = st.columns(2)
        with col1:
            st.markdown("**Original Code (Buggy)**")
            st.code(original_code, language="python")
        with col2:
            st.markdown("**Patched Code (Remediated)**")
            st.code(patched_code, language="python")
