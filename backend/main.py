from fastapi import FastAPI, UploadFile, File
from fastapi.responses import FileResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from pathlib import Path
import tempfile, os, json, zipfile, shutil
from datetime import datetime
from typing import List, Dict, Optional
from dotenv import load_dotenv

load_dotenv()
load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))
load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

from scanner.ast_checker import ASTChecker
from scanner.lint_runner import run_pylint, run_bandit
from scanner.llm_scanner import llm_scan
from patcher.diff_maker import generate_patch
from tester.test_runner import run_in_sandbox
from tester.test_generator import generate_tests

app = FastAPI(title="AutoPatch API")

app.add_middleware(CORSMiddleware, allow_origins=["*"],
                   allow_methods=["*"], allow_headers=["*"])

REPORTS_DIR = Path(__file__).resolve().parent / "reports"
REPORTS_DIR.mkdir(parents=True, exist_ok=True)
CHANGE_LOG_PATH = str(REPORTS_DIR / "change_history.json")

@app.get("/")
def landing_page():
    landing_file = Path(__file__).resolve().parent.parent / "frontend" / "landing" / "index.html"
    if landing_file.exists():
        return FileResponse(str(landing_file), media_type="text/html")
    return {"message": "Landing page not found", "dashboard": "/dashboard"}

@app.get("/green_vortex.jpg")
def green_vortex_img():
    gv_file = Path(__file__).resolve().parent.parent / "frontend" / "landing" / "green_vortex.jpg"
    if gv_file.exists():
        return FileResponse(str(gv_file), media_type="image/jpeg")
    return {"message": "Image not found"}

dashboard_dist = Path(__file__).resolve().parent.parent / "frontend" / "dashboard" / "dist"
dashboard_assets = dashboard_dist / "assets"

# Serve root assets directly so both relative and absolute Vite asset requests succeed
if dashboard_assets.exists():
    app.mount("/assets", StaticFiles(directory=str(dashboard_assets)), name="assets")

# Serve /dashboard directly or redirect
@app.get("/dashboard")
def dashboard_view():
    index_file = dashboard_dist / "index.html"
    if index_file.exists():
        return FileResponse(str(index_file), media_type="text/html")
    return RedirectResponse(url="/dashboard/", status_code=307)

if dashboard_dist.exists():
    app.mount("/dashboard", StaticFiles(directory=str(dashboard_dist), html=True), name="dashboard")

@app.get("/health")
def health_check():
    return {
        "status": "ok",
        "service": "BugSensei",
        "timestamp": datetime.utcnow().isoformat(),
        "dashboard_url": "/dashboard",
        "engine": "AST + Pylint + Bandit + 3-Tier LLM + Docker Sandbox"
    }

@app.post("/scan")
async def scan_project(file: UploadFile = File(...)):
    """
    Main pipeline: Upload → Scan → Explain → Patch → Test
    """
    # 1. Save uploaded file/zip
    with tempfile.TemporaryDirectory() as tmpdir:
        file_path = os.path.join(tmpdir, file.filename)
        with open(file_path, "wb") as f:
            f.write(await file.read())

        # Unzip if needed
        if file.filename.endswith(".zip"):
            with zipfile.ZipFile(file_path, "r") as z:
                z.extractall(tmpdir)

        # 2. Find all Python application files (excluding test files)
        py_files = []
        for root, _, files in os.walk(tmpdir):
            for fname in files:
                if fname.endswith(".py") and not fname.startswith("test_") and not fname.endswith("_test.py"):
                    py_files.append(os.path.join(root, fname))

        # Fallback if only test files were uploaded
        if not py_files:
            for root, _, files in os.walk(tmpdir):
                for fname in files:
                    if fname.endswith(".py"):
                        py_files.append(os.path.join(root, fname))

        all_bugs = []

        for py_file in py_files:
            with open(py_file, "r", encoding="utf-8", errors="ignore") as f:
                source = f.read()

            fname = os.path.basename(py_file)

            # 3. Run all scanners
            ast_bugs  = ASTChecker(source, fname).check()
            lint_bugs = run_pylint(py_file)
            sec_bugs  = run_bandit(py_file)
            llm_bugs  = llm_scan(source, fname)  # optional, falls back to []

            # Tag each bug with its origin source
            for b in ast_bugs:
                b["source"] = "AST"
            for b in lint_bugs:
                b["source"] = "Pylint"
            for b in sec_bugs:
                b["source"] = "Bandit"
            for b in llm_bugs:
                b["source"] = "LLM"

            bugs = ast_bugs + lint_bugs + sec_bugs + llm_bugs

            # 4. Deduplicate without dropping distinct findings
            seen = set()
            unique_bugs = []
            for b in bugs:
                key = (b.get("line"), str(b.get("type", "")).strip().lower(), b.get("source", ""))
                if key not in seen:
                    seen.add(key)
                    unique_bugs.append(b)

            # 5. Run tests before patch (once per file for speed)
            before = run_in_sandbox(tmpdir)

            # 6. Generate patches + tests for each bug
            for bug in unique_bugs:
                try:
                    patch = generate_patch(source, bug)
                except Exception as pe:
                    patch = {"original": source, "patched": source, "diff": "", "patch_method": "no_change"}

                try:
                    tests = generate_tests(source, bug, fname)
                except Exception:
                    tests = ""

                # Apply patch and run tests to verify
                try:
                    patched_code = patch.get("patched", source)
                    if patched_code != source:
                        with open(py_file, "w", encoding="utf-8") as f:
                            f.write(patched_code)
                        after = run_in_sandbox(tmpdir)
                    else:
                        after = before
                except Exception:
                    after = before

                # Reject patch if it breaks existing tests
                patch_safe = (after.get("success", False) or
                              after.get("passed", 0) >= before.get("passed", 0))

                # Restore original if patch breaks tests or for next bug check
                with open(py_file, "w", encoding="utf-8") as f:
                    f.write(source)

                bug_report = {
                    "id": f"BUG-{len(all_bugs)+1:03d}",
                    "source": bug.get("source", "AST"),
                    "file": fname,
                    "bug_details": bug,
                    "root_cause": bug.get("root_cause", "See details"),
                    "trigger_input": bug.get("trigger_input", ""),
                    "suggested_patch": patch,
                    "test_results": {
                        "before": before,
                        "after": after,
                        "regression_safe": patch_safe,
                        "summary": f"{before.get('passed',0)} passed before → {after.get('passed',0)} passed after"
                    },
                    "severity": bug.get("severity", "MEDIUM"),
                    "confidence": bug.get("confidence", 0.7),
                    "generated_tests": tests,
                    "status": "NEEDS_REVIEW",
                    "timestamp": datetime.utcnow().isoformat()
                }
                all_bugs.append(bug_report)

        # 7. Sort by severity × confidence (prioritization)
        severity_map = {"CRITICAL": 4, "HIGH": 3, "MEDIUM": 2, "LOW": 1}
        all_bugs.sort(
            key=lambda b: severity_map.get(b["severity"], 1) * b.get("confidence", 0.5),
            reverse=True
        )

        return {"bugs": all_bugs, "total": len(all_bugs)}


@app.post("/decision/{bug_id}")
async def record_decision(bug_id: str, decision: dict):
    """Accept / Reject / Needs Review — saves to audit log."""
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    log = []
    if os.path.exists(CHANGE_LOG_PATH):
        try:
            with open(CHANGE_LOG_PATH, "r", encoding="utf-8") as f:
                log = json.load(f)
        except Exception:
            log = []

    log.append({
        "bug_id": bug_id,
        "decision": decision.get("action"),  # ACCEPTED / REJECTED / NEEDS_REVIEW
        "note": decision.get("note", ""),
        "timestamp": datetime.utcnow().isoformat()
    })

    with open(CHANGE_LOG_PATH, "w", encoding="utf-8") as f:
        json.dump(log, f, indent=2)

    return {"status": "saved"}


@app.get("/history")
async def get_history():
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    if not os.path.exists(CHANGE_LOG_PATH):
        return {"history": []}
    try:
        with open(CHANGE_LOG_PATH, "r", encoding="utf-8") as f:
            return {"history": json.load(f)}
    except Exception:
        return {"history": []}


# --- Additional helper endpoints for demo projects and direct code testing ---

class DirectScanRequest(BaseModel):
    code: str
    filename: Optional[str] = "app.py"
    test_code: Optional[str] = ""

@app.post("/scan/code")
async def scan_code_direct(req: DirectScanRequest):
    """Scan raw code without file upload."""
    with tempfile.TemporaryDirectory() as tmpdir:
        file_path = os.path.join(tmpdir, req.filename)
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(req.code)

        if req.test_code:
            test_path = os.path.join(tmpdir, f"test_{req.filename}")
            with open(test_path, "w", encoding="utf-8") as f:
                f.write(req.test_code)

        source = req.code
        fname = req.filename

        ast_bugs  = ASTChecker(source, fname).check()
        lint_bugs = run_pylint(file_path)
        sec_bugs  = run_bandit(file_path)
        llm_bugs  = llm_scan(source, fname)

        # Tag each bug with its origin source
        for b in ast_bugs:
            b["source"] = "AST"
        for b in lint_bugs:
            b["source"] = "Pylint"
        for b in sec_bugs:
            b["source"] = "Bandit"
        for b in llm_bugs:
            b["source"] = "LLM"

        bugs = ast_bugs + lint_bugs + sec_bugs + llm_bugs

        seen = set()
        unique_bugs = []
        for b in bugs:
            key = (b.get("line"), str(b.get("type", "")).strip().lower(), b.get("source", ""))
            if key not in seen:
                seen.add(key)
                unique_bugs.append(b)

        all_bugs = []
        for bug in unique_bugs:
            try:
                patch = generate_patch(source, bug)
            except Exception:
                patch = {"original": source, "patched": source, "diff": "", "patch_method": "no_change"}

            try:
                tests = generate_tests(source, bug, fname)
            except Exception:
                tests = ""

            before = run_in_sandbox(tmpdir)
            try:
                patched_code = patch.get("patched", source)
                if patched_code != source:
                    with open(file_path, "w", encoding="utf-8") as f:
                        f.write(patched_code)
                    after = run_in_sandbox(tmpdir)
                else:
                    after = before
            except Exception:
                after = before

            patch_safe = (after.get("success", False) or
                          after.get("passed", 0) >= before.get("passed", 0))

            # Always restore original file for next bug evaluation
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(source)

            bug_report = {
                "id": f"BUG-{len(all_bugs)+1:03d}",
                "source": bug.get("source", "AST"),
                "file": fname,
                "bug_details": bug,
                "root_cause": bug.get("root_cause", "See details"),
                "trigger_input": bug.get("trigger_input", ""),
                "suggested_patch": patch,
                "test_results": {
                    "before": before,
                    "after": after,
                    "regression_safe": patch_safe,
                    "summary": f"{before.get('passed',0)} passed before → {after.get('passed',0)} passed after"
                },
                "severity": bug.get("severity", "MEDIUM"),
                "confidence": bug.get("confidence", 0.7),
                "generated_tests": tests,
                "status": "NEEDS_REVIEW",
                "timestamp": datetime.utcnow().isoformat()
            }
            all_bugs.append(bug_report)

        severity_map = {"CRITICAL": 4, "HIGH": 3, "MEDIUM": 2, "LOW": 1}
        all_bugs.sort(
            key=lambda b: severity_map.get(b["severity"], 1) * b.get("confidence", 0.5),
            reverse=True
        )

        return {"bugs": all_bugs, "total": len(all_bugs)}


@app.get("/demo-projects")
def list_demo_projects() -> List[Dict]:
    projects_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "demo_projects"))
    if not os.path.exists(projects_dir):
        return []

    results = []
    for item in os.listdir(projects_dir):
        proj_path = os.path.join(projects_dir, item)
        if os.path.isdir(proj_path):
            main_code = ""
            test_code = ""
            code_file = os.path.join(proj_path, "main.py")
            t_file = os.path.join(proj_path, "test_main.py")

            if os.path.exists(code_file):
                with open(code_file, "r", encoding="utf-8") as f:
                    main_code = f.read()
            if os.path.exists(t_file):
                with open(t_file, "r", encoding="utf-8") as f:
                    test_code = f.read()

            results.append({
                "id": item,
                "name": item.replace("_", " ").title(),
                "path": proj_path,
                "main_code": main_code,
                "test_code": test_code
            })
    return results


class ApplyPatchesRequest(BaseModel):
    code: str
    filename: Optional[str] = "app.py"
    accepted_bugs: List[Dict] = []

@app.post("/apply-patches")
async def apply_patches_endpoint(req: ApplyPatchesRequest):
    """
    Applies accepted bug patches to code, validates in sandbox, and returns fixed code.
    """
    current_code = req.code
    applied_count = 0
    applied_bugs = []

    # Sort bugs by line descending if line is available to prevent offset shifts
    sorted_bugs = sorted(
        req.accepted_bugs,
        key=lambda b: (b.get("bug_details", {}).get("line") or b.get("line") or 0),
        reverse=True
    )

    for b in sorted_bugs:
        patch_info = b.get("suggested_patch") or {}
        orig_snippet = patch_info.get("original", "").strip()
        patched_snippet = patch_info.get("patched", "").strip()

        # 1. Try snippet replacement
        if orig_snippet and patched_snippet and orig_snippet != patched_snippet:
            if orig_snippet in current_code:
                current_code = current_code.replace(orig_snippet, patched_snippet, 1)
                applied_count += 1
                applied_bugs.append(b.get("id"))
            else:
                # Normalize line endings and whitespace for fuzzy match
                matched = False
                for orig_line in orig_snippet.splitlines():
                    if orig_line.strip() and orig_line.strip() in current_code:
                        matched = True
                        break
                if matched and len(sorted_bugs) == 1:
                    current_code = patch_info.get("patched", current_code)
                    applied_count += 1
                    applied_bugs.append(b.get("id"))

    # Fallback if only 1 bug accepted and snippet match failed
    if applied_count == 0 and len(sorted_bugs) == 1:
        single_patch = sorted_bugs[0].get("suggested_patch", {}).get("patched")
        if single_patch and single_patch != current_code:
            current_code = single_patch
            applied_count = 1
            applied_bugs.append(sorted_bugs[0].get("id"))

    # Validate in sandbox
    with tempfile.TemporaryDirectory() as tmpdir:
        file_path = os.path.join(tmpdir, req.filename)
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(current_code)
        test_res = run_in_sandbox(tmpdir)

    return {
        "status": "success",
        "fixed_code": current_code,
        "applied_count": applied_count,
        "applied_bugs": applied_bugs,
        "filename": req.filename,
        "sandbox_test": test_res
    }

