from typing import List, Optional
from pydantic import BaseModel, Field

class BugItem(BaseModel):
    id: Optional[str] = Field(None, description="Unique bug identifier")
    title: Optional[str] = Field(None, description="Short summary of the bug")
    description: Optional[str] = Field(None, description="Detailed explanation of the issue")
    line_number: Optional[int] = Field(None, description="Line number where issue originates")
    severity: str = Field("medium", description="critical, high, medium, low, info")
    category: str = Field("logic", description="security, syntax, logic, style, performance")
    source_tool: str = Field("ast", description="ast, pylint, bandit, llm")
    suggested_fix: Optional[str] = Field(None, description="Suggested remedy or explanation")

    # Fields for extended AST scanner compatibility
    type: Optional[str] = None
    line: Optional[int] = None
    detail: Optional[str] = None
    root_cause: Optional[str] = None
    trigger_input: Optional[str] = None
    confidence: Optional[float] = None

class ScanRequest(BaseModel):
    code: str
    filename: Optional[str] = "app.py"
    use_llm: Optional[bool] = False

class ScanResponse(BaseModel):
    filename: str
    bugs: List[BugItem]
    total_bugs: int

class PatchRequest(BaseModel):
    original_code: str
    filename: Optional[str] = "app.py"
    bug_id: Optional[str] = None
    bug_description: Optional[str] = None
    use_llm: Optional[bool] = False

class PatchResponse(BaseModel):
    filename: str
    diff: str
    patched_code: str
    explanation: str

class TestRunRequest(BaseModel):
    code: str
    test_code: str
    filename: Optional[str] = "app.py"
    test_filename: Optional[str] = "test_app.py"

class TestRunResponse(BaseModel):
    passed: bool
    summary: str
    raw_output: str
    duration_seconds: float

class AuditLogEntry(BaseModel):
    timestamp: str
    project_or_file: str
    action: str
    details: dict
