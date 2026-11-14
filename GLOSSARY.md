# Grocy MCP Server

An MCP server that exposes Grocy as tools for AI agents, shipped as a Home Assistant add-on and as a standalone container. This glossary fixes the words used for versions and releases.

## Language

### Versioning

**Release**:
A published state of the project with one version number, a Git tag `vX.Y.Z`, a GitHub Release and a section in the changelog. Add-on, standalone container and Python package always carry the same version.
_Avoid_: Build, deployment, drop

**Beta phase**:
The period before 1.0.0, in which versions read `0.X.Y`. It ends when the tool surface is stable and the add-on is no longer `experimental`.
_Avoid_: Pre-release, alpha

**Patch release**:
A release that only changes `Y` in `0.X.Y`. It contains bug fixes only, so users can update without reading the changelog.
_Avoid_: Hotfix, minor update

**Minor release**:
A release that changes `X` in `0.X.Y` and resets `Y` to 0. It adds features or contains a breaking change, so users should read the changelog before updating.
_Avoid_: Major release (the major part stays 0 during the beta phase)

**Breaking change**:
A change that forces an existing MCP client or add-on setup to adapt: a tool or parameter renamed or removed, a changed response shape, a removed or renamed add-on option. Skills are part of this surface.
_Avoid_: Incompatible change

**Unreleased**:
The changelog section collecting user-visible changes made since the last release. A release renames it to the new version.
_Avoid_: Next, pending

**Internal change**:
A change to how the project is developed that users cannot observe, such as the dev environment or build setup. It is listed under `Internal` and never triggers a minor release on its own.
_Avoid_: Chore, misc
