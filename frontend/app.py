import streamlit as st
import requests
import json
import os
import io
import zipfile

BACKEND_URL = os.getenv("BACKEND_API_URL", "http://127.0.0.1:8000")

st.set_page_config(
    page_title="AutoPatch",
    page_icon="🔧",
    layout="wide"
)

# ── Header ──────────────────────────────────────────
st.markdown("""
<style>
.bug-card { border-left: 4px solid #e74c3c; padding: 1rem;
            border-radius: 0 8px 8px 0; margin: 1rem 0;
            background: #1a1a2e; }
.severity-critical { border-color: #e74c3c; }
.severity-high     { border-color: #e67e22; }
.severity-medium   { border-color: #f1c40f; }
.severity-low      { border-color: #2ecc71; }
</style>
""", unsafe_allow_html=True)

st.title("🔧 AutoPatch")
st.caption("Autonomous Software Bug Detection and Repair · Python + pytest")

# ── Upload ───────────────────────────────────────────
st.header("1. Upload Your Project")
uploaded = st.file_uploader(
    "Upload a .py file, folder zip, or select a demo project",
    type=["py", "zip"],
    key="uploaded_file_input"
)

demo = st.selectbox(
    "Or try a demo project:",
    options=[
        "None",
        "marks_calculator — input validation bug",
        "divide_app — ZeroDivisionError",
        "user_auth — hardcoded password (security)",
        "inventory_tracker — logic bug + edge case"
    ],
    index=0,
    key="demo_project_dropdown"
)

if st.button("🔍 Scan for Bugs", type="primary"):
    if not uploaded and demo == "None":
        st.warning("Please upload a .py / .zip file or choose a demo project first.")
        st.stop()

    with st.spinner("Scanning... running AST, pylint, bandit, and LLM pass"):
        try:
            if uploaded:
                files = {"file": (uploaded.name, uploaded.read())}
            else:
                demo_name = demo.split(" — ")[0]
                # Look in relative demo directory
                base_dir = os.path.dirname(os.path.abspath(__file__))
                demo_dir = os.path.join(base_dir, "..", "demo_projects", demo_name)
                if not os.path.exists(demo_dir):
                    demo_dir = os.path.join("demo_projects", demo_name)

                # Package demo project directory into an in-memory zip
                if os.path.exists(demo_dir):
                    zip_buffer = io.BytesIO()
                    with zipfile.ZipFile(zip_buffer, "w") as zf:
                        for root, _, filenames in os.walk(demo_dir):
                            for fname in filenames:
                                full_p = os.path.join(root, fname)
                                rel_p = os.path.relpath(full_p, demo_dir)
                                zf.write(full_p, arcname=rel_p)
                    zip_buffer.seek(0)
                    files = {"file": (f"{demo_name}.zip", zip_buffer.getvalue())}
                else:
                    st.error(f"Demo directory '{demo_dir}' not found.")
                    st.stop()

            resp = requests.post(f"{BACKEND_URL}/scan", files=files, timeout=180)
            if resp.status_code == 200:
                result = resp.json()
                st.session_state["bugs"] = result.get("bugs", [])
                st.session_state["total"] = result.get("total", 0)
            else:
                st.error(f"Backend returned error {resp.status_code}: {resp.text}")
        except Exception as e:
            st.error(f"Failed to connect to backend at {BACKEND_URL}: {str(e)}")

# ── Results ──────────────────────────────────────────
if "bugs" in st.session_state:
    bugs = st.session_state["bugs"]
    total = st.session_state["total"]

    # Summary bar
    col1, col2, col3, col4, col5 = st.columns(5)
    col1.metric("Total Bugs", total)
    col2.metric("🤖 LLM Detected",
                sum(1 for b in bugs if b.get("source") == "LLM" or b.get("bug_details", {}).get("source") == "LLM"))
    col3.metric("Critical/High",
                sum(1 for b in bugs if b.get("severity") in ["CRITICAL","HIGH"]))
    col4.metric("Auto-Patchable",
                sum(1 for b in bugs if b.get("suggested_patch", {}).get("patch_method") != "no_change"))
    col5.metric("Regression Safe",
                sum(1 for b in bugs if b.get("test_results", {}).get("regression_safe")))

    st.divider()
    st.header("2. Bug Report Cards")
    st.caption("Sorted by Severity × Confidence")

    for bug in bugs:
        sev = str(bug.get("severity", "MEDIUM")).lower()
        bug_details = bug.get("bug_details", {})
        line_num = bug_details.get("line") or bug_details.get("line_number") or "?"
        confidence = bug.get("confidence", 0.7)
        source = bug.get("source") or bug_details.get("source", "STATIC")

        with st.expander(
            f"[{bug.get('severity')}] [{source}] {bug_details.get('type', 'Bug')} "
            f"· Line {line_num} "
            f"· {bug.get('file', 'file.py')} "
            f"· Confidence {confidence*100:.0f}%",
            expanded=(sev in ["critical","high"])
        ):
            tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
                "🐛 Bug Details",
                "🔍 Root Cause",
                "🩹 Suggested Patch",
                "✅ Test Results",
                "📊 Severity & Confidence",
                "📋 Change History"
            ])

            with tab1:
                st.markdown(f"**Detected by:** `{source}`")
                st.markdown(f"**What went wrong:** {bug_details.get('detail', 'No details provided.')}")
                st.markdown(f"**File:** `{bug.get('file')}` · **Line:** `{line_num}`")

            with tab2:
                st.markdown(f"**Root Cause:** {bug.get('root_cause', 'Unknown')}")
                st.markdown(f"**Trigger Input:** `{bug.get('trigger_input', 'N/A')}`")

            with tab3:
                patch = bug.get("suggested_patch", {})
                if patch.get("diff"):
                    st.code(patch["diff"], language="diff")
                else:
                    st.info("No automatic patch available. Manual review needed.")

            with tab4:
                r = bug.get("test_results", {})
                st.markdown(f"**{r.get('summary', 'No test summary')}**")
                st.markdown(f"Regression safe: {'✅ Yes' if r.get('regression_safe') else '❌ No — patch rejected'}")
                st.markdown("**Test output:**")
                before_out = r.get("before", {}).get("output", "")
                after_out = r.get("after", {}).get("output", "")
                st.markdown("**Before Patch Output:**")
                st.code(before_out if before_out else "No output recorded.")
                if after_out:
                    st.markdown("**After Patch Output:**")
                    st.code(after_out)

                if bug.get("generated_tests"):
                    st.markdown("**Generated test cases:**")
                    st.code(bug["generated_tests"], language="python")

            with tab5:
                st.markdown(f"**Severity:** `{bug.get('severity')}`")
                st.progress(float(confidence))
                st.caption(f"Confidence: {confidence*100:.0f}%")

            with tab6:
                st.markdown(f"**Current Status:** `{bug.get('status')}`")

            # ── Human Approval Buttons ──────────────────
            st.divider()
            st.markdown("**Developer Decision:**")
            c1, c2, c3 = st.columns(3)

            bug_id = bug.get("id", "BUG-000")
            if c1.button(f"✅ Accept", key=f"acc_{bug_id}"):
                requests.post(f"{BACKEND_URL}/decision/{bug_id}",
                              json={"action": "ACCEPTED"})
                st.success("Patch accepted and logged.")

            if c2.button(f"❌ Reject", key=f"rej_{bug_id}"):
                requests.post(f"{BACKEND_URL}/decision/{bug_id}",
                              json={"action": "REJECTED"})
                st.warning("Patch rejected.")

            if c3.button(f"🔎 Needs Review", key=f"rev_{bug_id}"):
                requests.post(f"{BACKEND_URL}/decision/{bug_id}",
                              json={"action": "NEEDS_REVIEW"})
                st.info("Flagged for review.")

# ── Audit Log ────────────────────────────────────────
st.divider()
if st.button("📋 Show Audit Log"):
    try:
        resp = requests.get(f"{BACKEND_URL}/history")
        if resp.status_code == 200:
            history = resp.json().get("history", [])
            if history:
                st.json(history)
            else:
                st.info("No decisions recorded yet.")
        else:
            st.error(f"Error fetching history: {resp.status_code}")
    except Exception as e:
        st.error(f"Could not reach backend: {str(e)}")
