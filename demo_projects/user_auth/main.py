import hashlib

# Bug: hardcoded password — bandit B105 catches this
PASSWORD = "admin123"

def login(user_input):
    if user_input == PASSWORD:   # Bug: comparing to hardcoded secret
        return True
    return False

def hash_password(pwd):
    return hashlib.md5(pwd.encode()).hexdigest()  # Bug: MD5 is weak — bandit B324
