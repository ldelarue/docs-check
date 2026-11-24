from __future__ import annotations

from pathlib import Path

from docs_check.links import check_inventory


def test_inventory_and_lychee_match(tmp_path: Path) -> None:
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "index.md").write_text("[x](https://example.com/page)\n", encoding="utf-8")
    inventory = tmp_path / "links.yml"
    inventory.write_text(
        "hosts:\n  example.com:\n    class: public\n    expected: [200]\n",
        encoding="utf-8",
    )
    lychee = tmp_path / "lychee.toml"
    lychee.write_text("accept = [200]\nexclude = []\n", encoding="utf-8")
    assert check_inventory(docs, inventory, lychee, None) == []


def test_missing_inventory_host(tmp_path: Path) -> None:
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "index.md").write_text("[x](https://example.com/page)\n", encoding="utf-8")
    inventory = tmp_path / "links.yml"
    inventory.write_text("hosts: {}\n", encoding="utf-8")
    lychee = tmp_path / "lychee.toml"
    lychee.write_text("accept = []\nexclude = []\n", encoding="utf-8")
    errors = check_inventory(docs, inventory, lychee, None)
    assert errors
    assert "example.com" in errors[0]
