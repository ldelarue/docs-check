from __future__ import annotations

import re
import subprocess
from pathlib import Path

FENCE = re.compile(r"^\s*(`{3,}|~{3,})")
URL = re.compile(r"https?://([^/\s)\"'<>]+)")
HOST_LINE = re.compile(r"^  ([^\s:#][^:]*):\s*$")
FIELD_LINE = re.compile(r"^    (class|expected|note):\s*(.*)$")


def parse_value(raw: str) -> object:
    raw = raw.strip()
    if raw.startswith("[") and raw.endswith("]"):
        inner = raw[1:-1].strip()
        return [int(item) for item in inner.split(",") if item.strip()] if inner else []
    if len(raw) >= 2 and raw[0] == raw[-1] and raw[0] in "\"'":
        return raw[1:-1]
    return raw


def load_inventory(path: Path) -> dict[str, dict[str, object]]:
    hosts: dict[str, dict[str, object]] = {}
    current: str | None = None
    in_hosts = False
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.split("#", 1)[0].rstrip()
        if not line.strip():
            continue
        if not line.startswith(" "):
            in_hosts = line.strip() == "hosts:"
            current = None
            continue
        if not in_hosts:
            continue
        host_match = HOST_LINE.match(line)
        if host_match:
            current = host_match.group(1).strip().lower()
            hosts[current] = {}
            continue
        field_match = FIELD_LINE.match(line)
        if field_match and current:
            hosts[current][field_match.group(1)] = parse_value(field_match.group(2))
    return hosts


def markdown_hosts(docs: Path, sidebar: Path | None) -> set[str]:
    hosts: set[str] = set()
    paths = [*sorted(docs.rglob("*.md"))]
    if sidebar:
        paths.append(sidebar)
    for path in paths:
        if not path.is_file():
            continue
        inside = False
        marker = ""
        for line in path.read_text(encoding="utf-8").splitlines():
            fence = FENCE.match(line)
            if fence:
                token = fence.group(1)
                if not inside:
                    inside = True
                    marker = token[0]
                elif token[0] == marker:
                    inside = False
                continue
            if inside:
                continue
            line = re.sub(r"`[^`]*`", "", line)
            for match in URL.finditer(line):
                hosts.add(match.group(1).lower())
    return hosts


def toml_list(path: Path, key: str) -> list[str]:
    text = path.read_text(encoding="utf-8")
    match = re.search(rf"^{key}\s*=\s*\[(.*?)\]", text, re.DOTALL | re.MULTILINE)
    if not match:
        return []
    items = re.findall(r'"([^"]+)"|([0-9]+)', match.group(1))
    return [quoted or number for quoted, number in items]


def host_from_url(url: str) -> str:
    match = re.match(r"https?://([^/]+)/?", url)
    return match.group(1).lower() if match else ""


def check_inventory(
    docs: Path,
    inventory_path: Path,
    lychee_config: Path,
    sidebar: Path | None,
) -> list[str]:
    inventory = load_inventory(inventory_path)
    used = markdown_hosts(docs, sidebar)
    excluded = {
        host
        for url in toml_list(lychee_config, "exclude")
        if (host := host_from_url(url))
    }
    accepted = {
        int(value) for value in toml_list(lychee_config, "accept") if value.isdigit()
    }
    errors: list[str] = []
    for host in sorted(used):
        if host not in inventory:
            errors.append(f"{host}: used in docs but missing from links inventory")
    for host, spec in sorted(inventory.items()):
        klass = str(spec.get("class", ""))
        expected = spec.get("expected", [])
        if klass in {"internal", "deprecated"} and host not in excluded:
            errors.append(f"{host}: {klass} host must be excluded in lychee config")
        if klass in {"public", "auth"} and host not in excluded:
            for status in expected if isinstance(expected, list) else []:
                if status not in accepted:
                    errors.append(
                        f"{host}: expected status {status} is not accepted by lychee"
                    )
    return errors


def run(
    docs: Path,
    inventory: Path | None,
    lychee_config: Path | None,
    sidebar: Path | None,
    run_lychee: bool = False,
) -> int:
    if not inventory:
        print("link inventory: not configured")
        return 0
    if not inventory.is_file() or not lychee_config or not lychee_config.is_file():
        print("link inventory: inventory or lychee config missing")
        return 1
    errors = check_inventory(docs, inventory, lychee_config, sidebar)
    for error in errors:
        print(error)
    if errors:
        print(f"\n{len(errors)} link inventory error(s).")
        return 1
    print("link inventory: OK")
    if run_lychee:
        command = [
            "lychee",
            "--config",
            str(lychee_config),
            "--include-fragments=anchor-only",
            str(docs),
        ]
        if sidebar:
            command.append(str(sidebar))
        result = subprocess.run(command, check=False)
        return result.returncode
    return 0
