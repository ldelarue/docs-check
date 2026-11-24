from __future__ import annotations

from pathlib import Path

import typer

from . import __version__
from . import links as links_module
from . import lists as lists_module
from . import site as site_module
from . import style as style_module
from .config import load_config

app = typer.Typer(no_args_is_help=True, add_completion=False)


def _config(config: Path | None):
    return load_config(config)


@app.command()
def version() -> None:
    """Print the docs-check version."""
    typer.echo(__version__)


@app.command()
def site(
    config: Path | None = typer.Option(None, "--config", help="docs-check.toml"),
) -> None:
    """Check local Markdown links."""
    cfg = _config(config)
    raise typer.Exit(site_module.run(cfg.root, cfg.docs))


@app.command()
def style(
    config: Path | None = typer.Option(None, "--config", help="docs-check.toml"),
    strict: bool = typer.Option(False, "--strict", help="Fail on prose warnings"),
    json_output: bool = typer.Option(False, "--json", help="Emit JSON"),
    show_warnings: bool = typer.Option(False, "--show-warnings"),
    paths: list[str] = typer.Argument(None, help="Files or directories to check"),
) -> None:
    """Check front matter, headings, sections and prose."""
    cfg = _config(config)
    raise typer.Exit(
        style_module.run(
            style_module.StyleOptions(
                root=cfg.root,
                docs=cfg.docs,
                schema=cfg.schema,
                paths=paths or None,
                strict=strict or cfg.strict,
                json_output=json_output,
                show_warnings=show_warnings,
                confluence=cfg.confluence,
                require_last_reviewed=cfg.require_last_reviewed,
                enforce_sections=cfg.enforce_sections,
                enforce_external_link_sections=cfg.enforce_external_link_sections,
                allow_numbered_headings=cfg.allow_numbered_headings,
            )
        )
    )


@app.command()
def lists(
    config: Path | None = typer.Option(None, "--config", help="docs-check.toml"),
    site_dir: Path | None = typer.Option(
        None, "--site-dir", help="Built site directory"
    ),
    strict: bool = typer.Option(False, "--strict", help="Fail on warnings"),
) -> None:
    """Check ordered-list continuity in the built site."""
    cfg = _config(config)
    raise typer.Exit(
        lists_module.run(site_dir or cfg.site_dir or cfg.root / "site", strict)
    )


@app.command()
def links(
    config: Path | None = typer.Option(None, "--config", help="docs-check.toml"),
    lychee: bool = typer.Option(
        False, "--lychee", help="Run lychee after the inventory"
    ),
) -> None:
    """Check the external-link inventory and optionally run lychee."""
    cfg = _config(config)
    raise typer.Exit(
        links_module.run(
            cfg.docs, cfg.inventory, cfg.lychee_config, cfg.sidebar, lychee
        )
    )


@app.command()
def all_checks(
    config: Path | None = typer.Option(None, "--config", help="docs-check.toml"),
    strict: bool = typer.Option(False, "--strict", help="Fail on prose warnings"),
    lychee: bool = typer.Option(False, "--lychee", help="Run lychee"),
) -> None:
    """Run every configured check."""
    cfg = _config(config)
    failures = [
        site_module.run(cfg.root, cfg.docs),
        style_module.run(
            style_module.StyleOptions(
                root=cfg.root,
                docs=cfg.docs,
                schema=cfg.schema,
                strict=strict or cfg.strict,
                confluence=cfg.confluence,
                require_last_reviewed=cfg.require_last_reviewed,
                enforce_sections=cfg.enforce_sections,
                enforce_external_link_sections=cfg.enforce_external_link_sections,
                allow_numbered_headings=cfg.allow_numbered_headings,
            )
        ),
        lists_module.run(cfg.site_dir or cfg.root / "site", strict),
        links_module.run(
            cfg.docs, cfg.inventory, cfg.lychee_config, cfg.sidebar, lychee
        ),
    ]
    raise typer.Exit(1 if any(failures) else 0)


def main() -> None:
    app()


if __name__ == "__main__":
    main()
