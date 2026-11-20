import subprocess
import json
import os
import sys
import tempfile

def run_pylint(filepath: str) -> list:
    """Run pylint and return structured findings."""
    temp_file = None
    if "\n" in filepath or not os.path.exists(filepath):
        fd, temp_file = tempfile.mkstemp(suffix=".py")
        os.close(fd)
        with open(temp_file, "w", encoding="utf-8") as f:
            f.write(filepath)
        target = temp_file
    else:
        target = filepath

    try:
        # Fast targeted pylint check
        cmd = [
            sys.executable, "-m", "pylint", target,
            "--output-format=json",
            "--score=no",
            "--disable=all",
            "--enable=E,F,W0102,W0702,W0611",
            "--persistent=no"
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=3)
        issues = json.loads(result.stdout) if result.stdout.strip() else []
        return [{
            "type": f"Pylint:{i['symbol']}",
            "line": i["line"],
            "detail": i["message"],
            "severity": _map_pylint_severity(i["type"]),
            "confidence": 0.85,
            "root_cause": f"Pylint rule violation: {i['symbol']}",
            "trigger_input": "Static analysis — no specific input needed."
        } for i in issues]
    except Exception:
        return []
    finally:
        if temp_file and os.path.exists(temp_file):
            try:
                os.remove(temp_file)
            except OSError:
                pass

def run_bandit(filepath: str) -> list:
    """Run bandit security scanner."""
    temp_file = None
    if "\n" in filepath or not os.path.exists(filepath):
        fd, temp_file = tempfile.mkstemp(suffix=".py")
        os.close(fd)
        with open(temp_file, "w", encoding="utf-8") as f:
            f.write(filepath)
        target = temp_file
    else:
        target = filepath

    try:
        cmd = [sys.executable, "-m", "bandit", "-f", "json", target]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
        data = json.loads(result.stdout) if result.stdout.strip() else {}
        return [{
            "type": f"Security:{r['test_id']}",
            "line": r["line_number"],
            "detail": r["issue_text"],
            "severity": r["issue_severity"],
            "confidence": _map_bandit_confidence(r["issue_confidence"]),
            "root_cause": r["issue_text"],
            "trigger_input": "Security vulnerability — review immediately."
        } for r in data.get("results", [])]
    except Exception:
        return []
    finally:
        if temp_file and os.path.exists(temp_file):
            try:
                os.remove(temp_file)
            except OSError:
                pass

def _map_pylint_severity(t):
    return {"E": "HIGH", "W": "MEDIUM", "C": "LOW", "R": "LOW"}.get(t, "LOW")

def _map_bandit_confidence(c):
    return {"HIGH": 0.9, "MEDIUM": 0.7, "LOW": 0.5}.get(c, 0.6)
