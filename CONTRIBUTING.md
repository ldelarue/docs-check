# Contributing

## Workflow

1. Create a branch from `main`.
2. Make the change.
3. Run the local gates:
   ```sh
   mise test
   mise lint
   ```
4. Open a pull request.

## Releases

Releases use release-please. Merging the release PR creates the tag and GitHub
Release, then the publish workflow attaches the wheel and sdist and moves the
`latest` branch.

## Scope

`docs-check` is the shared engine. Repository-specific policy belongs in each
consumer's `docs-check.toml`, not in this package.
