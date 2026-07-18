# Security and Responsible Disclosure

TrialCompiler is an early-stage, review-only research prototype. It is not
approved for production clinical use and must not be used to make autonomous
medical, statistical, regulatory, or participant-level decisions.

## Do not submit sensitive material

Do not place the following in commits, issues, pull requests, benchmark cases,
or demonstration payloads:

- API keys, passwords, tokens, or private service endpoints;
- protected health information or identifiable patient records;
- confidential sponsor, investigator, vendor, or enterprise documents;
- unlicensed third-party material; or
- production credentials and database snapshots.

Use synthetic or explicitly public data for reproducible examples. Store local
secrets in environment variables or ignored `.env.*` files.

## Reporting a vulnerability

Do not disclose an exploitable vulnerability or exposed secret in a public
issue. Contact the repository maintainers privately through the security
reporting channel available on the GitHub repository. Include the affected
version, reproduction steps, expected impact, and any suggested mitigation.

## Security boundaries

The public MVP assumes a trusted local execution environment. Deployers are
responsible for authentication, authorization, transport security, secret
management, tenant isolation, retention controls, monitoring, and validation
appropriate to their jurisdiction and intended use.
