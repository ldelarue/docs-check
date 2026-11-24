from __future__ import annotations

from docs_check.lists import analyze_html


def test_interrupted_ordered_list() -> None:
    html = """
    <article>
      <h2>Steps</h2>
      <ol><li>one</li></ol>
      <p>break</p>
      <ol><li>two</li></ol>
    </article>
    """
    warnings = analyze_html(html)
    assert len(warnings) == 1
    assert warnings[0]["heading"] == "Steps"
