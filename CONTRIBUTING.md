# Contributing to SafeXML

Thank you for your interest in contributing to **SafeXML**! SafeXML is a high-performance, memory-safe, drop-in replacement for `defusedxml` and standard library `xml.etree.ElementTree`, engineered in Rust with PyO3.

---

## 1. Code of Conduct

All contributors, maintainers, and community members agree to abide by our [Code of Conduct](CODE_OF_CONDUCT.md).

---

## 2. Development Prerequisites

To build and contribute to SafeXML, ensure you have:

- **Rust**: Latest stable toolchain via `rustup` (including `rustfmt` and `clippy`).
- **Python**: Python >= 3.12 (SafeXML explicitly does not support older, end-of-life Python releases).
- **uv**: Fast Python package manager ([https://docs.astral.sh/uv/](https://docs.astral.sh/uv/)).
- **maturin**: PyO3 build backend (`uv pip install maturin`).

---

## 3. Local Development Setup

1. **Clone the repository**:
   ```bash
   git clone https://github.com/polyxml/safexml.git
   cd safexml
   ```

2. **Create and activate a virtual environment**:
   ```bash
   uv venv
   source .venv/bin/activate
   ```

3. **Install development dependencies and build the Rust extension**:
   ```bash
   uv pip install -e ".[dev]"
   maturin develop --release
   ```

4. **Enable Git Hooks (Recommended)**:
   SafeXML ships with standalone git hooks that run formatting, linting, and 100% test coverage checks locally before commit and push:
   ```bash
   git config core.hooksPath .githooks
   ```

---

## 4. Verification & Testing

SafeXML enforces strict code quality and **100.00% statement and branch test coverage** across all modules.

Before pushing or opening a Pull Request, verify that all checks pass:

### 1. Rust Code Formatting & Linting
```bash
cargo fmt --all -- --check
cargo clippy --all-targets -- -D warnings
```

### 2. Rust Unit Tests
```bash
cargo test --all-targets
```

### 3. Python Linting & Formatting (Ruff)
```bash
ruff check python tests benchmarks
ruff format --check python tests benchmarks
```

### 4. Python Test Suite & 100% Coverage Gate
```bash
pytest -v
```
*(Pytest is configured with `--cov=safexml --cov-report=term-missing --cov-fail-under=100`. Any missed statement or branch will cause the build to fail).*

### 5. Version Parity Check
```bash
python scripts/sync_version.py --check
```

---

## 5. Benchmarking

To run the local benchmark suite comparing SafeXML against `defusedxml` and stdlib `xml.etree`:
```bash
python benchmarks/run_benchmarks.py
```

---

## 6. Submitting a Pull Request

1. Fork the repository and create a feature branch (`git checkout -b feat/my-security-fix`).
2. Make your changes in Rust (`src/`) and/or Python (`python/safexml/`).
3. Add corresponding unit tests in `tests/`.
4. Ensure 100% coverage is maintained (`pytest`).
5. Commit using [Conventional Commits](https://www.conventionalcommits.org/) (e.g. `feat:`, `fix:`, `docs:`, `perf:`).
6. Open a Pull Request against `main`. All CI checks must pass before merging.
