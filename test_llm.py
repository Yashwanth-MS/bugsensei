def calculate_discount(price, discount_percent):
    # Bug: negative price passes through, discount > 100 results in negative total
    return price * (1 - discount_percent / 100)

def find_user_by_id(users, user_id):
    # Bug: returns first user if not found instead of None or raising KeyError
    for u in users:
        if u.get("id") == user_id:
            return u
    return users[0]

def withdraw_balance(account, amount):
    # Bug: no check for insufficient funds or negative withdrawal amount
    account["balance"] -= amount
    return account["balance"]
