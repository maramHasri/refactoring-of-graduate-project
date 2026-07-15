"""Second pass: multiline raises and remaining hardcoded strings."""
from __future__ import annotations

import ast
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
import sys
sys.path.insert(0, str(ROOT))

# Manual multiline / concatenated replacements: (file, old, new)
MANUAL: list[tuple[str, str, str]] = []


def load_messages() -> dict[str, str]:
    from utils.messages import Messages

    return {
        value: name
        for name, value in vars(Messages).items()
        if isinstance(value, str) and not name.startswith("_")
    }


def fix_multiline_raises(path: Path, text_to_const: dict[str, str]) -> str:
    content = path.read_text(encoding="utf-8")
    original = content

    for msg, const in sorted(text_to_const.items(), key=lambda x: -len(x[0])):
        if "\n" in msg:
            continue
        # raise XError(\n    "msg"\n)
        pattern = re.compile(
            rf'raise\s+(\w+Error)\(\s*\n\s*"{re.escape(msg)}"\s*\n\s*\)',
            re.MULTILINE,
        )
        content = pattern.sub(rf"raise \1(Messages.{const})", content)

        # raise XError(\n    "part1"\n    "part2"\n)  two-string concat
        if msg.endswith(" "):
            trimmed = msg.rstrip()
            if trimmed in text_to_const:
                c2 = text_to_const[trimmed]
                pattern2 = re.compile(
                    rf'raise\s+(\w+Error)\(\s*\n\s*"{re.escape(trimmed)}"\s*\n\s*"[^"]+"\s*\n\s*\)',
                    re.MULTILINE,
                )
                content = pattern2.sub(rf"raise \1(Messages.{c2})", content)

    return content if content != original else ""


def main() -> None:
    text_to_const = load_messages()
    changed = []
    for folder in ("service", "router"):
        for path in (ROOT / folder).rglob("*.py"):
            new_content = fix_multiline_raises(path, text_to_const)
            if new_content:
                path.write_text(new_content, encoding="utf-8")
                changed.append(str(path.relative_to(ROOT)))

    # exceptions.py
    exc = ROOT / "service" / "exceptions.py"
    text = exc.read_text(encoding="utf-8")
    if "from utils.messages import Messages" not in text:
        text = "from utils.messages import Messages\n\n" + text
    text = text.replace(
        '"This exam overlaps with another scheduled exam for one or more students."',
        "Messages.THIS_EXAM_OVERLAPS_WITH_ANOTHER_SCHEDULED_EXAM_FOR_ONE_OR_MORE_STUDENTS",
    )
    text = text.replace(
        '"The teacher already has another scheduled exam during this time."',
        "Messages.THE_TEACHER_ALREADY_HAS_ANOTHER_SCHEDULED_EXAM_DURING_THIS_TIME",
    )
    exc.write_text(text, encoding="utf-8")
    changed.append("service/exceptions.py")

    # proctoring_ws ServiceError strings
    ws = ROOT / "router" / "proctoring_ws.py"
    wst = ws.read_text(encoding="utf-8")
    replacements = {
        'ServiceError("Missing token", 401)': "ServiceError(Messages.MISSING_TOKEN, 401)",
        'ServiceError("Invalid access token", 401)': "ServiceError(Messages.INVALID_ACCESS_TOKEN, 401)",
        'ServiceError("User not found", 401)': "ServiceError(Messages.USER_NOT_FOUND, 401)",
        'ServiceError("workspace_id query parameter is required", 400)': "ServiceError(Messages.WORKSPACE_ID_QUERY_PARAMETER_IS_REQUIRED, 400)",
        'ServiceError("Not an active member of this workspace", 403)': "ServiceError(Messages.NOT_AN_ACTIVE_MEMBER_OF_THIS_WORKSPACE, 403)",
    }
    for old, new in replacements.items():
        wst = wst.replace(old, new)
    ws.write_text(wst, encoding="utf-8")
    changed.append("router/proctoring_ws.py")

    print(f"Second pass updated {len(changed)} files")


if __name__ == "__main__":
    main()
