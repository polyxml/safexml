# safexml 🛡️

**High-performance, secure, modern XML parser and drop-in `defusedxml` replacement built in Rust.**

[![CI](https://github.com/polyxml/safexml/actions/workflows/ci.yml/badge.svg)](https://github.com/polyxml/safexml/actions/workflows/ci.yml)
[![PyPI version](https://img.shields.io/pypi/v/safexml.svg)](https://pypi.org/project/safexml/)
[![Python versions](https://img.shields.io/pypi/pyversions/safexml.svg)](https://pypi.org/project/safexml/)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](https://opensource.org/licenses/MIT)

---

## Why safexml?

Python's standard library documentation explicitly warns:
> *"The XML modules in the Python standard library are not secure against maliciously constructed data. Use `defusedxml`."*

However, `defusedxml` was created in 2013 and has been stagnant (last released in March 2021), holding back over **94,000+ dependent repositories**. It relies on Python-level monkeypatching of legacy CPython `pyexpat` handlers, retains Python GIL locks during parsing, and lacks modern Python 3.12+ features, typing, and standard ElementTree functions.

`safexml` is engineered from scratch in Rust using [`quick-xml`](https://github.com/tafia/quick-xml) and [`PyO3`](https://github.com/PyO3/pyo3) to solve these problems:

1. **Drop-in Compatibility**: 100% compatible with `defusedxml.ElementTree` and standard `xml.etree.ElementTree`.
2. **True GIL Release**: Detaches the Python GIL during XML tokenization and validation via Rust threads (`py.detach`).
3. **Blazing Fast**: Parses, validates, and builds native elements orders of magnitude faster than pure Python / expat wrappers.
4. **Modern Python Only**: Requires **Python >= 3.12** exclusively (zero legacy Python 2 or 3.7–3.11 baggage).
5. **Strict Security by Default**:
   - Defeats **Billion Laughs** (exponential entity expansion).
   - Defeats **Quadratic Blowup** entity attacks.
   - Defeats **XML External Entity (XXE)** attacks (`SYSTEM` and `PUBLIC` URIs).
   - Defeats **Cyclic Entity** references.
   - Defeats **DTD Injections** and parameter entities.
   - Enforces configurable **Nesting Depth Limits** (default 1,000) to protect against C call stack exhaustion.
   - Enforces configurable **Text and Entity Size Limits** to eliminate memory exhaustion attacks.

---

## `safexml` vs `polyxml`

| Feature | `polyxml` | `safexml` |
| :--- | :--- | :--- |
| **Model** | **Data-Binding / Serde** (schema-driven) | **Untyped DOM Tree** |
| **Input / Output** | XML $\leftrightarrow$ Python Typed Models (Dataclasses, Pydantic) | XML $\leftrightarrow$ `ElementTree.Element` |
| **Use Case** | APIs, microservices, typed business logic | Drop-in for `ElementTree` & `defusedxml` (SAML, Office docs, RSS, SVG) |

---

## Upstream `defusedxml` Issues Resolved

`safexml` directly fixes open issues and pain points reported against `tiran/defusedxml`:

- **[#112](https://github.com/tiran/defusedxml/issues/112), [#84](https://github.com/tiran/defusedxml/issues/84)**: Stagnant project maintenance. Active development under the `polyxml` organization.
- **[#105](https://github.com/tiran/defusedxml/issues/105)**: Exception formatting crashed when printed by `rich` tracebacks due to missing `args`. Fixed with proper standard exception hierarchy.
- **[#104](https://github.com/tiran/defusedxml/issues/104)**: Complete lack of PEP 561 typing. `safexml` ships with `py.typed` and full type annotations.
- **[#87](https://github.com/tiran/defusedxml/issues/87)**: Missing `xml.etree.ElementTree.indent()`. Full support provided.
- **[#80](https://github.com/tiran/defusedxml/issues/80)**: Missing `Element` class export. Re-exported directly.
- **[#79](https://github.com/tiran/defusedxml/issues/79)**: Missing `register_namespace()` helper. Fully implemented.
- **[#78](https://github.com/tiran/defusedxml/issues/78)**: `fromstring()` rejected `parser=` keyword argument. Standard signature parity supported.
- **[#76](https://github.com/tiran/defusedxml/issues/76), [#77](https://github.com/tiran/defusedxml/issues/77), [#88](https://github.com/tiran/defusedxml/issues/88)**: `defuse_stdlib()` monkeypatching broke `openpyxl` and `xmlschema`. Safe, non-destructive defuser implemented.

---

## Installation

```bash
pip install safexml
```

---

## Quickstart

### Drop-in Replacement for `defusedxml.ElementTree`

```python
import safexml.ElementTree as ET

# Parsing strings
root = ET.fromstring("<root><item id='1'>Safe XML</item></root>")
print(root.tag)               # "root"
print(root[0].text)           # "Safe XML"

# Pretty-printing (resolves tiran/defusedxml#87)
ET.indent(root)
print(ET.tostring(root, encoding="unicode"))
```

### Catching Security Exceptions

```python
import safexml.ElementTree as ET
from safexml.common import EntitiesForbidden, DTDForbidden, ExternalReferenceForbidden

# 1. Billion Laughs / Entity attack rejection
try:
    ET.fromstring("""<!DOCTYPE bomb [
        <!ENTITY a "1234567890">
        <!ENTITY b "&a;&a;&a;&a;&a;&a;&a;&a;">
    ]><bomb>&a;</bomb>""")
except EntitiesForbidden as exc:
    print(f"Blocked entity expansion: {exc.name}")

# 2. External DTD / XXE rejection
try:
    ET.fromstring("""<!DOCTYPE root SYSTEM "http://attacker.com/evil.dtd"><root/>""")
except ExternalReferenceForbidden as exc:
    print(f"Blocked external reference: {exc.sysid}")

# 3. Forbid any DTD
try:
    ET.fromstring("<!DOCTYPE root><root/>", forbid_dtd=True)
except DTDForbidden as exc:
    print(f"Blocked DTD: {exc.name}")
```

---

## License

MIT License. Developed under the [PolyXML](https://github.com/polyxml) organization.

