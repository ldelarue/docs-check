# docs-check

Documentation QA checks for Markdown and Zensical repositories.

`docs-check` provides one command for the checks that are easy to get wrong
across repositories:

- local Markdown links;
- front matter against a JSON schema;
- H1/title consistency, heading depth and code-fence languages;
- required sections per Diátaxis page type;
- Related-section links;
- weak words, first-person prose, long sentences and TODO markers;
- ordered-list continuity in the built site;
- external-link inventory and optional lychee execution.

## Install

```sh
uv tool install "git+https://github.com/ldelarue/docs-check@v0.1.0"
```

Or add it to a project:

```sh
uv add --dev "docs-check @ git+https://github.com/ldelarue/docs-check@v0.1.0"
```

## Use

Create `docs-check.toml` in the documentation repository:

```toml
[docs]
root = "."
docs = "docs"
schema = "schema/front-matter.schema.json"

[style]
strict = true
confluence = false
require_last_reviewed = false

[links]
inventory = "linkcheck/links.yml"
lychee_config = "linkcheck/lychee.toml"
sidebar = "linkcheck/sidebar-links.md"

[lists]
site_dir = "site"
```

Run:

```sh
docs-check site
docs-check style --strict
docs-check lists
docs-check links --lychee
docs-check all --strict
```

`docs-check links` checks the inventory and only runs `lychee` when `--lychee`
is passed. `docs-check lists` reads the built site; build it first.

## Development

```sh
mise install
mise test
mise lint
mise build
```

## License

Creative Commons Attribution 4.0 International (CC BY 4.0). See `LICENSE`.
