import difflib
import ast

# Rule-based patches for known bug types
PATCH_TEMPLATES = {
    "PossibleZeroDivision": lambda src, line: _patch_zero_div(src, line),
    "BareExcept": lambda src, line: _patch_bare_except(src, line),
    "CompareToNone": lambda src, line: src.replace("== None", "is None").replace("!= None", "is not None"),
}

def generate_patch(source: str, bug: dict) -> dict:
    """
    Returns a minimal unified diff.
    Tries rule-based first. Falls back to LLM patch (Groq/Gemini/OpenRouter) if no rule matches.
    """
    bug_type = bug.get("type", "") or bug.get("id", "")
    patched = source
    method = "no_change"

    # 1. Try rule-based templates
    for key, fn in PATCH_TEMPLATES.items():
        if key in bug_type:
            try:
                patched = fn(source, bug.get("line", 0) or bug.get("line_number", 0))
                if patched != source:
                    method = "rule_based"
                break
            except Exception:
                patched = source

    # 2. Try LLM patch fallback if rules didn't change the code
    if patched == source:
        try:
            try:
                from llm.provider import llm_patch
            except ImportError:
                from backend.llm.provider import llm_patch

            llm_result = llm_patch(source, bug)
            if llm_result and isinstance(llm_result, str):
                cleaned = llm_result.strip()
                if cleaned.startswith("```python"):
                    cleaned = cleaned[9:]
                elif cleaned.startswith("```"):
                    cleaned = cleaned[3:]
                if cleaned.endswith("```"):
                    cleaned = cleaned[:-3]
                cleaned = cleaned.strip()

                if cleaned and cleaned != source:
                    patched = cleaned
                    method = "llm_patch"
        except Exception as e:
            print(f"[BugSensei] LLM patch failed gracefully: {e}")

    diff = list(difflib.unified_diff(
        source.splitlines(keepends=True),
        patched.splitlines(keepends=True),
        fromfile="original.py",
        tofile="patched.py",
        lineterm=""
    ))

    return {
        "original": source,
        "patched": patched,
        "diff": "\n".join(diff),
        "patch_method": method if diff else "no_change"
    }

def _patch_zero_div(source: str, line: int) -> str:
    lines = source.splitlines()
    if line > 0 and line <= len(lines):
        original_line = lines[line - 1]
        indent = len(original_line) - len(original_line.lstrip())
        pad = " " * indent
        # Wrap the division in a zero-check
        lines[line - 1] = f"{pad}# AutoPatch: Added zero-division guard\n{pad}if denominator == 0:\n{pad}    raise ValueError('Denominator cannot be zero')\n{original_line}"
    return "\n".join(lines)

def _patch_bare_except(source: str, line: int) -> str:
    return source.replace("except:", "except Exception:")

def generate_unified_diff(original: str, modified: str, filename: str = "app.py") -> str:
    """
    Generates a minimal unified diff between the original and modified code.
    """
    orig_lines = original.splitlines(keepends=True)
    mod_lines = modified.splitlines(keepends=True)

    diff = difflib.unified_diff(
        orig_lines,
        mod_lines,
        fromfile=f"a/{filename}",
        tofile=f"b/{filename}",
        lineterm=""
    )
    return "".join(diff)

def apply_simple_rule_patch(original: str, bug_id: str) -> str:
    """
    Fallback patch dispatcher based on bug identifier or type.
    """
    res = generate_patch(original, {"type": bug_id})
    return res.get("patched", original)
