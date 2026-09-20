# Release process

STAC Scout releases are release-branch-driven and build-once.

## One-time PyPI setup

PyPI Trusted Publishing must authorize exactly this GitHub identity:

- PyPI project: `stac-scout`
- owner: `GeoGeekLab`
- repository: `stac-scout`
- workflow: `release.yml`
- environment: `pypi`

For a first publication, configure a pending Trusted Publisher on PyPI with those values.
No long-lived PyPI API token is required or expected.

## Release contract

1. Merge a release-ready commit to `main`.
2. Create branch `release/vX.Y.Z` from that exact `main` commit, where `X.Y.Z` matches `project.version`.
3. The Release workflow validates the branch/version match and reruns deterministic quality gates and evals.
4. It builds wheel and sdist exactly once.
5. It verifies the wheel's version and packaged registry data.
6. It records SHA-256 checksums and creates GitHub artifact provenance attestations.
7. The exact built distributions are published to PyPI through OIDC Trusted Publishing.
8. Only after PyPI succeeds, the workflow creates tag `vX.Y.Z` on the same commit and attaches those same files and checksums to the GitHub Release.

A release is incomplete if any of these jobs fails.

## Action pinning decision

Core GitHub-maintained actions use current Node 24-capable major releases and are covered by
Dependabot. Full commit-SHA pinning is intentionally deferred because it would add maintenance
overhead without changing the release identity contract; it can be adopted later if the project
requires a stricter SLSA-style policy.

## OpenSSF Scorecard decision

OpenSSF Scorecard was evaluated for this hardening cycle. It is not added as a merge gate for
v0.5.0: the actionable controls are implemented directly through protected PRs, deterministic CI,
Dependabot, dependency review, CodeQL, OIDC publishing, build-once artifacts, checksums, and
signed GitHub attestations. Scorecard can be added later as an external reporting signal.
