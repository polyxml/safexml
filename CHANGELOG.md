# Changelog

All notable changes to this project will be documented in this file.
See [standard-version](https://github.com/conventional-changelog/standard-version) for commit guidelines.

## [1.0.2] - 2026-10-11

### Features
- Added drop-in replacements for `safexml.minidom` and `safexml.sax` with complete security enforcement.
- Enhanced `defuse_stdlib()` to seamlessly protect `xml.etree.ElementTree`, `xml.dom.minidom`, and `xml.sax`.
- Added strict resource defenses: `max_input_size` (256MB default) and `max_elements` (5,000,000 default).
- Implemented continuous fuzzing test target with `libfuzzer-sys` under `fuzz/`.
- Added property-based differential testing suite using Hypothesis verifying DOM equivalence against `xml.etree.ElementTree`.
- Modularized Rust crate structure with `python` optional feature for standalone Rust usage.

## [1.0.0] - 2026-10-11

### Features
- Initial release of `safexml`: High-performance, secure, modern XML parser and drop-in `defusedxml` replacement built in Rust.
- Core Rust streaming XML parser powered by `quick-xml` and `PyO3` with true GIL release (`py.detach`).
- Full drop-in parity for `defusedxml.ElementTree` and `xml.etree.ElementTree`.
- Strict security against Billion Laughs (exponential entity expansion), Quadratic Blowup, XXE, cyclic entities, and external DTDs.
- Enforced depth recursion limits (default 1,000) and text/entity memory bounds.
- Modern developer ergonomics and standard library compatibility:
  - Rich traceback exception formatting.
  - PEP 561 `py.typed` marker and full typing annotations.
  - Standard `ElementTree.indent()` support.
  - Direct `Element` class export.
  - `register_namespace()` helper.
  - `fromstring(..., parser=None)` keyword signature parity.
  - Safe non-destructive `defuse_stdlib()`.
