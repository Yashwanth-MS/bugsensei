try:
    from llm.provider import llm_scan
except ImportError:
    from backend.llm.provider import llm_scan

# Alias for backwards compatibility
run_llm_scan = llm_scan
