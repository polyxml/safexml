## [1.1.1](https://github.com/polyxml/safexml/compare/v1.1.0...v1.1.1) (2026-10-12)


### Bug Fixes

* **ci:** align wheel publish workflow with PyPI trusted publisher config (release.yml) ([#18](https://github.com/polyxml/safexml/issues/18)) ([3ec4c53](https://github.com/polyxml/safexml/commit/3ec4c53db33fc385afa7027d8d835b16b6c9a61b))

# [1.1.0](https://github.com/polyxml/safexml/compare/v1.0.2...v1.1.0) (2026-10-12)


### Bug Fixes

* **ci:** make differential fuzz runner stdout ascii-safe for Windows console ([7a9e41f](https://github.com/polyxml/safexml/commit/7a9e41ffc0f079a0dc83af64e58127c568fdfe71))
* **ci:** make Rust extension import optional in common/init and build in rust-check job ([cf9553c](https://github.com/polyxml/safexml/commit/cf9553cc4528f61493dd3fe0837408c39de1eae8))
* **test:** bundle industrial XML instance payloads for cross-platform CI runner parity ([707808f](https://github.com/polyxml/safexml/commit/707808fb5a413c0f2df0b084579e35dc37328de8))


### Features

* **ci,docs:** add banner, CI for Python 3.14/3.15, OSV metadata, and decouple compatibility tests ([89f508d](https://github.com/polyxml/safexml/commit/89f508d94ad51bdd1a9bc804584b999d5911219b))
* **dropin:** add minidom and sax drop-in modules, XML 1.0 attribute normalization, hypothesis testing, and libFuzzer target ([46689bf](https://github.com/polyxml/safexml/commit/46689bf2bf14b1a898be870112bcda8ad44d4729))
* industrial schema validation and adversarial payload hardening ([#10](https://github.com/polyxml/safexml/issues/10)) ([#14](https://github.com/polyxml/safexml/issues/14)) ([7ef8f7a](https://github.com/polyxml/safexml/commit/7ef8f7a5760d7f73e9e972a79cf5114fc3607ddf))
* **security:** add max_input_size and max_elements defenses, modularize PyO3 feature, and clean issue references ([023a650](https://github.com/polyxml/safexml/commit/023a650724c07c71f7823f34464bec74eb6c6085))
* **security:** harden XML parser against audit findings A1-A12 and fix stdlib parity ([#7](https://github.com/polyxml/safexml/issues/7)) ([7d68839](https://github.com/polyxml/safexml/commit/7d68839a600d461884223d925f6a9a721eebdaec))
* **test:** add automated differential fuzzing against stdlib and defusedxml ([#8](https://github.com/polyxml/safexml/issues/8)) ([#12](https://github.com/polyxml/safexml/issues/12)) ([ed7c40a](https://github.com/polyxml/safexml/commit/ed7c40a1eda87498df87165b3efcfcbcea71fe20))
* W3C XML conformance manifest runner and parser compliance ([#9](https://github.com/polyxml/safexml/issues/9)) ([#13](https://github.com/polyxml/safexml/issues/13)) ([47cea2a](https://github.com/polyxml/safexml/commit/47cea2abb9a1c1087188a3d000f859293781dc50))

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
