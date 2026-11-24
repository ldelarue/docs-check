from __future__ import annotations

from pathlib import Path

from docs_check import site


def test_local_links(tmp_path: Path) -> None:
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "index.md").write_text(
        "[ok](other.md)\n[bad](missing.md)\n", encoding="utf-8"
    )
    (docs / "other.md").write_text("# Other\n", encoding="utf-8")
    errors = site.check(tmp_path, docs)
    assert len(errors) == 1
    assert "missing.md" in errors[0]
