"""Find remaining hardcoded API messages."""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
pat = re.compile(
    r'raise\s+\w+Error\(\s*["\']|raise\s+\w+Error\(f["\']|"message"\s*:\s*["\']|"error"\s*:\s*["\']'
)
roots = list((ROOT / "service").rglob("*.py")) + list((ROOT / "router").rglob("*.py"))
roots.append(ROOT / "utils" / "question_type_validation.py")
roots.append(ROOT / "utils" / "exam_blueprint_allocation.py")

for p in roots:
    text = p.read_text(encoding="utf-8")
    for i, line in enumerate(text.splitlines(), 1):
        if not pat.search(line):
            continue
        if "Messages." in line or "exc.message" in line or "exc.messages" in line:
            continue
        print(f"{p.relative_to(ROOT)}:{i}:{line.strip()[:140]}")
