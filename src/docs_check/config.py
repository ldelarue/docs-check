from __future__ import annotations

import tomllib
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class DocsCheckConfig:
    root: Path
    docs: Path
    schema: Path | None = None
    strict: bool = False
    confluence: bool = False
    require_last_reviewed: bool = False
    enforce_sections: bool = True
    enforce_external_link_sections: bool = True
    allow_numbered_headings: bool = False
    site_dir: Path | None = None
    inventory: Path | None = None
    lychee_config: Path | None = None
    sidebar: Path | None = None
    extra: dict = field(default_factory=dict)


def load_config(path: Path | None = None) -> DocsCheckConfig:
    config_path = path or Path.cwd() / "docs-check.toml"
    base = config_path.parent if config_path.is_file() else Path.cwd()
    data: dict = {}
    if config_path.is_file():
        data = tomllib.loads(config_path.read_text(encoding="utf-8"))

    docs = data.get("docs", {})
    style = data.get("style", {})
    links = data.get("links", {})
    lists = data.get("lists", {})

    def rel(value: str | None, default: str | None = None) -> Path | None:
        raw = value or default
        return (base / raw).resolve() if raw else None

    return DocsCheckConfig(
        root=rel(docs.get("root"), ".") or base,
        docs=rel(docs.get("docs"), "docs") or base / "docs",
        schema=rel(docs.get("schema"), "schema/front-matter.schema.json"),
        strict=bool(style.get("strict", False)),
        confluence=bool(style.get("confluence", False)),
        require_last_reviewed=bool(style.get("require_last_reviewed", False)),
        enforce_sections=bool(style.get("enforce_sections", True)),
        enforce_external_link_sections=bool(
            style.get("enforce_external_link_sections", True)
        ),
        allow_numbered_headings=bool(style.get("allow_numbered_headings", False)),
        site_dir=rel(lists.get("site_dir"), "site"),
        inventory=rel(links.get("inventory")),
        lychee_config=rel(links.get("lychee_config")),
        sidebar=rel(links.get("sidebar")),
        extra=data,
    )
