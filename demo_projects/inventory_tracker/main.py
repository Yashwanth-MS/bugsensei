def update_stock(inventory, item, quantity):
    if item in inventory:
        inventory[item] += quantity
    # Bug: silent fail if item not in inventory — should raise KeyError or add item

def get_price(inventory, item):
    return inventory[item]["price"]  # Bug: KeyError if item missing, no default

def apply_discount(price, discount):
    return price - (price * discount / 100)  # Bug: no check for discount > 100
