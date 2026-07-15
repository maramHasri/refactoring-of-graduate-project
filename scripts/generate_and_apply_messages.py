"""
Generate utils/messages.py and apply replacements across service/ and router/.
"""
from __future__ import annotations

import re
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

DOMAIN_RULES: list[tuple[str, tuple[str, ...]]] = [
    ("Authentication", ("login", "logout", "password", "otp", "token", "credential", "session", "registration", "verify", "refresh", "authorization", "account", "email not", "email is", "logged out", "all sessions")),
    ("Users", ("profile", "user ", "user_", "super admin", "suspension", "suspended", "restored successfully")),
    ("Workspaces", ("workspace", "join code", "institution", "organization", "member", "owner", "admin access", "solo workspace")),
    ("Subjects", ("subject", "enroll", "teacher assigned", "teacher assignment", "teacher removed from subject")),
    ("Topics", ("topic",)),
    ("Question Banks", ("question bank", "bank ", "visibility")),
    ("Questions", ("question", "choice", "mcq", "essay", "true_false", "multi_select", "difficulty", "points must")),
    ("Tests", ("test ", "exam", "publish", "scheduled", "slug", "blueprint", "csv", "whitelist", "student_membership")),
    ("Attempts", ("attempt", "grading", "submission", "answer", "autosave", "timeout", "manual grading")),
    ("Proctoring", ("proctoring", "violation", "evidence")),
    ("Invitations", ("invit", "invite", "pending invite")),
    ("Files", ("image", "upload", "csv_file", "multipart", "file type")),
    ("AI", ("ai ", "gemini", "openrouter", "huggingface", "qwen", "generation")),
    ("Student Groups", ("group",)),
    ("System", ()),
]


def to_constant_name(text: str, used: set[str]) -> str:
    base = (
        text.strip()
        .rstrip(".")
        .replace("'", "")
        .replace("/", "_")
        .replace("-", "_")
        .replace(".", "")
    )
    words = re.findall(r"[A-Za-z0-9]+", base)
    if not words:
        words = ["MESSAGE"]
    name = "_".join(w.upper() for w in words)
    if name[0].isdigit():
        name = f"MSG_{name}"
    if len(name) > 80:
        name = name[:80].rstrip("_")
    original = name
    i = 2
    while name in used:
        name = f"{original}_{i}"
        i += 1
    used.add(name)
    return name


def classify_domain(text: str) -> str:
    lower = text.lower()
    for domain, keywords in DOMAIN_RULES:
        if any(k in lower for k in keywords):
            return domain
    return "System"


def collect_static_messages() -> list[str]:
    audit = (ROOT / "scripts" / "audit_messages_app.txt").read_text(encoding="utf-8")
    section = audit.split("=== ALL")[1]
    messages = []
    for line in section.splitlines():
        line = line.strip()
        if not line or line.startswith("("):
            continue
        messages.append(line)
    return messages


def collect_fstring_templates() -> list[str]:
    templates: set[str] = set()
    pat = re.compile(r'raise\s+\w+Error\(f"([^"]+)"')
    for path in list((ROOT / "service").rglob("*.py")) + list((ROOT / "router").rglob("*.py")):
        text = path.read_text(encoding="utf-8")
        for m in pat.finditer(text):
            templates.add(m.group(1))
    extra = [
        "You have reached the maximum allowed attempts ({max_attempts})",
        "Missing answers for question IDs: {missing_question_ids}",
        "All questions must be answered before submission. Missing answers for question IDs: {missing_question_ids}",
        "Membership is not a workspace {expected_role.lower()}",
        "Use access_token from login, not refresh_token",
        "See server logs for traceback",
        "Attempt force-submitted",
        "Workspace created",
        "Teacher removed from workspace successfully.",
        "Attempt is not a workspace {role}",
    ]
    for e in extra:
        templates.add(e)
    return sorted(templates)


def build_registry() -> tuple[dict[str, str], dict[str, str]]:
    """Returns text->CONSTANT and CONSTANT->text."""
    used: set[str] = set()
    text_to_const: dict[str, str] = {}
    const_to_text: dict[str, str] = {}

    for text in collect_static_messages():
        if text not in text_to_const:
            const = to_constant_name(text, used)
            text_to_const[text] = const
            const_to_text[const] = text

    for template in collect_fstring_templates():
        if template not in text_to_const:
            const = to_constant_name(template, used)
            text_to_const[template] = const
            const_to_text[const] = template

    return text_to_const, const_to_text


def write_messages_py(const_to_text: dict[str, str]) -> None:
    by_domain: dict[str, list[tuple[str, str]]] = defaultdict(list)
    for const, text in const_to_text.items():
        by_domain[classify_domain(text)].append((const, text))

    lines = [
        '"""',
        "Centralized backend API response messages.",
        "",
        "These strings are part of the API contract. Do not change casually.",
        "Frontend teams use docs/backend-messages.md for translation dictionaries.",
        '"""',
        "",
        "",
        "class Messages:",
        '    """Standardized English response messages grouped by domain."""',
        "",
    ]

    domain_order = [d for d, _ in DOMAIN_RULES] + ["System"]
    seen_domains: set[str] = set()
    for domain in domain_order:
        if domain not in by_domain:
            continue
        seen_domains.add(domain)
        lines.append(f"    # {domain}")
        lines.append("")
        for const, text in sorted(by_domain[domain], key=lambda x: x[0]):
            escaped = text.replace("\\", "\\\\").replace('"', '\\"')
            lines.append(f'    {const} = "{escaped}"')
        lines.append("")

    for domain in sorted(by_domain):
        if domain in seen_domains:
            continue
        lines.append(f"    # {domain}")
        lines.append("")
        for const, text in sorted(by_domain[domain], key=lambda x: x[0]):
            escaped = text.replace("\\", "\\\\").replace('"', '\\"')
            lines.append(f'    {const} = "{escaped}"')
        lines.append("")

    path = ROOT / "utils" / "messages.py"
    path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")
    print(f"Wrote {path} ({len(const_to_text)} constants)")


def apply_replacements(text_to_const: dict[str, str], path: Path) -> str:
    content = path.read_text(encoding="utf-8")
    original = content
    needs_import = False

    for msg, const in sorted(text_to_const.items(), key=lambda x: -len(x[0])):
        if "{" in msg:
            # f-string template -> Messages.CONST.format(...)
            if f'f"{msg}"' not in content:
                continue
            placeholders = re.findall(r"\{([^}]+)\}", msg)
            if not placeholders:
                continue
            format_args = ", ".join(f"{p}={p}" for p in placeholders)
            content = content.replace(
                f'f"{msg}"',
                f"Messages.{const}.format({format_args})",
            )
            needs_import = True
        else:
            patterns = [
                (f'raise ValidationError("{msg}"', f"raise ValidationError(Messages.{const}"),
                (f'raise NotFoundError("{msg}"', f"raise NotFoundError(Messages.{const}"),
                (f'raise ForbiddenError("{msg}"', f"raise ForbiddenError(Messages.{const}"),
                (f'raise ConflictError("{msg}"', f"raise ConflictError(Messages.{const}"),
                (f'raise UnauthorizedError("{msg}"', f"raise UnauthorizedError(Messages.{const}"),
                (f'super().__init__("{msg}"', f"super().__init__(Messages.{const}"),
                (f'"message": "{msg}"', f'"message": Messages.{const}'),
                (f'"error": "{msg}"', f'"error": Messages.{const}'),
                (f'return jsonify({{"error": "{msg}"}})', f'return jsonify({{"error": Messages.{const}}})'),
                (f'return {{"message": "{msg}"', f'return {{"message": Messages.{const}'),
                (f'"payload": {{"error": "{msg}"}}', f'"payload": {{"error": Messages.{const}}}'),
            ]
            for old, new in patterns:
                if old in content:
                    content = content.replace(old, new)
                    needs_import = True

    if needs_import and "from utils.messages import Messages" not in content:
        # Insert after module docstring or at top
        if content.startswith('"""'):
            end = content.find('"""', 3)
            if end != -1:
                end += 3
                while end < len(content) and content[end] in "\r\n":
                    end += 1
                content = content[:end] + "\nfrom utils.messages import Messages\n" + content[end:]
            else:
                content = "from utils.messages import Messages\n" + content
        else:
            content = "from utils.messages import Messages\n" + content

    if content != original:
        path.write_text(content, encoding="utf-8")
    return content if content != original else ""


def main() -> None:
    text_to_const, const_to_text = build_registry()
    write_messages_py(const_to_text)

    changed = []
    for folder in ("service", "router"):
        for path in (ROOT / folder).rglob("*.py"):
            if apply_replacements(text_to_const, path):
                changed.append(str(path.relative_to(ROOT)))

    utils_qtv = ROOT / "utils" / "question_type_validation.py"
    if utils_qtv.exists() and apply_replacements(text_to_const, utils_qtv):
        changed.append(str(utils_qtv.relative_to(ROOT)))

    exc = ROOT / "service" / "exceptions.py"
    if apply_replacements(text_to_const, exc):
        changed.append(str(exc.relative_to(ROOT)))

    print(f"Updated {len(changed)} files")
    for f in sorted(changed):
        print(f"  - {f}")


if __name__ == "__main__":
    main()
