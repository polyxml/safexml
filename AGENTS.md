# AGENTS.md

Instructions and guidelines for AI coding assistants working in the `safexml` repository.

---

## 1. Project Overview

`safexml` is a high-performance, secure, modern XML parser and drop-in `defusedxml` replacement built in Rust.

- **Technology**: Rust 2021, PyO3 (`abi3-py312`), `quick-xml` (0.42+), `maturin`.
- **Repository**: `polyxml/safexml`
- **Supported Python**: `Python >= 3.12` exclusively. No legacy Python 2 or Python 3.7–3.11 backward-compatibility shims.
- **Maintainer**: Bailey Nguyen (`bailey.tan.nguyen@gmail.com`).
- **Organization**: [PolyXML](https://github.com/polyxml).

---

## 2. Core Architectural Decisions & Invariants

When contributing or refactoring, strictly maintain the following invariants:

1. **Python >= 3.12 Exclusively**:
   - Never introduce Python 2 or legacy Python 3 (< 3.12) compatibility shims (e.g. `sys.version_info < (3, ...)` or `six`).
   - Use modern syntax (`X | Y` type unions, PEP 561 typing, built-in generics).

2. **Drop-in Compatibility with `defusedxml.ElementTree` & `xml.etree.ElementTree`**:
   - Returns standard `xml.etree.ElementTree.Element` instances to maintain 100% compatibility with libraries like `pysaml2`, `python3-saml`, `openpyxl`, `python-docx`, `feedparser`, `botocore`.
   - Re-exports standard ElementTree symbols (`Element`, `SubElement`, `Comment`, `PI`, `indent`, `register_namespace`, `dump`, `tostring`, `tostringlist`).
   - Signature parity: `fromstring(text, parser=None, forbid_dtd=False, forbid_entities=True, forbid_external=True, ...)` must accept `parser` keyword argument (resolving `tiran/defusedxml#78`).

3. **True GIL Detachment in Rust**:
   - All tokenization, XML scanning, DTD validation, and entity checking in Rust must execute outside the Python GIL using `py.detach(|| ...)` to allow multi-threaded Python servers (FastAPI, Django, Celery, gunicorn) to parse XML concurrently without blocking.

4. **Security by Default**:
   - **Billion Laughs / Entity Expansion**: Reject non-predefined entities when `forbid_entities=True` (`EntitiesForbidden`).
   - **XXE (XML External Entity)**: Reject `SYSTEM` and `PUBLIC` references when `forbid_external=True` (`ExternalReferenceForbidden`).
   - **DTD Injections**: Reject `<!DOCTYPE>` declarations when `forbid_dtd=True` (`DTDForbidden`).
   - **Nesting Depth Limit**: Enforce `max_depth` (default 1,000) to protect against stack exhaustion.
   - **Size Limits**: Enforce `max_text_size` and `max_entity_size` to prevent memory exhaustion attacks.

5. **Upstream Issue Fixes**:
   - Maintain the fixes for tracked upstream issues:
     - `tiran/defusedxml#105`: Exception formatting for `rich` tracebacks.
     - `tiran/defusedxml#104`: PEP 561 `py.typed` marker and full type annotations.
     - `tiran/defusedxml#87`: Standard `ElementTree.indent()` support.
     - `tiran/defusedxml#80`: Direct `Element` class export.
     - `tiran/defusedxml#79`: `register_namespace()` support.
     - `tiran/defusedxml#76`, `#77`, `#88`: Safe `defuse_stdlib()` without breaking 3rd-party libs.

---

## 3. Tooling & Development Workflow

### Rust Toolchain
- Check workspace:
  ```bash
  cargo check
  ```
- Run Rust tests:
  ```bash
  cargo test
  ```
- Format code:
  ```bash
  cargo fmt --all
  ```
- Clippy:
  ```bash
  cargo clippy -- -D warnings
  ```

### Python Development
- Compile extension into local virtualenv:
  ```bash
  maturin develop
  ```
- Run test suite:
  ```bash
  pytest -v
  ```
- Lint & format with Ruff:
  ```bash
  ruff check python tests
  ruff format python tests
  ```
- Version parity check:
  ```bash
  python scripts/sync_version.py --check
  ```

---

## 4. Release Process
- Releases are automated via GitHub Actions (`.github/workflows/release.yml`) using Semantic Release (`.releaserc`) and PyPI Trusted Publishing.
- Manifest versions (`Cargo.toml` and `pyproject.toml`) are kept in sync via `scripts/sync_version.py`.
