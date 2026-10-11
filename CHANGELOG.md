# Changelog

All notable changes to this project will be documented in this file.
See [standard-version](https://github.com/conventional-changelog/standard-version) for commit guidelines.

## [0.1.0] - 2026-10-11

### Features
- Initial release of `safexml`: High-performance, secure, modern XML parser and drop-in `defusedxml` replacement built in Rust.
- Core Rust streaming XML parser powered by `quick-xml` and `PyO3` with true GIL release (`py.detach`).
- Full drop-in parity for `defusedxml.ElementTree` and `xml.etree.ElementTree`.
- Strict security against Billion Laughs (exponential entity expansion), Quadratic Blowup, XXE, cyclic entities, and external DTDs.
- Enforced depth recursion limits (default 1,000) and text/entity memory bounds.
- Resolved upstream `defusedxml` open issues:
  - tiran/defusedxml#105: Rich traceback exception formatting.
  - tiran/defusedxml#104: PEP 561 `py.typed` marker and full typing annotations.
  - tiran/defusedxml#87: Standard `ElementTree.indent()` support.
  - tiran/defusedxml#80: `Element` class export.
  - tiran/defusedxml#79: `register_namespace()` helper.
  - tiran/defusedxml#78: `fromstring(..., parser=None)` keyword signature parity.
  - tiran/defusedxml#76, #77, #88: Safe non-destructive `defuse_stdlib()`.
