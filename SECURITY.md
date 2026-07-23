# Security Policy

## Supported versions

| Version | Supported |
|---------|-----------|
| 0.1.x   | Yes (best-effort) |

## What AURORA is

AURORA is a **local-first, single-user research engine**. It is not multi-tenant SaaS.
Default deployments bind to localhost; treat any network exposure as your responsibility.

## Reporting a vulnerability

Please **do not** open a public issue for security-sensitive reports.

- Prefer a private GitHub security advisory on this repository, or
- Contact the repository owner via GitHub.

Include: affected version/commit, reproduction steps, impact assessment.

## Scope notes

- Core discovery path uses no external API keys by design.
- Offline adapters must not introduce hidden network I/O.
- Do not submit findings that require inventing live trading or broker access — that is out of project scope.
