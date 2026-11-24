from __future__ import annotations

import re
from pathlib import Path

LINK = re.compile(r"\]\(([^)#\s]+\.md)(?:#[^)]*)?\)")


def check(root: Path, docs: Path) -> list[str]:
    errors: list[str] = []
    for page in sorted(docs.rglob("*.md")):
        text = page.read_text(encoding="utf-8")
        for target in LINK.findall(text):
            if target.startswith(("http://", "https://")):
                continue
            resolved = (page.parent / target).resolve()
            if not resolved.is_file():
                errors.append(f"{page.relative_to(root)}: broken link -> {target}")
    return errors


def run(root: Path, docs: Path) -> int:
    errors = check(root, docs)
    for error in errors:
        print(error)
    if errors:
        print(f"\n{len(errors)} broken local link(s).")
        return 1
    print("local links: OK")
    return 0
