import pytest
from main import calculate_grade, average

def test_valid_marks():
    assert calculate_grade(95) == "A"
    assert calculate_grade(80) == "B"

def test_empty_scores():
    with pytest.raises(ZeroDivisionError):
        average([])  # This will expose the bug
