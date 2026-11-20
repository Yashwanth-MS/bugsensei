import ast
import textwrap

class ASTChecker:
    """
    Walks the Python AST tree to find common logic bugs.
    Think of AST as a 'map' of your code's structure.
    """

    def __init__(self, source_code: str, filename: str = "app.py"):
        self.source = source_code
        self.filename = filename
        self.bugs = []

    def check(self):
        try:
            tree = ast.parse(self.source)
        except SyntaxError as e:
            self.bugs.append({
                "type": "SyntaxError",
                "line": e.lineno,
                "detail": str(e),
                "severity": "CRITICAL",
                "confidence": 1.0
            })
            return self.bugs

        self._check_division(tree)
        self._check_bare_except(tree)
        self._check_mutable_defaults(tree)
        self._check_comparison_to_none(tree)
        return self.bugs

    def _check_division(self, tree):
        """Catch division without zero-check."""
        for node in ast.walk(tree):
            if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Div):
                self.bugs.append({
                    "type": "PossibleZeroDivision",
                    "line": node.lineno,
                    "detail": "Division operation found with no zero-check on denominator.",
                    "root_cause": "If the denominator is 0 at runtime, Python raises ZeroDivisionError and the program crashes.",
                    "trigger_input": "Pass 0 as the denominator value.",
                    "severity": "HIGH",
                    "confidence": 0.75
                })

    def _check_bare_except(self, tree):
        """Catch except: with no exception type — swallows all errors silently."""
        for node in ast.walk(tree):
            if isinstance(node, ast.ExceptHandler) and node.type is None:
                self.bugs.append({
                    "type": "BareExcept",
                    "line": node.lineno,
                    "detail": "Bare 'except:' catches everything including KeyboardInterrupt and SystemExit.",
                    "root_cause": "Without specifying an exception type, real errors are silently swallowed.",
                    "trigger_input": "Any unexpected error in the try block will be hidden.",
                    "severity": "MEDIUM",
                    "confidence": 0.95
                })

    def _check_mutable_defaults(self, tree):
        """Catch def func(items=[]) — classic Python gotcha."""
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                for default in node.args.defaults:
                    if isinstance(default, (ast.List, ast.Dict, ast.Set)):
                        self.bugs.append({
                            "type": "MutableDefaultArgument",
                            "line": node.lineno,
                            "detail": f"Function '{node.name}' uses a mutable default argument.",
                            "root_cause": "Mutable defaults are created once and shared across all calls. Modifying them in one call affects future calls.",
                            "trigger_input": "Call the function twice — the second call will see mutations from the first.",
                            "severity": "MEDIUM",
                            "confidence": 0.98
                        })

    def _check_comparison_to_none(self, tree):
        """Catch 'if x == None' instead of 'if x is None'."""
        for node in ast.walk(tree):
            if isinstance(node, ast.Compare):
                for op, comparator in zip(node.ops, node.comparators):
                    if isinstance(op, (ast.Eq, ast.NotEq)) and isinstance(comparator, ast.Constant) and comparator.value is None:
                        self.bugs.append({
                            "type": "CompareToNone",
                            "line": node.lineno,
                            "detail": "Use 'is None' or 'is not None' instead of '== None'.",
                            "root_cause": "'==' calls __eq__ which can be overridden. 'is' checks identity — always correct for None.",
                            "trigger_input": "An object with a custom __eq__ method could return True when compared to None.",
                            "severity": "LOW",
                            "confidence": 1.0
                        })


def run_ast_checks(code: str, filename: str = "app.py"):
    checker = ASTChecker(code, filename)
    return checker.check()
