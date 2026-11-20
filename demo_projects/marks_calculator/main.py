# Bug: no input validation — negative marks and >100 pass through

def calculate_grade(marks):
    if marks >= 90:
        return "A"
    elif marks >= 75:
        return "B"
    elif marks >= 60:
        return "C"
    elif marks >= 35:
        return "D"
    else:
        return "F"

def average(scores):
    total = 0
    for s in scores:
        total += s
    return total / len(scores)   # Bug: ZeroDivisionError if scores=[]

if __name__ == "__main__":
    print(calculate_grade(-10))   # should raise error, returns "F" silently
    print(calculate_grade(150))   # should raise error, returns "A" silently
