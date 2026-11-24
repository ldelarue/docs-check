from __future__ import annotations

import pathlib
from html.parser import HTMLParser


class ListParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.article_depth = 0
        self.li_depth = 0
        self.in_heading = False
        self.heading_buf: list[str] = []
        self.heading = ""
        self.in_p = False
        self.p_has_text = False
        self.p_strong_only = False
        self.in_strong = False
        self.strong_buf: list[str] = []
        self.label = ""
        self.ol_stack: list[dict] = []
        self.lists: list[dict] = []

    def handle_starttag(self, tag: str, attrs) -> None:
        if tag == "article":
            self.article_depth += 1
        elif tag in ("h2", "h3") and self.article_depth:
            self.in_heading = True
            self.heading_buf = []
        elif tag == "p" and self.article_depth:
            self.in_p = True
            self.p_has_text = False
            self.p_strong_only = True
        elif (
            tag == "strong" and self.article_depth and self.in_p and self.li_depth == 0
        ):
            self.in_strong = True
            self.strong_buf = []
        elif tag == "ol" and self.article_depth:
            top = self.li_depth == 0
            record = {
                "heading": self.heading,
                "label": self.label,
                "items": 0,
                "top": top,
            }
            self.ol_stack.append(record)
            if top:
                self.lists.append(record)
        elif tag == "li" and self.article_depth:
            self.li_depth += 1
            if self.ol_stack and self.ol_stack[-1]["top"]:
                self.ol_stack[-1]["items"] += 1

    def handle_endtag(self, tag: str) -> None:
        if tag == "article":
            self.article_depth = max(0, self.article_depth - 1)
        elif tag in ("h2", "h3") and self.in_heading:
            self.heading = " ".join("".join(self.heading_buf).split())
            self.in_heading = False
        elif tag == "p" and self.article_depth:
            self.in_p = False
            self.p_strong_only = False
        elif tag == "strong" and self.in_strong:
            text = " ".join("".join(self.strong_buf).split())
            if self.p_strong_only and not self.p_has_text and text:
                self.label = text
            self.in_strong = False
        elif tag == "ol" and self.ol_stack:
            self.ol_stack.pop()
        elif tag == "li" and self.article_depth:
            self.li_depth = max(0, self.li_depth - 1)

    def handle_data(self, data: str) -> None:
        if self.in_heading:
            self.heading_buf.append(data)
        elif self.in_strong:
            self.strong_buf.append(data)
        elif self.in_p and data.strip():
            self.p_has_text = True
            self.p_strong_only = False


def analyze_html(html: str) -> list[dict]:
    parser = ListParser()
    parser.feed(html)
    groups: dict[tuple[str, str], list[dict]] = {}
    for record in parser.lists:
        groups.setdefault((record["heading"], record["label"]), []).append(record)
    warnings = []
    for (heading, label), records in groups.items():
        if len(records) > 1:
            warnings.append(
                {
                    "heading": heading or "(no heading)",
                    "label": label,
                    "items": [record["items"] for record in records],
                }
            )
    return warnings


def run(site_dir: pathlib.Path, strict: bool = False) -> int:
    if not site_dir.exists():
        print(f"{site_dir} does not exist; build the site first.")
        return 0
    warnings = []
    for path in sorted(site_dir.rglob("index.html")):
        try:
            html = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        for warning in analyze_html(html):
            warnings.append((path, warning))
    for path, warning in warnings:
        label = f" / {warning['label']}" if warning["label"] else ""
        print(
            f"{path}: {warning['heading']}{label}: "
            f"{len(warning['items'])} ordered lists (items: {warning['items']})"
        )
    if warnings:
        print(f"\n{len(warnings)} ordered-list continuity warning(s).")
    else:
        print("ordered-list continuity: OK")
    return 1 if strict and warnings else 0
