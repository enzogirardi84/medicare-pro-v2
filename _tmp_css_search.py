import re

with open('assets/style.css', 'r') as f:
    content = f.read()

# Buscar reglas que afecten stMain o stAppViewContainer
selectors = ['stMain', 'stAppViewContainer', 'block-container']
for sel in selectors:
    print(f"\n=== {sel} ===")
    pattern = re.compile(rf'\[data-testid="{sel}"\].*?\{{[^\}}]*\}}', re.DOTALL)
    for m in pattern.findall(content)[:20]:
        print('---')
        print(m[:300])
        print()

# Buscar display:none en reglas de desktop (no en media queries mobile)
print("\n=== display:none fuera de @media mobile ===")
lines = content.split('\n')
in_mobile_media = False
for i, line in enumerate(lines):
    if '@media (max-width' in line and '767' in line:
        in_mobile_media = True
    if in_mobile_media and line.strip() == '}':
        in_mobile_media = False
    if not in_mobile_media and 'display: none' in line.lower():
        print(f"Line {i+1}: {line.strip()[:120]}")
