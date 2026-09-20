# Security Policy

## Supported versions

Security fixes are applied to the latest released version and the current default branch unless a release note states otherwise.

During the v0.5.0 hardening cycle, users should expect security-related changes to land on the hardening branch through reviewed pull requests before release.

## Reporting a vulnerability

Do **not** open a public issue containing vulnerability details, credentials, access tokens, signed URLs, private catalog endpoints, or exploit instructions.

Preferred reporting path:

1. Open the repository's **Security** tab.
2. Use GitHub private vulnerability reporting if the "Report a vulnerability" option is available.
3. Include the affected version/commit, impact, minimal reproduction, and suggested mitigation if known.

If private vulnerability reporting is not available, open a public issue titled `[security] private contact requested` with **no vulnerability details**. A maintainer can then establish a private channel.

## Scope

Security reports are especially relevant for:

- arbitrary STAC catalog URLs and outbound-network behavior;
- redirects and server-side request forgery (SSRF) risks in hosted/agent deployments;
- credential, token, SAS, or signed-URL leakage;
- dependency and build-chain compromise;
- unsafe deserialization or malformed remote metadata;
- path/file handling in manifests and generated recipes;
- GitHub Actions and release-publishing credentials.

Scientific disagreement or incorrect dataset-selection semantics should use the **Correctness report** issue form unless there is also a security impact.

## Disclosure expectations

Please give maintainers a reasonable opportunity to investigate and release a fix before publishing exploit details.

The project will avoid claiming a vulnerability is fixed until a regression test or other reproducible verification demonstrates the remediation.
