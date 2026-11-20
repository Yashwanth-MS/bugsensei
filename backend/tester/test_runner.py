import subprocess
import os
import sys
import json
import time
import tempfile
import shutil
from models import TestRunResponse

def run_tests(project_path: str, timeout: int = 10) -> dict:
    """
    Runs pytest inside the project folder using the active Python interpreter.
    Runs with cwd=project_path and --rootdir=. to prevent pytest from traversing
    the parent temp directory.
    """
    report_file = os.path.join(project_path, ".pytest_report.json")

    cmd = [
        sys.executable, "-m", "pytest", ".",
        "--rootdir=.",
        "--tb=short", "-q",
        "--json-report", f"--json-report-file={report_file}"
    ]

    try:
        result = subprocess.run(
            cmd,
            cwd=project_path,
            capture_output=True,
            text=True,
            timeout=timeout
        )
        if "unrecognized arguments: --json-report" in (result.stderr or ""):
            result = subprocess.run(
                [sys.executable, "-m", "pytest", ".", "--rootdir=.", "--tb=short", "-q"],
                cwd=project_path,
                capture_output=True,
                text=True,
                timeout=timeout
            )
    except Exception as e:
        return {
            "passed": 0,
            "failed": 0,
            "errors": 1,
            "total": 0,
            "output": f"Pytest execution error: {str(e)}",
            "success": False
        }

    try:
        if os.path.exists(report_file):
            with open(report_file, "r", encoding="utf-8") as f:
                report = json.load(f)
            summary = report.get("summary", {})
            try:
                os.remove(report_file)
            except OSError:
                pass
            return {
                "passed": summary.get("passed", 0),
                "failed": summary.get("failed", 0),
                "errors": summary.get("errors", 0),
                "total": summary.get("total", 0),
                "output": result.stdout or result.stderr,
                "success": result.returncode == 0
            }
    except Exception:
        pass

    # Fallback: parse stdout
    out = (result.stdout or "") + "\n" + (result.stderr or "")
    return {
        "passed": out.count(" passed"),
        "failed": out.count(" failed"),
        "errors": out.count(" error"),
        "total": out.count(" passed") + out.count(" failed"),
        "output": out.strip(),
        "success": result.returncode == 0
    }

def run_in_sandbox(project_path: str) -> dict:
    """
    Runs tests in sandbox. Falls back to direct Python pytest run with cwd isolated.
    Skips Docker and runs direct pytest cleanly when SANDBOX_ENABLED=false.
    """
    sandbox_enabled = os.getenv("SANDBOX_ENABLED", "true").strip().lower() not in ("false", "0", "no")
    if sandbox_enabled and shutil.which("docker"):
        try:
            clean_path = os.path.abspath(project_path).replace("\\", "/")
            result = subprocess.run([
                "docker", "run", "--rm",
                "--network=none",
                "--memory=256m",
                "--cpus=0.5",
                "-v", f"{clean_path}:/code",
                "autopatch-sandbox",
                "pytest", "/code", "-q", "--tb=short"
            ], capture_output=True, text=True, timeout=10)

            if result.returncode in [0, 1]:
                return {
                    "output": result.stdout or result.stderr,
                    "success": result.returncode == 0,
                    "sandbox": True
                }
        except Exception:
            pass

    return run_tests(project_path)

def run_tests_docker_or_local(
    code: str,
    test_code: str,
    filename: str = "app.py",
    test_filename: str = "test_app.py"
) -> TestRunResponse:
    start_time = time.time()
    with tempfile.TemporaryDirectory() as temp_dir:
        code_file = os.path.join(temp_dir, filename)
        test_file = os.path.join(temp_dir, test_filename)

        with open(code_file, "w", encoding="utf-8") as f:
            f.write(code)
        with open(test_file, "w", encoding="utf-8") as f:
            f.write(test_code)

        res = run_in_sandbox(temp_dir)
        duration = round(time.time() - start_time, 2)

        return TestRunResponse(
            passed=res.get("success", False),
            summary="Tests passed successfully." if res.get("success") else "Tests failed.",
            raw_output=res.get("output", ""),
            duration_seconds=duration
        )
