import pytest
from main import login, hash_password

def test_login_success():
    assert login("admin123") is True

def test_login_failure():
    assert login("wrong_password") is False

def test_hash_password():
    hashed = hash_password("test_pass")
    assert isinstance(hashed, str)
    assert len(hashed) == 32
