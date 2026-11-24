"""Documentation style checks for docs/.

The checker is intentionally dependency-free and covers the rules that are
cheap to verify mechanically:

- front matter contract validated against ``schema/front-matter.schema.json``
- H1 matches the front matter title
- heading depth
- numbered headings
- code fences have a language
- required sections per Diataxis type
- a Related section contains at least one internal link
- external links live under External tools or External resources
- no links to the non-rendered root archive/
- weak words, long sentences, first person in procedures
- TODO/WIP/TBD/FIXME markers

Structural rules, schema violations, and weak words are errors and block the
gate. First-person and long sentences are warnings and are reported but do not
block. Use --strict to make warnings fatal.

The package wrapper is ``docs-check style``. The module-level configuration is
set by ``run()`` so the same code works for any repository.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path.cwd()
DOCS = ROOT / "docs"
SCHEMA: Path | None = None
CONFLUENCE = False
REQUIRE_LAST_REVIEWED = False
ENFORCE_SECTIONS = True
ENFORCE_EXTERNAL_LINK_SECTIONS = True
ALLOW_NUMBERED_HEADINGS = False
REQUIRED_SECTIONS_OVERRIDE: dict[str, list[tuple[str, str]]] | None = None

DEFAULT_REQUIRED = ["title", "diataxis", "doc_status"]
DEFAULT_DIATAXIS = ["tutorial", "how-to", "reference", "explanation", "overview"]
DEFAULT_STATUS = ["stub", "migrated", "reviewed", "archive", "meta", "section"]

REQUIRED_SECTIONS = {
    "how-to": [
        ("prerequisites", r"^(?:prerequisites?|requirements?|before you start)$"),
        ("steps", r"^(?:steps?|procedure|runbook)$"),
        ("verify", r"^(?:verify|verification|check|validation|expected result)$"),
        ("related", r"^(?:related|see also|related pages|further reading)$"),
    ],
    "tutorial": [
        (
            "what-you-will-learn",
            r"^(?:what you will learn|learning outcomes|by the end)$",
        ),
        ("what-you-need", r"^(?:what you need|prerequisites?|requirements?)$"),
        ("walkthrough", r"^(?:walkthrough|guided practice|lesson)$"),
        ("checkpoint", r"^(?:checkpoint|result|verify)$"),
        ("next-steps", r"^(?:next steps?|related|see also)$"),
    ],
    "reference": [("related", r"^(?:related|see also|related pages|further reading)$")],
    "explanation": [
        ("related", r"^(?:related|see also|related pages|further reading)$")
    ],
}

RELATED_TITLES = {"related", "see also", "related pages", "further reading"}

ADR_STATUSES = ["proposed", "accepted", "rejected", "deprecated", "superseded"]
ADR_SECTIONS = [
    ("status", r"^status$"),
    ("context", r"^context$"),
    ("decision drivers", r"^decision drivers$"),
    ("considered options", r"^considered options$"),
    ("decision", r"^decision$"),
    ("consequences", r"^consequences$"),
    ("related", r"^(?:related|links|more information)$"),
]

POSTMORTEM_STATUSES = ["open", "completed", "closed"]
POSTMORTEM_SECTIONS = [
    ("summary", r"^summary$"),
    ("impact", r"^impact$"),
    ("timeline", r"^timeline$"),
    ("root cause", r"^root causes?$"),
    ("action items", r"^action items?$"),
    ("lessons learned", r"^lessons? learned$"),
    ("related", r"^(?:related|see also|related pages)$"),
]
POSTMORTEM_TITLE_DATE = re.compile(r"^(\d{4}-\d{2}-\d{2})\s+\S")
POSTMORTEM_FILE_DATE = re.compile(r"^(\d{4}-\d{2}-\d{2})-")

WEAK_WORDS = [
    "simply",
    "just",
    "easy",
    "easily",
    "obviously",
    "basically",
    "actually",
    "please note",
    "note that",
    "in order to",
    "and so on",
    "etc.",
]

# First-person and long sentences are advisory. Weak words are errors. Use
# --strict to make the remaining warnings fatal.
WARNING_RULES = {"first-person", "long-sentence"}

FIRST_PERSON = re.compile(r"\b(?:I|we|our|us|my|me)\b", re.IGNORECASE)
TODO_MARKER = re.compile(r"\b(TODO|WIP|TBD|FIXME|XXX)\b", re.IGNORECASE)
FENCE = re.compile(r"^\s*(`{3,}|~{3,})(.*)$")
HEADING = re.compile(r"^(#{1,6})\s+(.*)$", re.MULTILINE)
NUMBERED_HEADING = re.compile(r"^\s*\d{1,2}(?:[.)]|[-:])\s+")
LINK = re.compile(r"\]\(([^)\s]+)\)")


@dataclass(frozen=True)
class Violation:
    path: str
    rule: str
    detail: str

    def key(self) -> str:
        return self.rule


def load_schema_document() -> dict:
    if SCHEMA is None or not SCHEMA.is_file():
        return {}
    try:
        return json.loads(SCHEMA.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def schema_values(schema: dict) -> tuple[list[str], list[str], list[str], list[str]]:
    required = schema.get("required", DEFAULT_REQUIRED)
    props = schema.get("properties", {})
    diataxis = props.get("diataxis", {}).get("enum", DEFAULT_DIATAXIS)
    status = props.get("doc_status", {}).get("enum", DEFAULT_STATUS)
    adr_status = props.get("adr_status", {}).get("enum", ADR_STATUSES)
    return required, diataxis, status, adr_status


def load_schema() -> tuple[list[str], list[str], list[str], list[str]]:
    return schema_values(load_schema_document())


def _split_flow(text: str) -> list[str]:
    parts: list[str] = []
    buf: list[str] = []
    quote = ""
    for char in text:
        if quote:
            buf.append(char)
            if char == quote:
                quote = ""
        elif char in "\"'":
            quote = char
            buf.append(char)
        elif char == ",":
            parts.append("".join(buf).strip())
            buf = []
        else:
            buf.append(char)
    if buf:
        parts.append("".join(buf).strip())
    return [part for part in parts if part]


def _parse_scalar(raw: str) -> object:
    raw = raw.strip()
    if len(raw) >= 2 and raw[0] == raw[-1] and raw[0] in "\"'":
        return raw[1:-1]
    if raw.startswith("[") and raw.endswith("]"):
        inner = raw[1:-1].strip()
        return [_parse_scalar(part) for part in _split_flow(inner)] if inner else []
    if raw in {"true", "True"}:
        return True
    if raw in {"false", "False"}:
        return False
    if raw in {"null", "Null", "~"}:
        return None
    if re.fullmatch(r"-?\d+", raw):
        return int(raw)
    return raw


def parse_front_matter_typed(text: str) -> dict[str, object]:
    if not text.startswith("---"):
        return {}
    end = text.find("\n---", 3)
    if end == -1:
        return {}
    lines = text[3:end].strip("\n").splitlines()
    meta: dict[str, object] = {}
    index = 0
    while index < len(lines):
        line = lines[index]
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or line[:1] in {" ", "\t"}:
            index += 1
            continue
        key, separator, raw = line.partition(":")
        if not separator:
            index += 1
            continue
        key = key.strip()
        raw = raw.strip()
        if raw:
            meta[key] = _parse_scalar(raw)
            index += 1
            continue
        items: list[object] = []
        index += 1
        while index < len(lines):
            item = lines[index].strip()
            if item.startswith("- "):
                items.append(_parse_scalar(item[2:]))
                index += 1
            elif not item:
                index += 1
            else:
                break
        meta[key] = items
    return meta


def _type_ok(value: object, expected: str) -> bool:
    if expected == "string":
        return isinstance(value, str)
    if expected == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    if expected == "number":
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    if expected == "array":
        return isinstance(value, list)
    if expected == "object":
        return isinstance(value, dict)
    if expected == "boolean":
        return isinstance(value, bool)
    return True


def _matches(schema: object, value: object) -> bool:
    if not isinstance(schema, dict):
        return True
    if "not" in schema and _matches(schema["not"], value):
        return False
    if "const" in schema and value != schema["const"]:
        return False
    if "enum" in schema and value not in schema["enum"]:
        return False
    if "required" in schema and (
        not isinstance(value, dict)
        or any(key not in value for key in schema["required"])
    ):
        return False
    if "properties" in schema:
        if not isinstance(value, dict):
            return False
        for key, subschema in schema["properties"].items():
            if key in value and not _matches(subschema, value[key]):
                return False
    return True


def _is_uri(value: str) -> bool:
    parsed = urlparse(value)
    return bool(parsed.scheme and (parsed.netloc or parsed.path))


def validate_schema(meta: dict[str, object], schema: dict, rel: str) -> list[Violation]:
    out: list[Violation] = []
    for key in schema.get("required", []):
        if key not in meta or meta[key] is None or meta[key] == "":
            out.append(Violation(rel, "front-matter", f"missing {key}"))
    for key, value in meta.items():
        spec = schema.get("properties", {}).get(key)
        if not isinstance(spec, dict):
            continue
        expected = spec.get("type")
        if expected and not _type_ok(value, expected):
            out.append(
                Violation(
                    rel,
                    "front-matter",
                    f"invalid {key} {value!r} (expected {expected})",
                )
            )
            continue
        if "enum" in spec and value not in spec["enum"]:
            out.append(Violation(rel, "front-matter", f"invalid {key} {value!r}"))
        if isinstance(value, str):
            if "minLength" in spec and len(value) < spec["minLength"]:
                out.append(Violation(rel, "front-matter", f"invalid {key} {value!r}"))
            if "pattern" in spec and not re.search(spec["pattern"], value):
                out.append(Violation(rel, "front-matter", f"invalid {key} {value!r}"))
            if spec.get("format") == "date" and not re.fullmatch(
                r"\d{4}-\d{2}-\d{2}", value
            ):
                out.append(Violation(rel, "front-matter", f"invalid {key} {value!r}"))
            if spec.get("format") == "uri" and not _is_uri(value):
                out.append(Violation(rel, "front-matter", f"invalid {key} {value!r}"))
        if (
            isinstance(value, int)
            and not isinstance(value, bool)
            and "minimum" in spec
            and value < spec["minimum"]
        ):
            out.append(Violation(rel, "front-matter", f"invalid {key} {value!r}"))
        if isinstance(value, list) and isinstance(spec.get("items"), dict):
            item_type = spec["items"].get("type")
            if item_type:
                for item in value:
                    if not _type_ok(item, item_type):
                        out.append(
                            Violation(
                                rel,
                                "front-matter",
                                f"invalid {key} item {item!r}",
                            )
                        )
    for clause in schema.get("allOf", []):
        if isinstance(clause, dict) and "if" in clause and _matches(clause["if"], meta):
            out.extend(validate_schema(meta, clause.get("then", {}), rel))
    return out


def parse_front_matter(text: str) -> tuple[dict[str, str], str]:
    if not text.startswith("---"):
        return {}, text
    end = text.find("\n---", 3)
    if end == -1:
        return {}, text
    block = text[3:end].strip("\n")
    body = text[end + 4 :].lstrip("\n")
    meta: dict[str, str] = {}
    for line in block.splitlines():
        line = line.strip()
        if not line or line.startswith("#") or ":" not in line:
            continue
        key, value = line.split(":", 1)
        meta[key.strip()] = value.strip().strip("\"'")
    return meta, body


def strip_code(text: str) -> str:
    text = re.sub(r"```.*?```", " ", text, flags=re.DOTALL)
    text = re.sub(r"~~~.*?~~~", " ", text, flags=re.DOTALL)
    return re.sub(r"`[^`]*`", " ", text)


def prose(text: str) -> str:
    """Extract prose, keeping list items and blockquote lines separate.

    Bullet lists and blockquotes are not prose sentences. Treating each item as
    its own segment avoids reporting a 100-word "sentence" that is really a
    list, and keeps the sentence-length rule meaningful.
    """
    text = strip_code(text)
    text = re.sub(r"^\s{0,3}#{1,6}\s.*$", "\n", text, flags=re.MULTILINE)
    text = re.sub(r"^\s*\|.*\|\s*$", "\n", text, flags=re.MULTILINE)
    text = re.sub(r"!\[[^\]]*\]\([^)]*\)", " ", text)
    text = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", text)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"^\s*>\s?", "", text, flags=re.MULTILINE)
    text = re.sub(r"^\s*(?:[-*+]|\d+\.)\s+", "\n", text, flags=re.MULTILINE)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n\s*\n+", "\n", text)
    return text.strip()


def sentences(text: str) -> list[str]:
    out: list[str] = []
    for line in text.splitlines():
        for sentence in re.split(r"(?<=[.!?])\s+", line.strip()):
            if len(sentence.split()) >= 4:
                out.append(sentence)
    return out


def norm(value: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9 ]", "", value.lower())).strip()


def fence_violations(body: str) -> list[str]:
    bad = 0
    inside = False
    marker = ""
    for line in body.splitlines():
        match = FENCE.match(line)
        if not match:
            continue
        token, rest = match.group(1), match.group(2).strip()
        if not inside:
            inside = True
            marker = token[0]
            if not rest:
                bad += 1
        elif token[0] == marker and not rest:
            # Only a bare fence closes a block. A line such as ```text inside a
            # code sample is content, not a closing fence.
            inside = False
    return [f"{bad} code fence(s) without a language"] if bad else []


def external_links(body: str) -> list[str]:
    links: list[str] = []
    inside = False
    marker = ""
    for line in body.splitlines():
        match = FENCE.match(line)
        if match:
            token, rest = match.group(1), match.group(2).strip()
            if not inside:
                inside = True
                marker = token[0]
            elif token[0] == marker and not rest:
                inside = False
            continue
        if inside:
            continue
        line = re.sub(r"`[^`]*`", "", line)
        links.extend(re.findall(r"(?<!!)\[[^\]]*\]\((https?://[^)\s]+)\)", line))
        links.extend(re.findall(r"<(https?://[^>]+)>", line))
    return list(dict.fromkeys(links))


def related_without_link(body: str) -> bool:
    in_related = False
    has_link = False
    for line in body.splitlines():
        heading = HEADING.match(line)
        if heading and len(heading.group(1)) == 2:
            if in_related and not has_link:
                return True
            in_related = heading.group(2).strip().lower() in RELATED_TITLES
            has_link = False
            continue
        if in_related and LINK.search(line):
            has_link = True
    return in_related and not has_link


def section_text(body: str, title: str) -> str:
    out: list[str] = []
    inside = False
    for line in body.splitlines():
        match = HEADING.match(line)
        if match and len(match.group(1)) == 2:
            if inside:
                break
            inside = norm(match.group(2)) == norm(title)
            continue
        if inside:
            out.append(line)
    return "\n".join(out)


def walkthrough_missing_results(body: str) -> list[str]:
    missing: list[str] = []
    in_walkthrough = False
    current_step: str | None = None
    has_result = False
    steps_seen = False

    inside = False
    marker = ""
    for line in body.splitlines():
        fence = FENCE.match(line)
        if fence:
            token, rest = fence.group(1), fence.group(2).strip()
            if not inside:
                inside = True
                marker = token[0]
            elif token[0] == marker and not rest:
                inside = False
            continue
        if inside:
            continue
        match = HEADING.match(line)
        if match and len(match.group(1)) == 2:
            if in_walkthrough and current_step and not has_result:
                missing.append(current_step)
            title = norm(match.group(2))
            in_walkthrough = title in {"walkthrough", "guided practice", "lesson"}
            current_step = None
            has_result = False
            steps_seen = False
            continue
        if in_walkthrough and match and len(match.group(1)) == 3:
            if current_step and not has_result:
                missing.append(current_step)
            current_step = match.group(2).strip()
            has_result = False
            steps_seen = True
            continue
        if (
            in_walkthrough
            and current_step
            and re.search(r"\*\*(?:Result|You should see):?\*\*", line, re.IGNORECASE)
        ):
            has_result = True

    if in_walkthrough and current_step and not has_result:
        missing.append(current_step)
    if in_walkthrough and not steps_seen:
        missing.append("(no H3 steps)")
    return missing


def check_page(
    path: Path,
    rel: str,
    required: list[str],
    diataxis_values: list[str],
    status_values: list[str],
    adr_status_values: list[str],
    schema: dict | None = None,
) -> list[Violation]:
    text = path.read_text(encoding="utf-8")
    meta, body = parse_front_matter(text)
    out: list[Violation] = []
    if schema:
        out.extend(validate_schema(parse_front_matter_typed(text), schema, rel))

    for key in required:
        if not meta.get(key):
            out.append(Violation(rel, "front-matter", f"missing {key}"))

    diataxis = meta.get("diataxis", "")
    status = meta.get("doc_status", "")
    if diataxis and diataxis not in diataxis_values:
        out.append(Violation(rel, "front-matter", f"invalid diataxis {diataxis!r}"))
    if status and status not in status_values:
        out.append(Violation(rel, "front-matter", f"invalid doc_status {status!r}"))

    title = meta.get("title", "").strip()
    if title and re.match(r"^[\s\-*#>]", title):
        out.append(Violation(rel, "title", "starts with punctuation"))
    if title and re.match(r"^(?:how\s*to|howto|how-to)\b", title, re.IGNORECASE):
        out.append(Violation(rel, "title", "starts with How to"))

    if CONFLUENCE:
        source = meta.get("source", "confluence")
        if source not in {"confluence", "jira", "repo"}:
            out.append(Violation(rel, "front-matter", f"invalid source {source!r}"))
        if source == "jira" and not meta.get("jira_issue"):
            out.append(Violation(rel, "front-matter", "missing jira_issue"))
        if status not in {"meta", "section"} and source == "confluence":
            for key in ("confluence_page_id", "confluence_space", "confluence_url"):
                if not meta.get(key):
                    out.append(Violation(rel, "front-matter", f"missing {key}"))

    if REQUIRE_LAST_REVIEWED:
        if status == "reviewed" and not meta.get("last_reviewed"):
            out.append(Violation(rel, "front-matter", "missing last_reviewed"))
        if meta.get("last_reviewed") and not re.fullmatch(
            r"\d{4}-\d{2}-\d{2}", meta["last_reviewed"]
        ):
            out.append(
                Violation(
                    rel,
                    "front-matter",
                    f"invalid last_reviewed {meta['last_reviewed']!r}",
                )
            )

    h1 = re.search(r"^#\s+(.*)$", body, re.MULTILINE)
    if not h1:
        out.append(Violation(rel, "h1", "missing H1"))
    elif meta.get("title") and norm(h1.group(1)) != norm(meta["title"]):
        out.append(
            Violation(rel, "h1", f"H1 {h1.group(1)!r} != title {meta['title']!r}")
        )

    depths = [len(m.group(1)) for m in HEADING.finditer(body)]
    if any(d > 3 for d in depths):
        out.append(Violation(rel, "heading-depth", "heading deeper than H3"))

    if not ALLOW_NUMBERED_HEADINGS:
        for match in HEADING.finditer(body):
            if NUMBERED_HEADING.match(match.group(2)):
                out.append(Violation(rel, "numbered-heading", match.group(2).strip()))

    if status not in {"archive", "stub"}:
        for detail in fence_violations(body):
            out.append(Violation(rel, "code-fence", detail))

    sections = REQUIRED_SECTIONS_OVERRIDE or REQUIRED_SECTIONS
    if ENFORCE_SECTIONS and status in {"migrated", "reviewed"} and diataxis in sections:
        headings = "\n".join(
            m.group(2) for m in HEADING.finditer(body) if len(m.group(1)) <= 3
        )
        for name, pattern in sections[diataxis]:
            if not re.search(pattern, headings, re.IGNORECASE | re.MULTILINE):
                out.append(Violation(rel, "section", f"missing {name}"))
        if related_without_link(body):
            out.append(Violation(rel, "related-link", "Related section has no link"))

    if ENFORCE_EXTERNAL_LINK_SECTIONS and status in {"migrated", "reviewed"}:
        related_text = "\n".join(
            section_text(body, title)
            for title in ("Related", "Links", "See also", "Next steps")
        )
        external_text = "\n".join(
            section_text(body, title)
            for title in ("External tools", "External resources")
        )
        for url in external_links(body):
            if url in related_text:
                out.append(
                    Violation(
                        rel,
                        "external-link-section",
                        f"{url} is in an internal-link section; move it to External tools",
                    )
                )
            elif url not in external_text:
                out.append(Violation(rel, "external-link-section", url))
        if related_text:
            links = re.findall(r"\]\(([^)\s]+)\)", related_text)
            if links and not any(
                not link.startswith(("http://", "https://")) for link in links
            ):
                out.append(
                    Violation(
                        rel,
                        "related-internal-link",
                        "Related section has no internal documentation link",
                    )
                )

    if status in {"migrated", "reviewed"} and diataxis == "tutorial":
        for step in walkthrough_missing_results(body):
            out.append(
                Violation(rel, "tutorial-result", f"step {step!r} has no Result")
            )

    if rel.startswith("explanation/decisions/") and not rel.endswith("index.md"):
        for key in ("adr_status", "adr_date"):
            if not meta.get(key):
                out.append(Violation(rel, "adr-front-matter", f"missing {key}"))
        adr_status = meta.get("adr_status", "")
        if adr_status and adr_status not in adr_status_values:
            out.append(
                Violation(rel, "adr-front-matter", f"invalid adr_status {adr_status!r}")
            )
        if meta.get("adr_date") and not re.fullmatch(
            r"\d{4}-\d{2}-\d{2}", meta["adr_date"]
        ):
            out.append(
                Violation(
                    rel, "adr-front-matter", f"invalid adr_date {meta['adr_date']!r}"
                )
            )
        headings = "\n".join(
            m.group(2) for m in HEADING.finditer(body) if len(m.group(1)) <= 3
        )
        for name, pattern in ADR_SECTIONS:
            if not re.search(pattern, headings, re.IGNORECASE | re.MULTILINE):
                out.append(Violation(rel, "adr-section", f"missing {name}"))
        status_text = section_text(body, "Status")
        if not re.search(
            r"\b(?:proposed|accepted|rejected|deprecated|superseded)\b",
            status_text,
            re.IGNORECASE,
        ):
            out.append(
                Violation(rel, "adr-status", "Status section does not state the status")
            )

    if meta.get("postmortem_status"):
        postmortem_status = meta["postmortem_status"]
        if postmortem_status not in POSTMORTEM_STATUSES:
            out.append(
                Violation(
                    rel,
                    "postmortem-front-matter",
                    f"invalid postmortem_status {postmortem_status!r}",
                )
            )
        for key in ("incident_id", "incident_date", "postmortem_date", "severity"):
            if not meta.get(key):
                out.append(Violation(rel, "postmortem-front-matter", f"missing {key}"))
        for key in ("incident_date", "postmortem_date"):
            if meta.get(key) and not re.fullmatch(r"\d{4}-\d{2}-\d{2}", meta[key]):
                out.append(
                    Violation(
                        rel,
                        "postmortem-front-matter",
                        f"invalid {key} {meta[key]!r}",
                    )
                )
        title_date = POSTMORTEM_TITLE_DATE.match(meta.get("title", ""))
        if not title_date:
            out.append(
                Violation(
                    rel,
                    "postmortem-title-date",
                    "title must start with YYYY-MM-DD",
                )
            )
        elif meta.get("incident_date") and title_date.group(1) != meta["incident_date"]:
            out.append(
                Violation(
                    rel,
                    "postmortem-title-date",
                    f"title date {title_date.group(1)} != incident_date {meta['incident_date']}",
                )
            )
        file_date = POSTMORTEM_FILE_DATE.match(Path(rel).name)
        if not file_date:
            out.append(
                Violation(
                    rel,
                    "postmortem-filename-date",
                    "filename must start with YYYY-MM-DD-",
                )
            )
        elif meta.get("incident_date") and file_date.group(1) != meta["incident_date"]:
            out.append(
                Violation(
                    rel,
                    "postmortem-filename-date",
                    f"filename date {file_date.group(1)} != incident_date {meta['incident_date']}",
                )
            )
        if status in {"migrated", "reviewed"}:
            headings = "\n".join(
                m.group(2) for m in HEADING.finditer(body) if len(m.group(1)) <= 3
            )
            for name, pattern in POSTMORTEM_SECTIONS:
                if not re.search(pattern, headings, re.IGNORECASE | re.MULTILINE):
                    out.append(Violation(rel, "postmortem-section", f"missing {name}"))

    if (
        status in {"migrated", "reviewed"}
        and diataxis in {"how-to", "reference"}
        and not re.search(r"/(?:decisions|adr)/", rel)
    ):
        clean = prose(body)
        if FIRST_PERSON.search(clean):
            out.append(
                Violation(
                    rel,
                    "first-person",
                    "first person in a procedure or reference",
                )
            )

    clean = prose(body)
    for word in WEAK_WORDS:
        if re.search(r"(?<!\w)" + re.escape(word) + r"(?!\w)", clean, re.IGNORECASE):
            out.append(Violation(rel, "weak-word", word))
    long_sentences = [s for s in sentences(clean) if len(s.split()) > 30]
    if long_sentences:
        out.append(
            Violation(
                rel,
                "long-sentence",
                f"{len(long_sentences)} sentence(s) over 30 words",
            )
        )
    if re.search(r"(?<!\w)jira(?!\w)", clean):
        out.append(Violation(rel, "term-case", "use Jira"))
    if status != "stub":
        markers = sorted({m.group(1).upper() for m in TODO_MARKER.finditer(clean)})
        for marker in markers:
            out.append(Violation(rel, "todo-marker", marker))

    for href in LINK.findall(body):
        if re.search(r"(?:^|/)\.\./(?:\.\./)*archive/", href):
            out.append(Violation(rel, "archive-link", href))

    return out


def iter_pages(paths: list[str] | None) -> list[tuple[Path, str]]:
    if paths:
        selected = []
        for value in paths:
            path = Path(value)
            if not path.is_absolute():
                path = ROOT / path
            if path.is_dir():
                selected.extend(
                    (p, p.relative_to(DOCS).as_posix())
                    for p in sorted(path.rglob("*.md"))
                )
            elif path.suffix == ".md":
                selected.append((path, path.relative_to(DOCS).as_posix()))
        return selected
    return [(p, p.relative_to(DOCS).as_posix()) for p in sorted(DOCS.rglob("*.md"))]


@dataclass
class StyleOptions:
    root: Path
    docs: Path
    schema: Path | None = None
    paths: list[str] | None = None
    strict: bool = False
    json_output: bool = False
    show_warnings: bool = False
    confluence: bool = False
    require_last_reviewed: bool = False
    enforce_sections: bool = True
    enforce_external_link_sections: bool = True
    allow_numbered_headings: bool = False
    required_sections: dict[str, list[tuple[str, str]]] | None = None


def run(options: StyleOptions) -> int:
    global ROOT, DOCS, SCHEMA, CONFLUENCE, REQUIRE_LAST_REVIEWED
    global ENFORCE_SECTIONS, ENFORCE_EXTERNAL_LINK_SECTIONS
    global ALLOW_NUMBERED_HEADINGS, REQUIRED_SECTIONS_OVERRIDE
    ROOT = options.root.resolve()
    DOCS = options.docs.resolve()
    SCHEMA = options.schema.resolve() if options.schema else None
    CONFLUENCE = options.confluence
    REQUIRE_LAST_REVIEWED = options.require_last_reviewed
    ENFORCE_SECTIONS = options.enforce_sections
    ENFORCE_EXTERNAL_LINK_SECTIONS = options.enforce_external_link_sections
    ALLOW_NUMBERED_HEADINGS = options.allow_numbered_headings
    REQUIRED_SECTIONS_OVERRIDE = options.required_sections

    schema_document = load_schema_document()
    required, diataxis_values, status_values, adr_status_values = schema_values(
        schema_document
    )
    violations: list[Violation] = []
    for path, rel in iter_pages(options.paths):
        if not path.is_file():
            continue
        violations.extend(
            check_page(
                path,
                rel,
                required,
                diataxis_values,
                status_values,
                adr_status_values,
                schema_document,
            )
        )
    violations = list(dict.fromkeys(violations))

    errors = [v for v in violations if v.rule not in WARNING_RULES]
    warnings = [v for v in violations if v.rule in WARNING_RULES]

    if options.json_output:
        print(
            json.dumps(
                {
                    "errors": [v.__dict__ for v in errors],
                    "warnings": [v.__dict__ for v in warnings],
                },
                indent=2,
            )
        )
    else:
        for item in sorted(errors, key=lambda v: (v.path, v.rule, v.detail)):
            print(f"{item.path}: {item.rule}: {item.detail}")
        if options.show_warnings:
            for item in sorted(warnings, key=lambda v: (v.path, v.rule, v.detail)):
                print(f"{item.path}: warning: {item.rule}: {item.detail}")
        counts = {}
        for item in warnings:
            counts[item.rule] = counts.get(item.rule, 0) + 1
        summary = ", ".join(f"{k}={v}" for k, v in sorted(counts.items())) or "none"
        if errors:
            print(f"\n{len(errors)} structural error(s).")
        else:
            print("style checks passed (0 structural errors).")
        print(f"prose warnings: {summary}")

    failed = bool(errors) or (options.strict and bool(warnings))
    return 1 if failed else 0
