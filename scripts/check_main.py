"""Check main_medicare.py for encoding issues."""
with open("main_medicare.py", "r", encoding="utf-8") as f:
    lines = f.readlines()

print(f"Line 16: {repr(lines[15].rstrip())}")
print(f"Total lines: {len(lines)}")

# Check line 16 for leading spaces
if lines[15].startswith(" "):
    print("ERROR: Line 16 starts with spaces!")
else:
    print("OK: Line 16 starts at column 0")
