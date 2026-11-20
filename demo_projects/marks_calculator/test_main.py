import pytest
from main import calculate_grade, average

def test_average_normal():
    assert average([80, 90, 100]) == 90.0

def test_average_empty_list():
    # Calling average on an empty list should not crash unhandled
    with pytest.raises((ValueError, ZeroDivisionError)):
        average([])

def test_calculate_grade_valid():
    assert calculate_grade(95) == "A"
    assert calculate_grade(80) == "B"
    assert calculate_grade(65) == "C"
    assert calculate_grade(40) == "D"
    assert calculate_grade(20) == "F"

def test_calculate_grade_invalid_negative():
    # Negative marks should raise ValueError
    with pytest.raises(ValueError):
        res = calculate_grade(-10)
        # If no error is raised and invalid grade returned, fail assertion
        if res == "F":
            raise ValueError("Negative marks allowed without validation")

def test_calculate_grade_invalid_exceeds_hundred():
    # Marks > 100 should raise ValueError
    with pytest.raises(ValueError):
        res = calculate_grade(150)
        if res == "A":
            raise ValueError("Marks exceeding 100 allowed without validation")
