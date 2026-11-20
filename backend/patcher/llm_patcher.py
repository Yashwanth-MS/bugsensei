try:
    from llm.provider import llm_patch
except ImportError:
    from backend.llm.provider import llm_patch
from patcher.diff_maker import generate_unified_diff, generate_patch as generate_rule_patch

def generate_patch(
    original_code: str,
    filename: str = "app.py",
    bug: dict = None,
    bug_id: str = None,
    bug_description: str = None,
    use_llm: bool = True
) -> dict:
    """
    Generates a minimal bug fix patch using the multi-provider LLM chain (Gemini -> Groq -> OpenRouter),
    falling back to rule-based templates.
    """
    if bug is None:
        bug = {
            "type": bug_id or "GeneralFix",
            "line": 1,
            "detail": bug_description or "",
            "root_cause": bug_description or "",
            "suggested_fix": bug_description or ""
        }

    # 1. Try rule-based patch first
    rule_result = generate_rule_patch(original_code, bug)
    if rule_result.get("patch_method") != "no_change":
        return {
            "filename": filename,
            "diff": rule_result["diff"],
            "patched_code": rule_result["patched"],
            "explanation": f"Applied rule-based template for {bug.get('type')}"
        }

    # 2. Try LLM patch fallback chain (Gemini -> Groq -> OpenRouter)
    if use_llm:
        patched_code = llm_patch(original_code, bug)
        if patched_code:
            clean_code = patched_code.strip()
            if clean_code.startswith("```python"):
                clean_code = clean_code[9:]
            elif clean_code.startswith("```"):
                clean_code = clean_code[3:]
            if clean_code.endswith("```"):
                clean_code = clean_code[:-3]
            clean_code = clean_code.strip()

            diff = generate_unified_diff(original_code, clean_code, filename)
            return {
                "filename": filename,
                "diff": diff,
                "patched_code": clean_code,
                "explanation": f"AutoPatch generated fix via LLM fallback chain for {bug.get('type')}"
            }

    return {
        "filename": filename,
        "diff": "",
        "patched_code": original_code,
        "explanation": "No automatic patch generated. Manual review required."
    }
