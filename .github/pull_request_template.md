## Description

Provide a clear and concise summary of what this pull request changes and why.

---

## Type of Change

- [ ] Bug fix (non-breaking change fixing an issue or security vulnerability)
- [ ] New feature (non-breaking change adding functionality)
- [ ] Breaking change (fix or feature causing existing functionality to break)
- [ ] Performance improvement
- [ ] Documentation update

---

## Verification Checklist

Before submitting, please ensure:

- [ ] `cargo fmt --all -- --check` passes with zero differences.
- [ ] `cargo clippy --all-targets -- -D warnings` produces 0 warnings.
- [ ] `cargo test --all-targets` passes all Rust unit tests.
- [ ] `ruff check python tests benchmarks` passes with zero errors.
- [ ] `ruff format --check python tests benchmarks` passes.
- [ ] `pytest -v` passes with 100% statement and branch coverage (`--cov-fail-under=100`).
- [ ] `python scripts/sync_version.py --check` confirms version parity.
- [ ] New or updated documentation is included if applicable.
