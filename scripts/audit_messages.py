"""Audit API messages in application source only."""
import re
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
INCLUDE_DIRS = ("service", "router", "utils")
INCLUDE_FILES = {"service/exceptions.py"}
EXCLUDE_UTILS = {
    "utils/enums.py",
    "utils/db.py",
    "utils/mixins.py",
    "utils/jwt_tokens.py",
    "utils/security.py",
    "utils/otp.py",
    "utils/pagination.py",
    "utils/join_code.py",
    "utils/invite_links.py",
    "utils/dev_invite.py",
    "utils/dev_otp.py",
    "utils/academic_rbac.py",
    "utils/rbac.py",
    "utils/app_timezone.py",
    "utils/exam_blueprint_allocation.py",
}

patterns = [
    re.compile(r'raise\s+\w+Error\(\s*f?"([^"]+)"'),
    re.compile(r'raise\s+UnauthorizedError\(\s*f?"([^"]+)"'),
    re.compile(r'"message"\s*:\s*"([^"]+)"'),
    re.compile(r'"error"\s*:\s*"([^"]+)"'),
    re.compile(r'super\(\)\.__init__\(\s*"([^"]+)"'),
    re.compile(r'return jsonify\(\{"error": "([^"]+)"\}\)'),
]

msgs: dict[str, set[str]] = defaultdict(set)

for rel in INCLUDE_FILES:
    path = ROOT / rel
    if path.exists():
        paths = [path]
    else:
        paths = []
for d in INCLUDE_DIRS:
    paths = list(ROOT.glob(f"{d}/**/*.py")) if d != "utils" else []
    for path in ROOT.glob(f"{d}/**/*.py"):
        rel = str(path.relative_to(ROOT)).replace("\\", "/")
        if d == "utils" and rel in EXCLUDE_UTILS:
            continue
        if d == "utils" and rel not in EXCLUDE_UTILS and "question_type" not in rel:
            continue
        text = path.read_text(encoding="utf-8")
        for pat in patterns:
            for m in pat.finditer(text):
                msg = m.group(1)
                if len(msg) < 3 or "{" in msg:
                    continue
                msgs[msg].add(rel)

# Also scan service and router fully
for d in ("service", "router"):
    for path in ROOT.glob(f"{d}/**/*.py"):
        rel = str(path.relative_to(ROOT)).replace("\\", "/")
        text = path.read_text(encoding="utf-8")
        for pat in patterns:
            for m in pat.finditer(text):
                msg = m.group(1)
                if len(msg) < 3 or "{" in msg:
                    continue
                msgs[msg].add(rel)

out = ROOT / "scripts" / "audit_messages_app.txt"
lines = ["=== DUPLICATES ==="]
for msg in sorted(msgs, key=lambda m: (-len(msgs[m]), m)):
    if len(msgs[msg]) > 1:
        lines.append(f"[{len(msgs[msg])}] {msg}")
        for f in sorted(msgs[msg]):
            lines.append(f"    - {f}")

lines.append("\n=== ALL ({}) ===".format(len(msgs)))
for msg in sorted(msgs):
    lines.append(msg)

out.write_text("\n".join(lines), encoding="utf-8")
print(f"Wrote {out} ({len(msgs)} messages)")
