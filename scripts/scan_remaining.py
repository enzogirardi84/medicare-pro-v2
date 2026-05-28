"""Scan for remaining security issues."""
import os, re

findings = []

for root, dirs, files in os.walk("."):
    if "__pycache__" in root or ".git" in root or ".venv" in root:
        continue
    for f in files:
        if not f.endswith(".py"):
            continue
        path = os.path.join(root, f)
        try:
            with open(path, "r", encoding="utf-8", errors="ignore") as fh:
                content = fh.read()
        except:
            continue

        lines = content.split("\n")

        # Check st.file_uploader for validate_uploaded_file
        for i, line in enumerate(lines):
            if "st.file_uploader" in line:
                nearby = "\n".join(lines[i : i + 20])
                if "validate_uploaded_file" not in nearby:
                    findings.append(f"MISSING validate: {path}:{i+1}")

        # Check unsafe_allow_html without html.escape
        for i, line in enumerate(lines):
            if "unsafe_allow_html=True" not in line:
                continue
            # Skip known safe patterns
            if "html.escape" in line or "safe_markdown" in line or "escape(" in line:
                continue
            if re.search(r'["\'].*\{.*\}.*["\']', line):
                # Check if it's a static template (no f-string)
                if "f'" in line or 'f"' in line or ".format(" in line:
                    findings.append(f"XSS risk: {path}:{i+1}")

print(f"Total findings: {len(findings)}")
for f in findings[:20]:
    print(f"  {f}")
