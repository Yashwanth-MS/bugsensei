import pytest
from main import divide, process

def test_divide_normal():
    assert divide(10, 2) == 5.0

def test_divide_by_zero():
    with pytest.raises(ZeroDivisionError):
        divide(10, 0)

def test_process_mutable_defaults():
    # Calling process twice should not retain mutations across calls
    res1 = process()
    res2 = process()
    assert res1 == ["processed"]
    assert res2 == ["processed"], "Mutable default bug detected: list retained previous call state"
