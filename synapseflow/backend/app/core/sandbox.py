import subprocess
import sys
import textwrap
import tempfile
import os
import time
from typing import Dict, Any, Optional


def _normalize_output(value: Optional[str]) -> str:
    return (value or "").strip()


def execute_code_safely(code: str, timeout: int = 5, stdin: str = "") -> Dict[str, Any]:
    """
    Executes untrusted learner code in an isolated subprocess with a hard timeout.
    Returns {'stdout': str, 'stderr': str, 'exit_code': int, 'timed_out': bool}
    """
    fd, path = tempfile.mkstemp(suffix=".py")
    temp_dir = tempfile.mkdtemp()
    try:
        with os.fdopen(fd, "w") as f:
            f.write(code if code.endswith("\n") else code + "\n")

        proc = subprocess.Popen(
            [sys.executable, "-I", "-B", path],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            env={"PYTHONIOENCODING": "utf-8", "PATH": os.environ.get("PATH", "")},
            cwd=temp_dir,
        )
        timed_out = False
        try:
            stdout, stderr = proc.communicate(input=stdin, timeout=timeout)
        except subprocess.TimeoutExpired:
            timed_out = True
            try:
                proc.kill()
            except Exception:
                pass
            try:
                stdout, stderr = proc.communicate(timeout=2)
            except Exception:
                stdout, stderr = "", "Execution timed out"
        return {
            "stdout": _normalize_output(stdout),
            "stderr": _normalize_output(stderr),
            "exit_code": proc.returncode if proc.returncode is not None else -1,
            "timed_out": timed_out,
        }
    except Exception as e:
        return {"stdout": "", "stderr": str(e), "exit_code": -2, "timed_out": False}
    finally:
        for p in (path,):
            try:
                os.unlink(p)
            except OSError:
                pass
        try:
            os.rmdir(temp_dir)
        except OSError:
            pass


def _case_expected(tc: Dict[str, Any]) -> Any:
    for key in ("expected", "expected_output", "expected_stdout"):
        if key in tc:
            return tc.get(key)
    return None


def grade_submission(code: str, test_cases: list) -> Dict[str, Any]:
    """Runs test cases; returns passed count and first failure."""
    failures = []
    passed = 0
    cases = test_cases or [{"expected": None}]
    total = len(cases)
    timeout = 5
    try:
        timeout = int(os.environ.get("SANDBOX_TIMEOUT_SECONDS", timeout))
    except (TypeError, ValueError):
        pass

    for tc in cases:
        tc = tc or {}
        expected = _case_expected(tc)
        stdin = tc.get("input", tc.get("stdin", ""))
        if not isinstance(stdin, str):
            try:
                stdin = str(stdin)
            except Exception:
                stdin = ""

        result = execute_code_safely(code, timeout=timeout, stdin=stdin)

        if result["timed_out"]:
            failures.append({"case": tc, "error": "Execution timed out"})
            continue
        if result["exit_code"] != 0:
            failures.append({"case": tc, "error": result["stderr"] or "runtime error"})
            continue

        if expected is not None:
            if result["stdout"] != str(expected).strip():
                failures.append({"case": tc, "got": result["stdout"], "expected": expected})
                continue

        passed += 1

    if not test_cases:
        total = 1

    return {
        "passed": len(failures) == 0 and total > 0 and passed == total,
        "passed_count": passed,
        "total": total,
        "failures": failures,
    }