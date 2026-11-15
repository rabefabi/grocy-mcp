---
name: grocy-mcp-build-release
description: >
  Internal development skill of this repo. Use when cutting a release of the
  Grocy MCP server, when the user says "release", "bump the version" or
  "cut 0.X", and whenever you add a user-visible change that needs a
  CHANGELOG.md entry. Not shipped to MCP clients (those skills live in skills/).
---

# Grocy MCP: release and changelog

Rules and rationale: [ADR-058](../../../docs/adr/058-versioning-and-changelog.md).
Vocabulary: [GLOSSARY.md](../../../GLOSSARY.md).

## While developing: keep `Unreleased` current

For every `feat`, `fix` or breaking change, add a line under `## Unreleased` in
`CHANGELOG.md` in the **same commit**. Do not wait for the release.

- Sections, in this order: `Added`, `Changed`, `Fixed`, `Removed`, `Internal`.
  Create a section only when it has an entry.
- Write for a Home Assistant user reading the update dialog: what changed for
  them, not which function. English, one line each, no commit jargon.
- A breaking change goes under `Changed` or `Removed`, starts with
  **Breaking:** and says what the user has to do. ADR-058 point 3 defines
  what counts as breaking.
- `Internal` is for development-only changes worth finding later (dev
  environment, build setup). Not every `docs`/`test` commit belongs there.
- Skill changes in `skills/` count like tool changes.

## Cutting a release

Only when the user asks. Work on `main`, clean working tree.

1. **Read** `## Unreleased`. If it is empty, stop: there is nothing to release.
2. **Pick the version** from the current one in `config.yaml` (`0.X.Y`):
   - anything under `Added`, `Changed` or `Removed` → `0.(X+1).0`
   - only `Fixed` and/or `Internal` → `0.X.(Y+1)`
   - 1.0.0 only when the user says the tool surface is stable.
   Tell the user the version and why, and confirm it.
3. **Check the entries** against `git log vLAST..HEAD` (`vLAST` = latest tag).
   Add user-visible changes that are missing; flag entries that no longer match
   the code.
4. **Rename** `## Unreleased` to `## X.Y.Z – YYYY-MM-DD` and add a fresh empty
   `## Unreleased` above it. Nothing else in the entries changes.
5. **Bump the version** to `X.Y.Z` in `config.yaml` and `pyproject.toml`, then
   run `uv lock` so `uv.lock` follows, and `uv sync` so the installed package
   metadata matches. `tests/test_version.py` fails if anything disagrees.
6. **Commit** `chore(release): vX.Y.Z` with only those files.
7. **Tag** annotated: `git tag -a vX.Y.Z -m "vX.Y.Z"`.
8. **Push and publish** only with the user's go-ahead (it is outward-facing):
   `git push && git push origin vX.Y.Z`, then
   `gh release create vX.Y.Z --title vX.Y.Z --notes-file <section text>`, where
   the notes are the new changelog section without its heading.

Nothing is built or published elsewhere: no registry, no CI.
