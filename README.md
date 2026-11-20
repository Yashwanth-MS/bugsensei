# 🔧 AutoPatch — Autonomous Software Bug Detection and Repair

> INNOVEDGE Hackathon 2026 · Problem Statement 02

## Scope
**Python projects with pytest only.**
AutoPatch is focused and reliable within this scope.

## What It Does
1. **Upload** a .py file, folder zip, or use a demo project
2. **Scan** using AST analysis, pylint, bandit, and optional Claude AI
3. **Explain** root cause + exact trigger input, not just line numbers
4. **Fix** with minimal diffs only — never rewrites your whole file
5. **Test** in a Docker sandbox with no network and a 30s timeout
6. **Prove** regression safety: shows before/after test counts
7. **Approve** every patch via Accept / Reject / Needs Review buttons

## Run in One Command
```bash
cp .env.example .env        # add your API key (optional)
docker-compose up --build
```
Open: http://localhost:8501

## Without Docker
```bash
cd backend && pip install -r requirements.txt
uvicorn main:app --reload &
cd ../frontend && streamlit run app.py
```

## Demo Projects (try these first)
| Project | Bug Type |
|---|---|
| marks_calculator | Input validation + ZeroDivision |
| divide_app | ZeroDivisionError + mutable default |
| user_auth | Hardcoded password + weak MD5 |
| inventory_tracker | Silent failures + missing edge cases |

## Bug Report Card (matches PS section 05)
Every bug gets: Bug Details · Root Cause · Suggested Patch ·
Test Results · Severity & Confidence · Change History

## Fallback Design
LLM layer is optional. If no API key is set or the call fails,
static analysis (AST + pylint + bandit) + template explanations
run automatically. The demo never breaks.
