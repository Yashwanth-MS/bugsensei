import os
import json
import re
import ssl
import httpx
import requests
import urllib3
from dotenv import load_dotenv

# Suppress SSL verification warnings for corporate/university proxies
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# Robust .env loader: search current, parent, and workspace root directories
load_dotenv()
for dir_path in [
    os.path.dirname(os.path.abspath(__file__)),
    os.path.abspath(os.path.join(os.path.dirname(__file__), "..")),
    r"C:\Users\YASWANTH M S\Downloads\BUGSENSEI"
]:
    env_file = os.path.join(dir_path, ".env")
    if os.path.exists(env_file):
        load_dotenv(env_file, override=False)

# ─────────────────────────────────────────────
# PROMPT BUILDER  (shared across all providers)
# ─────────────────────────────────────────────

def build_scan_prompt(source_code: str, filename: str) -> str:
    return f"""You are an expert Python bug detector for a tool called BugSensei.
Analyze the code below and return ONLY valid JSON — no markdown, no explanation, no backticks.

Return a JSON array in exactly this format:
[
  {{
    "type": "BugTypeName",
    "line": 12,
    "detail": "clear description of what is wrong",
    "root_cause": "why this bug happens technically",
    "trigger_input": "exact input or condition that causes the bug",
    "severity": "CRITICAL|HIGH|MEDIUM|LOW",
    "confidence": 0.85,
    "suggested_fix": "one sentence description of the fix"
  }}
]

Rules:
- Return [] if no bugs found
- Keep descriptions concise (under 20 words each) so JSON is never truncated
- severity must be one of: CRITICAL, HIGH, MEDIUM, LOW
- confidence must be a float between 0.0 and 1.0
- Do NOT return markdown, do NOT wrap in backticks
- Focus on logic bugs that static tools miss

File: {filename}

```python
{source_code}
```"""


def build_patch_prompt(source_code: str, bug: dict) -> str:
    return f"""You are an expert Python developer for BugSensei.
Generate a minimal patch for this bug. Return ONLY the fixed Python code, nothing else.
Do not rewrite the whole file. Change only the minimum lines needed.

Bug type: {bug.get('type')}
Bug at line: {bug.get('line')}
Root cause: {bug.get('root_cause')}
Suggested fix: {bug.get('suggested_fix')}

Original code:
```python
{source_code}
```

Return ONLY the fixed Python code."""


def build_test_prompt(source_code: str, bug: dict, filename: str) -> str:
    return f"""You are an expert Python tester for BugSensei.
Write pytest test cases that:
1. Reproduce the bug (should FAIL before patch)
2. Verify the fix (should PASS after patch)

Return ONLY valid Python pytest code, no explanation, no markdown.

Bug type: {bug.get('type')}
Trigger input: {bug.get('trigger_input')}
File: {filename}

Code:
```python
{source_code}
```"""


# ─────────────────────────────────────────────
# SAFE JSON PARSER
# ─────────────────────────────────────────────

def safe_parse_json(text: str) -> list:
    """
    Cleans LLM output and parses JSON safely.
    Handles:
    - Markdown code fences (```json ... ``` or ``` ...)
    - Direct JSON arrays: [...]
    - JSON objects wrapping lists: {"bugs": [...]}, {"data": [...]}, etc.
    - Single JSON object: {...}
    - Missing or malformed fields normalized with defaults
    """
    if not text or not isinstance(text, str):
        return []

    # 1. Clean markdown code fences and whitespace
    cleaned = re.sub(r"^```(?:json|python)?\s*", "", text.strip(), flags=re.MULTILINE)
    cleaned = re.sub(r"```\s*$", "", cleaned.strip(), flags=re.MULTILINE)
    cleaned = cleaned.strip("` \n\r\t")

    raw_items = []

    # Try 2. Full direct JSON parse first
    try:
        parsed = json.loads(cleaned)
        if isinstance(parsed, list):
            raw_items = parsed
        elif isinstance(parsed, dict):
            # Check if any value is a list of dicts (e.g. {"bugs": [...]})
            for val in parsed.values():
                if isinstance(val, list) and val and isinstance(val[0], dict):
                    raw_items = val
                    break
            if not raw_items:
                # Might be a single bug object e.g. {"type": "...", "line": 2}
                if any(k in parsed for k in ["type", "line", "detail", "description"]):
                    raw_items = [parsed]
    except Exception:
        pass

    # Try 3. Extract JSON array substring [ ... ]
    if not raw_items:
        start_arr = cleaned.find("[")
        end_arr   = cleaned.rfind("]")
        if start_arr != -1 and end_arr > start_arr:
            try:
                candidate = cleaned[start_arr:end_arr+1]
                # Fix potential trailing commas before ] or }
                candidate = re.sub(r",\s*([\]}])", r"\1", candidate)
                parsed = json.loads(candidate)
                if isinstance(parsed, list):
                    raw_items = parsed
            except Exception:
                pass

        # Truncation recovery: if array was cut off by token limit, trim back to the last complete '}'
        if not raw_items and start_arr != -1:
            last_brace = cleaned.rfind("}")
            if last_brace > start_arr:
                try:
                    candidate = cleaned[start_arr:last_brace+1] + "\n]"
                    candidate = re.sub(r",\s*([\]}])", r"\1", candidate)
                    parsed = json.loads(candidate)
                    if isinstance(parsed, list):
                        raw_items = parsed
                except Exception:
                    pass

    # Try 4. Extract JSON object substring { ... }
    if not raw_items:
        start_obj = cleaned.find("{")
        end_obj   = cleaned.rfind("}")
        if start_obj != -1 and end_obj > start_obj:
            try:
                candidate = cleaned[start_obj:end_obj+1]
                candidate = re.sub(r",\s*([\]}])", r"\1", candidate)
                parsed = json.loads(candidate)
                if isinstance(parsed, dict):
                    for val in parsed.values():
                        if isinstance(val, list) and val and isinstance(val[0], dict):
                            raw_items = val
                            break
                    if not raw_items and any(k in parsed for k in ["type", "line", "detail", "description"]):
                        raw_items = [parsed]
            except Exception:
                pass

    # Try 5. Regex individual complete JSON objects if array parsing failed
    if not raw_items:
        matches = re.finditer(r"\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}", cleaned, flags=re.DOTALL)
        for m in matches:
            try:
                obj_cand = re.sub(r",\s*([\]}])", r"\1", m.group(0))
                obj = json.loads(obj_cand)
                if isinstance(obj, dict) and any(k in obj for k in ["type", "line", "detail", "description"]):
                    raw_items.append(obj)
            except Exception:
                pass

    # 5. Normalize items with defaults so nothing gets dropped
    valid_items = []
    for item in raw_items:
        if not isinstance(item, dict):
            continue
        try:
            line_val = item.get("line") or item.get("line_number") or item.get("lineno") or 1
            try:
                line_int = int(line_val)
            except (ValueError, TypeError):
                line_int = 1

            conf_val = item.get("confidence", 0.85)
            try:
                conf_float = max(0.0, min(1.0, float(conf_val)))
            except (ValueError, TypeError):
                conf_float = 0.85

            sev = str(item.get("severity") or "MEDIUM").strip().upper()
            if sev not in {"CRITICAL", "HIGH", "MEDIUM", "LOW"}:
                sev = "MEDIUM"

            valid_items.append({
                "type": str(item.get("type") or item.get("name") or item.get("bug_type") or item.get("function_name") or "LogicBug").strip(),
                "line": line_int,
                "detail": str(item.get("detail") or item.get("description") or item.get("message") or "Potential logic issue detected.").strip(),
                "root_cause": str(item.get("root_cause") or item.get("reason") or item.get("cause") or item.get("notes") or "Logic edge case.").strip(),
                "trigger_input": str(item.get("trigger_input") or item.get("input") or "Edge case input.").strip(),
                "severity": sev,
                "confidence": conf_float,
                "suggested_fix": str(item.get("suggested_fix") or item.get("fix") or "Review and handle condition.").strip(),
                "source": "LLM"
            })
        except Exception:
            continue

    return valid_items


# ─────────────────────────────────────────────
# PROVIDER 1 — GROQ (Fastest - 0.5s response)
# ─────────────────────────────────────────────

def _groq_call(prompt: str) -> str | None:
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        return None
    try:
        import time
        from groq import Groq
        client = Groq(
            api_key=api_key,
            timeout=8.0,
            http_client=httpx.Client(verify=False)
        )
        for model in ["qwen/qwen3.8-27b", "openai/gpt-oss-120b"]:
            for attempt in range(2):
                try:
                    response = client.chat.completions.create(
                        model=model,
                        messages=[{"role": "user", "content": prompt}],
                        temperature=0.1,
                        max_tokens=450,
                    )
                    if response.choices and response.choices[0].message.content:
                        text = response.choices[0].message.content.strip()
                        if text:
                            return text
                except Exception as me:
                    err_str = str(me)
                    if "429" in err_str and attempt == 0:
                        time.sleep(1.0)
                        continue
                    break
        return None
    except Exception as e:
        print(f"[BugSensei] Groq skipped/failed → {e}")
        return None


# ─────────────────────────────────────────────
# PROVIDER 2 — GOOGLE GEMINI
# ─────────────────────────────────────────────

def _gemini_call(prompt: str) -> str | None:
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        return None

    # Direct REST with verify=False (fast, bypasses SSL/gRPC blocks)
    for model_name in ["gemini-3.8-flash", "gemini-flash-latest"]:
        try:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={api_key}"
            payload = {
                "contents": [{"parts": [{"text": prompt}]}],
                "generationConfig": {"temperature": 0.1, "maxOutputTokens": 450}
            }
            resp = requests.post(
                url,
                json=payload,
                headers={"Content-Type": "application/json"},
                timeout=3.0,
                verify=False
            )
            if resp.status_code == 200:
                data = resp.json()
                candidates = data.get("candidates", [])
                if candidates:
                    parts = candidates[0].get("content", {}).get("parts", [])
                    if parts and "text" in parts[0]:
                        return parts[0]["text"]
        except Exception:
            continue

    return None


# ─────────────────────────────────────────────
# PROVIDER 3 — OPENROUTER (Fallback)
# ─────────────────────────────────────────────

def _openrouter_call(prompt: str) -> str | None:
    api_key = os.getenv("OPENROUTER_API_KEY")
    if not api_key:
        return None
    try:
        response = requests.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
                "HTTP-Referer": "https://bugsensai.app",
                "X-Title": "BugSensei"
            },
            json={
                "model": "openrouter/auto",
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.1,
                "max_tokens": 800,
            },
            timeout=3.0
        )
        response.raise_for_status()
        data = response.json()
        if "choices" in data and data["choices"]:
            return data["choices"][0]["message"]["content"]
        return None
    except Exception as e:
        print(f"[BugSensei] OpenRouter skipped/failed → {e}")
        return None


# ─────────────────────────────────────────────
# FALLBACK CHAIN — Groq (fastest) → Gemini → OpenRouter
# ─────────────────────────────────────────────

def llm_call(prompt: str) -> str | None:
    """
    Master fallback chain:
    Groq (sub-second) → Gemini → OpenRouter → None (static analysis takes over)
    """
    for provider_name, fn in [
        ("Groq",        _groq_call),
        ("OpenRouter",  _openrouter_call),
        ("Gemini",      _gemini_call),
    ]:
        try:
            result = fn(prompt)
            if result:
                print(f"[BugSensei] ✅ {provider_name} responded")
                return result
        except Exception:
            pass
        print(f"[BugSensei] ⚠️  {provider_name} skipped/failed")

    print("[BugSensei] ℹ️  All LLM providers unavailable — static analysis only")
    return None


# ─────────────────────────────────────────────
# PUBLIC FUNCTIONS  (imported by scanner/patcher/tester)
# ─────────────────────────────────────────────

def llm_scan(source_code: str, filename: str) -> list:
    """LLM bug detection — falls back to [] gracefully with detailed diagnostics."""
    prompt = build_scan_prompt(source_code, filename)
    raw    = llm_call(prompt)
    if not raw:
        print(f"[BugSensei] [llm_scan] No LLM response returned for {filename}")
        return []

    parsed = safe_parse_json(raw)
    print(f"[BugSensei] [llm_scan] Raw response length: {len(raw)} chars | Parsed bugs: {len(parsed)}")
    if parsed:
        for b in parsed:
            print(f"   ↳ [LLM Bug] Line {b.get('line')} [{b.get('type')}] - {b.get('detail')[:60]}...")
    else:
        print(f"[BugSensei] [llm_scan] ⚠️ Parsed 0 bugs from raw LLM output: {raw[:200]!r}")
    return parsed


def llm_patch(source_code: str, bug: dict) -> str | None:
    """LLM patch generation — returns fixed code or None."""
    prompt = build_patch_prompt(source_code, bug)
    return llm_call(prompt)


def llm_generate_tests(source_code: str, bug: dict, filename: str) -> str | None:
    """LLM test generation — returns pytest code or None."""
    prompt = build_test_prompt(source_code, bug, filename)
    return llm_call(prompt)
