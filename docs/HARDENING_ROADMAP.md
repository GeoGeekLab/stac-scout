# v0.5.0 Hardening Roadmap

This roadmap converts the 2026-09-20 repository audit into explicit engineering work.

The purpose of v0.5.0 is not feature expansion. It is to make STAC Scout's public contracts, scientific semantics, network behavior, provenance, release process, and repository governance match the confidence implied by its current positioning.

## Release principle

v0.5.0 is a hardening release.

Until the exit criteria below are satisfied:

- do not add new providers unless a provider is needed to prove an abstraction;
- do not add new task archetypes unless a task is needed for a regression case;
- do not describe an accepted request field as enforced unless it is actually evaluated;
- do not treat metadata as evidence;
- do not hide UNKNOWN by coercing it to PASS or FAIL;
- do not weaken deterministic behavior to make examples look better.

## Priority definitions

- **P0 — correctness / contract:** can produce a scientifically wrong result, silently ignore a public constraint, or misrepresent reproducibility.
- **P1 — robustness / engineering:** can produce misleading failures, fragile network behavior, weak release security, or difficult maintenance.
- **P2 — adoption / developer experience:** improves installation, documentation, discoverability, and contributor workflow after correctness is stable.

## Phase 1 — Governance baseline

Status: in progress on the v0.5.0 hardening governance PR.

Deliverables:

- pull request template with correctness, testing, compatibility, provenance, and security checks;
- structured issue forms for bugs, scientific/correctness reports, and feature requests;
- security reporting policy;
- contributor workflow requiring narrow PRs and explicit local checks;
- this roadmap as the canonical hardening scope;
- tracking issues for all phases;
- documented repository settings that must be enabled in GitHub Settings.

Repository settings to enable:

1. Protect `main` with a repository ruleset.
2. Require changes to enter through pull requests.
3. Require CI status checks before merge.
4. Initially require **0 approvals** while the project has one maintainer; do not create an impossible self-review gate.
5. Block force pushes and branch deletion for `main`.
6. Prefer squash merges for a linear, reviewable history.
7. Enable automatic deletion of merged branches.
8. Enable "update pull request branch" when supported.
9. Enable GitHub private vulnerability reporting.
10. Add CODEOWNERS only when there is at least one independent reviewer able to review the owner/maintainer's changes.

Exit criteria:

- all hardening work is traceable to issues;
- non-trivial changes use feature branches and PRs;
- CI is a merge gate, not merely an informational workflow.

## Phase 2 — Request and constraint semantics

### P0-01: Enforce every public constraint or make it explicitly non-enforcing

Current public request fields include:

- `data_type`
- `required_measurements`
- `max_spatial_resolution_m`
- `max_cloud_cover`
- `access`
- `max_data_volume_bytes`
- `preferences`

Audit finding: only a subset is currently enforced by `evaluate_constraints()`. The generic STAC search path also does not consistently push applicable constraints to provider queries.

Required work:

- define the authoritative semantics of every request field;
- separate hard constraints from preferences;
- represent the evaluation of each hard constraint as PASS / FAIL / UNKNOWN;
- never silently accept an unsupported or unevaluated hard constraint;
- document which constraints can be evaluated at Collection level, Item level, Asset level, or only during planning.

### P0-02: Make task-derived modality enforceable

Audit finding: task advice can derive `DataType.SAR`, but normalized collection cards and constraint evaluation do not currently guarantee that the modality participates in suitability filtering.

Required work:

- normalize defensible modality evidence;
- preserve UNKNOWN when metadata is insufficient;
- evaluate requested/derived data type as a real suitability constraint;
- add optical-vs-SAR mismatch regression cases.

### P0-03: Separate candidate generation, constraint evaluation, and ranking

Audit finding: discovery ranking is currently a deterministic token-overlap score and can rank a candidate highly even when a hard constraint fails.

Required pipeline:

`candidate generation -> evidence normalization -> hard-constraint evaluation -> exclude FAIL -> rank PASS/UNKNOWN -> live verification`

Ranking must remain deterministic and inspectable.

### P0-04: Tighten request validation

Required work:

- define supported AOI geometry types explicitly;
- validate non-empty geometry and invalid rings;
- define WGS84 expectations;
- require timezone-aware datetimes;
- normalize datetimes to UTC;
- reject or explicitly handle mixed/naive timezone input;
- test malformed provider/request metadata separately from user validation failures.

## Phase 3 — Geospatial and raster correctness

### P0-05: Make AOI coverage topology safe

Audit finding: area measurement is geodesic, but geometric intersection is performed by Shapely on lon/lat coordinates. This can fail around the antimeridian, poles, and very large geometries.

Mandatory regression cases:

- antimeridian-crossing Polygon;
- antimeridian-crossing MultiPolygon;
- polar AOI;
- polygon holes;
- invalid/self-intersecting geometry;
- empty geometry;
- unsupported Point/LineString AOIs;
- very large AOI.

The implementation must define how longitude wrapping and topology are normalized before coverage is computed.

### P0-06: Separate source-resolution acceptance from output resolution

Audit finding: `max_spatial_resolution_m` is used both as an acceptance threshold and as the generated load/output resolution.

Required work:

- replace ambiguous semantics with separate concepts such as `max_source_resolution_m` and `target_resolution_m`;
- make target CRS and resampling policy explicit where required;
- provide a compatibility/migration decision for the existing field.

### P0-07: Stop using collection-wide minimum GSD as measurement suitability

Audit finding: selecting `min(gsd)` across a collection can allow an unrelated high-resolution band to make a lower-resolution requested measurement appear suitable.

Required work:

- retain per-band/per-asset resolution evidence when available;
- evaluate resolution against the assets/measurements that will actually be used;
- return UNKNOWN when the relevant measurement resolution cannot be established.

### P0-08: Make asset selection evidence-based

Audit finding: when multiple assets match a measurement, current selection can degrade to lexicographic key order.

Required tie-break evidence should consider, where available:

- exact common_name match;
- declared band name;
- asset roles;
- GSD;
- media type;
- raster metadata;
- provider-specific rules.

The selected asset must retain an inspectable reason.

### P0-09: Make resampling semantics data-aware

Audit finding: a short name allowlist decides nearest-neighbor vs bilinear and can misclassify QA/classification bands such as SCL, QA60, Fmask, or pixel_qa.

Required work:

- derive categorical/continuous semantics from metadata, task/provider rules, or explicit user input;
- use nearest-neighbor for categorical/mask/QA data;
- do not silently apply bilinear when semantics are unknown;
- add regression cases for common QA/classification naming conventions.

## Phase 4 — Provider and federation robustness

### P1-01: Replace broad provider exception swallowing with typed failure boundaries

Audit finding: federation catches broad `Exception` and can misreport an internal programming bug as a provider failure.

Define typed failure classes for at least:

- network/timeout;
- authentication/authorization;
- rate limiting;
- provider protocol;
- malformed metadata;
- unsupported capability.

Unexpected internal exceptions must remain conspicuous.

### P1-02: Unify network policy

Required work:

- per-provider connect/read timeout;
- bounded retry only for appropriate transient failures;
- exponential backoff with jitter;
- explicit behavior for 429 and Retry-After;
- bounded federation concurrency;
- overall request deadline;
- deterministic provider failure reporting.

### P1-03: Harden malformed metadata boundaries

Examples:

- invalid provider datetimes;
- non-object catalog roots;
- malformed links/assets/extensions.

Provider data errors must not be confused with user request errors.

## Phase 5 — Provenance and replay

### P0-10: Version the manifest schema

Add an explicit manifest schema version and compatibility policy.

### P0-11: Record enough evidence to interpret replay

Manifest should capture, where relevant:

- canonicalized request/query;
- provider/catalog identity and capabilities;
- search limit;
- pagination/completeness/truncation state;
- item IDs;
- selected asset keys;
- asset metadata snapshot needed for the decision;
- collection/product fingerprint where defensible;
- access plan;
- output CRS/resolution;
- resampling decisions;
- volume estimate;
- assumptions and warnings.

### P0-12: Eliminate false replay drift from result truncation/order

Audit finding: replay defaults can compare a prior observed set to a newly truncated result set and report false missing/new items.

Required work:

- distinguish complete result set from sampled/truncated observation;
- preserve pagination and limit semantics;
- define stable comparison behavior when completeness cannot be proven.

## Phase 6 — Tests and evaluation corpus

### P1-04: Expand regression coverage around decision semantics

Coverage percentage alone is not the acceptance criterion.

Mandatory cases include:

- SAR requested against optical-only collection;
- optical requested against SAR-only collection;
- missing cloud metadata;
- cloud threshold PASS / FAIL / UNKNOWN;
- missing required bands;
- preferred bands missing but hard requirements satisfied;
- same DOI exact identity;
- malformed/invalid DOI;
- aliases/probable duplicates;
- multiple temporal intervals;
- multiple bboxes;
- antimeridian and polar AOIs;
- empty Item results;
- more than 100 Items;
- provider timeout;
- provider 429;
- partial federation failure;
- categorical resampling;
- missing `file:size`;
- volume budget exceeded;
- explicit user constraint conflicting with task defaults;
- malformed provider metadata.

### P1-05: Raise weak-module test depth

Audit hotspots include CLI and selected planning/catalog modules. Add branch-oriented tests where behavior matters rather than chasing coverage mechanically.

### P1-06: Expand the deterministic eval corpus

The eval corpus should become a public compatibility contract for geospatial dataset decisions, not a demo fixture.

## Phase 7 — Release and supply-chain hardening

### P1-07: Single-source package version

Audit finding: version information is duplicated between project metadata and package code.

Use one authoritative version source.

### P1-08: Modernize Python support matrix

Required work:

- test supported stable Python releases;
- keep classifiers synchronized with CI;
- use pre-release Python as an allowed-failure compatibility signal before making it required.

### P1-09: Build once, publish the same artifacts

Release pipeline should:

1. run quality checks and deterministic evals;
2. build wheel and sdist once;
3. verify packaged registry data;
4. publish those exact artifacts to PyPI via Trusted Publishing/OIDC;
5. attach the same artifacts to the GitHub Release;
6. produce provenance/attestation where supported.

Do not rely on a long-lived PyPI API token when Trusted Publishing is available.

### P1-10: Harden GitHub Actions and dependencies

Required work:

- update deprecated action versions;
- consider pinning third-party actions to full commit SHAs;
- add Dependabot or equivalent dependency update automation;
- add CodeQL;
- add dependency review for PRs where supported;
- add OpenSSF Scorecard or an equivalent supply-chain signal if it provides actionable value.

### P1-11: Document arbitrary catalog URL trust boundary

The CLI can accept an arbitrary STAC catalog URL. That is acceptable for a local CLI, but server/agent deployments must treat it as an outbound-network/SSRF boundary.

Document:

- trusted-input expectation for local use;
- outbound allowlist/policy requirement for hosted deployments;
- redirect and private-network considerations.

## Phase 8 — Developer experience and adoption

### P2-01: Fix installation funnel

Audit finding: README installation currently leads with editable developer installation rather than a normal user installation.

After packaging is published:

- lead with `pip install stac-scout`;
- move editable install to contributor documentation;
- provide a 60-second first-success example with expected output.

### P2-02: Add a reproducible end-to-end demonstration

Use a real task, for example wildfire impact:

`task -> derived requirements -> provider federation -> Item verification -> asset selection -> volume estimate -> manifest -> replay`

The same scenario should serve as:

- documentation;
- an integration/eval fixture where deterministic;
- a technical communication asset.

### P2-03: Improve repository discoverability without diluting positioning

Use accurate topics such as:

- `stac`
- `earth-observation`
- `satellite-imagery`
- `python`
- `pystac`
- `cloud-native-geospatial`
- `geospatial-data`

Keep the product name consistently "STAC Scout" and the positioning around dataset intelligence/evidence, not generic "Scout" or vague AI claims.

## Phase 9 — Production-readiness audit

Re-audit from the current default branch, not from assumptions.

Verify:

- public API contracts match implementation;
- all documented constraints are actually evaluated;
- hard constraints cannot be bypassed by ranking;
- geospatial edge cases pass;
- provider failures remain isolated without swallowing programming errors;
- manifests can distinguish complete from truncated evidence;
- replay does not create false drift;
- package version, tag, wheel, sdist, and release agree;
- documented install commands work from a clean environment;
- GitHub merge protections are active;
- vulnerability reporting works;
- release provenance is inspectable;
- live-provider checks are clearly separated from deterministic CI.

Only then decide whether to publish v0.5.0 or continue hardening in a follow-up release.

## Definition of done for every hardening PR

A PR is not complete merely because tests pass. It must satisfy all applicable items:

- behavior has an explicit contract;
- unknown information remains UNKNOWN rather than guessed;
- tests cover success, failure, and ambiguity paths;
- regression cases are added for the bug/risk being fixed;
- public behavior changes are documented;
- breaking changes include migration guidance;
- provider-specific behavior stays behind an adapter or registry rule;
- no hard constraint is silently ignored;
- provenance changes preserve replay interpretability;
- local quality gates and deterministic evals pass;
- security/network implications are considered for new external I/O.

## Scope discipline

During v0.5.0 hardening, correctness work outranks feature count, star growth, provider count, and benchmark-style marketing.

The project should earn stronger claims through inspectable tests, evidence, and release provenance.
