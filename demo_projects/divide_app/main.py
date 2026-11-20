def divide(a, b):
    return a / b   # Bug: no zero check

def process(items=[]):  # Bug: mutable default argument
    items.append("processed")
    return items

if __name__ == "__main__":
    result = divide(10, 0)   # crashes here
