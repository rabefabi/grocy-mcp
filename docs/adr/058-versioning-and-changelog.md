# ADR-058: Versioning and Changelog

**Status:** Accepted
**Date:** 2026-11-14
**Deciders:** Maintainer

## Context

The project ships as a Home Assistant add-on and as a standalone container.
Home Assistant offers an update whenever `version` in `config.yaml` changes and
shows `CHANGELOG.md` from the add-on directory in the update dialog. Until now
the version was a bare `0.1.0`, kept by hand in four places, with no rule for
when it changes and no tags.

Users of the add-on want to know whether an update is safe to install blindly
or whether they should read what changed first.

## Decision

1. **One version for the whole project.** Add-on, standalone container and
   Python package share it. `config.yaml` is the source; `pyproject.toml`,
   `uv.lock` and the runtime value follow it. A test asserts they agree.
2. **`0.X.Y` during the beta phase.** `Y` is bumped for bug fixes only, so a
   patch update is safe to install without reading. `X` is bumped for new
   features and for breaking changes, and resets `Y`. 1.0.0 is reserved for a
   stable tool surface; from then on regular SemVer applies. The public
   interface is what MCP clients and add-on users see: tools, parameters,
   response shapes, add-on options and the skills in `skills/`.
3. **Keep a Changelog, in English, written for users.** `Unreleased` is
   maintained continuously by the coding agent and reviewed by the human at
   merge or before push. A release only renames its heading. Breaking changes
   carry a **Breaking:** prefix. Development-only changes go under `Internal`.
4. **The bump follows the changelog.** Anything under `Added`, `Changed` or
   `Removed` bumps `X`; `Fixed` and `Internal` alone bump `Y`.
5. **Releases are tagged.** `vX.Y.Z` on the release commit on `main`, plus a
   GitHub Release whose text is the changelog section. There is no registry and
   no CI, so nothing is published beyond that.
6. **The release procedure is agent instructions, not a script.** It lives in
   the dev skill `.claude/skills/grocy-mcp-build-release/`.

## Alternatives considered

- **Changelog generated from Conventional Commits** (git-cliff, release-please):
  less writing, but entries read like commit titles, and a one-person project
  without CI does not earn the setup.
- **Strict SemVer from 0.1.0** (patch for fixes, minor for features, breaking
  allowed in minor): loses the signal that matters to add-on users, which is
  "can I update without reading?".
- **Separate versions for add-on and standalone image:** the code is identical,
  so two numbers would only create a mapping to maintain.

## Consequences

- Every user-visible commit touches `CHANGELOG.md`; this is a convention in
  `CLAUDE.md`, not enforced by tooling.
- The Home Assistant update dialog shows the whole file, so entries must make
  sense to someone who does not know the code base.
- Changing the beta numbering later (for example at 1.0.0) is cheap; the
  tag and changelog history stay as they are.
