# Security Policy

## Supported Versions

| Version | Supported          |
| ------- | ------------------ |
| >= 1.0.0 | :white_check_mark: |

## Reporting a Vulnerability

The `safexml` project takes the security of XML parsing and defense seriously.

If you believe you have found a security vulnerability (such as a bypass to XXE defense, quadratic blowup protection, or entity restriction), please do **NOT** open a public issue.

Instead, please report security issues privately:
- Contact maintainer Bailey Nguyen via email: `bailey.tan.nguyen@gmail.com`
- Or via GitHub Private Vulnerability Reporting on the [safexml repository](https://github.com/polyxml/safexml/security/advisories/new).

Please include:
1. Proof of concept (PoC) XML payload.
2. The version of `safexml`, Python, and operating system.
3. Observed vs expected behavior.

You will receive an acknowledgment within 48 hours and regular updates on the mitigation and release patch.

## OSV Schema Compliance & Advisory Publishing

Security advisories for `safexml` are published via [GitHub Security Advisories (GHSA)](https://github.com/polyxml/safexml/security/advisories), which publishes entries conforming to the **[Open Source Vulnerability (OSV) Schema](https://ossf.github.io/osv-schema/)**:

- **Ecosystem:** Advisories are published under the `PyPI` ecosystem for package `safexml`.
- **Machine-Readable Metadata:** Advisories provide structured package identification, semantic version ranges (`introduced`, `fixed`), and references.
- **Vulnerability Databases:** Advisories flow automatically into:
  - [Google Open Source Vulnerability Database (OSV.dev)](https://osv.dev/list?ecosystem=PyPI&q=safexml)
  - Downstream vulnerability scanners including `pip-audit`, `osv-scanner`, `trivy`, and `dependabot`.
- **CWE Classifications:** Advisories map to appropriate Common Weakness Enumeration identifiers:
  - **CWE-611:** Improper Restriction of XML External Entity Reference (XXE)
  - **CWE-776:** Improper Restriction of Recursive Entity References in DTDs (XML Entity Expansion)
  - **CWE-400:** Uncontrolled Resource Consumption
  - **CWE-827:** Improper Control of Document Type Definition

