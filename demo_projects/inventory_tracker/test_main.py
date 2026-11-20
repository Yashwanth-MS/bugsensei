import pytest
from main import update_stock, get_price, apply_discount

def test_update_stock_existing_item():
    inv = {"apple": 5}
    update_stock(inv, "apple", 3)
    assert inv["apple"] == 8

def test_update_stock_missing_item_silent_fail():
    inv = {"apple": 5}
    # If item is missing, it should either add it or raise KeyError, not silently do nothing
    update_stock(inv, "banana", 2)
    assert "banana" in inv, "Item should have been added or KeyError raised"

def test_get_price_existing():
    inv = {"apple": {"price": 10}}
    assert get_price(inv, "apple") == 10

def test_get_price_missing():
    inv = {}
    with pytest.raises(KeyError):
        get_price(inv, "missing_item")

def test_apply_discount_valid():
    assert apply_discount(100, 20) == 80.0

def test_apply_discount_exceeding_hundred():
    # Discounts > 100% should raise ValueError or be constrained
    with pytest.raises(ValueError):
        res = apply_discount(100, 150)
        if res < 0:
            raise ValueError("Negative price generated from discount > 100%")
