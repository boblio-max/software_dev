import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from app.core.sandbox import grade_submission, execute_code_safely


def test_sandbox_success():
    code = "print('Hello, World!')"
    r = execute_code_safely(code)
    assert r["exit_code"] == 0
    assert "Hello, World!" in r["stdout"]


def test_sandbox_timeout():
    r = execute_code_safely("while True: pass", timeout=1)
    assert r["timed_out"] is True


def test_grade():
    code = "print('15')"
    res = grade_submission(code, [{"expected": "15"}])
    assert res["passed"] is True


def test_grade_fail():
    code = "print('10')"
    res = grade_submission(code, [{"expected": "15"}])
    assert res["passed"] is False
    assert res["failures"]


if __name__ == "__main__":
    test_sandbox_success()
    test_sandbox_timeout()
    test_grade()
    test_grade_fail()
    print("All improvement tests passed")
