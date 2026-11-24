from __future__ import annotations

from pathlib import Path

from docs_check import style


def _page(tmp_path: Path, body: str, front: str = "") -> Path:
    docs = tmp_path / "docs"
    docs.mkdir(exist_ok=True)
    page = docs / "page.md"
    page.write_text(f"---\n{front}---\n{body}", encoding="utf-8")
    return docs


def test_valid_explanation(tmp_path: Path) -> None:
    docs = _page(
        tmp_path,
        "# Test\n\nText.\n\n## Related\n\n- [Other](other.md)\n",
        'title: "Test"\ndiataxis: explanation\ndoc_status: reviewed\n',
    )
    code = style.run(style.StyleOptions(root=tmp_path, docs=docs))
    assert code == 0


def test_weak_word_and_numbered_heading(tmp_path: Path) -> None:
    docs = _page(
        tmp_path,
        "# Test\n\nThis is just a test.\n\n### 1. Step\n\n## Related\n\n- [Other](other.md)\n",
        'title: "Test"\ndiataxis: explanation\ndoc_status: reviewed\n',
    )
    code = style.run(style.StyleOptions(root=tmp_path, docs=docs))
    assert code == 1
