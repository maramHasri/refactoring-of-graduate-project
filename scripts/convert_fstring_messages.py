"""Convert remaining f-string ServiceError raises to Messages.*.format(...)."""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


def const_name(template: str, used: set[str]) -> str:
    words = re.findall(r"[A-Za-z0-9]+", template)
    name = "_".join(w.upper() for w in words[:12]) or "MSG"
    if name[0].isdigit():
        name = f"MSG_{name}"
    if len(name) > 70:
        name = name[:70].rstrip("_")
    base = name
    i = 2
    while name in used:
        name = f"{base}_{i}"
        i += 1
    used.add(name)
    return name


def normalize_template(fmsg: str) -> tuple[str, list[str]]:
    """Convert f-string body to str.format template + arg names."""
    args: list[str] = []
    out = []
    i = 0
    while i < len(fmsg):
        if fmsg[i] == "{":
            # find matching }
            depth = 1
            j = i + 1
            while j < len(fmsg) and depth:
                if fmsg[j] == "{":
                    depth += 1
                elif fmsg[j] == "}":
                    depth -= 1
                j += 1
            expr = fmsg[i + 1 : j - 1]
            # strip format specs after :
            if ":" in expr and not expr.startswith("'") and not expr.startswith('"'):
                # could be var:spec or nested
                pass
            # simplify common expr to named placeholders
            clean = re.sub(r"[^A-Za-z0-9_]+", "_", expr).strip("_").lower()
            if not clean:
                clean = f"arg{len(args)+1}"
            # avoid keywords
            if clean in {"class", "type", "id"}:
                clean = f"{clean}_value"
            # if starts with digit
            if clean[0].isdigit():
                clean = f"v_{clean}"
            # unique
            base = clean
            n = 2
            while clean in args:
                clean = f"{base}_{n}"
                n += 1
            args.append((clean, expr))
            out.append("{" + clean + "}")
            i = j
        else:
            out.append(fmsg[i])
            i += 1
    return "".join(out), args


def main() -> None:
    from utils.messages import Messages

    used = {
        name
        for name, value in vars(Messages).items()
        if isinstance(value, str) and not name.startswith("_")
    }
    text_to_const = {
        value: name
        for name, value in vars(Messages).items()
        if isinstance(value, str) and not name.startswith("_")
    }

    fpat = re.compile(r'raise\s+(\w+Error)\(f"((?:[^"\\]|\\.)*)"\)')
    multiline_f = re.compile(
        r'raise\s+(\w+Error)\(\s*\n\s*f"((?:[^"\\]|\\.)*)"\s*\n(?:\s*f"((?:[^"\\]|\\.)*)"\s*\n)?\s*\)',
        re.MULTILINE,
    )

    new_constants: list[tuple[str, str]] = []
    file_changes = 0

    for folder in ("service", "router", "utils"):
        for path in (ROOT / folder).rglob("*.py"):
            if path.name == "messages.py":
                continue
            content = path.read_text(encoding="utf-8")
            original = content

            def repl_one(m: re.Match) -> str:
                err, fbody = m.group(1), m.group(2)
                # unescape
                fbody = bytes(fbody, "utf-8").decode("unicode_escape") if "\\" in fbody else fbody
                template, args = normalize_template(m.group(2))
                if template in text_to_const:
                    const = text_to_const[template]
                else:
                    const = const_name(template, used)
                    text_to_const[template] = const
                    new_constants.append((const, template))
                if not args:
                    return f"raise {err}(Messages.{const})"
                fmt = ", ".join(f"{name}={expr}" for name, expr in args)
                # filter illegal kw names with dots - rewrite those as positional remap
                safe_args = []
                for name, expr in args:
                    if re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", name):
                        safe_args.append(f"{name}={expr}")
                    else:
                        safe_args.append(f"{name}={expr}")
                return f"raise {err}(Messages.{const}.format({', '.join(safe_args)}))"

            content = fpat.sub(repl_one, content)

            # two-line concatenated f-strings
            def repl_multi(m: re.Match) -> str:
                err = m.group(1)
                part1 = m.group(2)
                part2 = m.group(3) or ""
                fbody = part1 + part2
                template, args = normalize_template(fbody)
                if template in text_to_const:
                    const = text_to_const[template]
                else:
                    const = const_name(template, used)
                    text_to_const[template] = const
                    new_constants.append((const, template))
                fmt = ", ".join(f"{name}={expr}" for name, expr in args)
                if fmt:
                    return f"raise {err}(Messages.{const}.format({fmt}))"
                return f"raise {err}(Messages.{const})"

            content = multiline_f.sub(repl_multi, content)

            if content != original:
                if "from utils.messages import Messages" not in content:
                    if content.startswith("from __future__"):
                        # after future import
                        lines = content.splitlines(keepends=True)
                        insert_at = 1
                        while insert_at < len(lines) and (
                            lines[insert_at].startswith("from __future__")
                            or lines[insert_at].strip() == ""
                        ):
                            insert_at += 1
                        lines.insert(insert_at, "from utils.messages import Messages\n")
                        content = "".join(lines)
                    else:
                        content = "from utils.messages import Messages\n" + content
                path.write_text(content, encoding="utf-8")
                file_changes += 1
                print(f"updated {path.relative_to(ROOT)}")

    if new_constants:
        msg_path = ROOT / "utils" / "messages.py"
        text = msg_path.read_text(encoding="utf-8")
        block = ["\n    # Dynamic templates\n"]
        for const, template in new_constants:
            escaped = template.replace("\\", "\\\\").replace('"', '\\"')
            block.append(f'    {const} = "{escaped}"\n')
        text = text.rstrip() + "\n" + "".join(block) + "\n"
        msg_path.write_text(text, encoding="utf-8")
        print(f"added {len(new_constants)} constants")

    print(f"files changed: {file_changes}")


if __name__ == "__main__":
    main()
