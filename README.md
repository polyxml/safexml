<p align="center">
  <img src="https://raw.githubusercontent.com/polyxml/safexml/main/docs/assets/brand/logo_polyxml_banner.png" alt="PolyXML SafeXML" width="1000">
</p>

# SafeXML 🛡️

**The memory-safe, GIL-free, ultra-fast XML parser and drop-in `defusedxml` successor built in Rust.**

[![CI](https://github.com/polyxml/safexml/actions/workflows/ci.yml/badge.svg)](https://github.com/polyxml/safexml/actions/workflows/ci.yml)
[![PyPI version](https://img.shields.io/pypi/v/safexml.svg)](https://pypi.org/project/safexml/)
[![Python versions](https://img.shields.io/pypi/pyversions/safexml.svg)](https://pypi.org/project/safexml/)
[![Coverage: 100%](https://img.shields.io/badge/Coverage-100%25-brightgreen.svg)](https://github.com/polyxml/safexml/actions/workflows/ci.yml)
[![Rust: 100% Safe](https://img.shields.io/badge/Rust-100%25%20Safe-orange.svg)](#1-immune-to-c-memory-corruption-cve-hell)
[![GIL: Detached](https://img.shields.io/badge/GIL-Detached%20(True%20Concurrency)-blueviolet.svg)](#2-true-gil-release-for-modern-multi-threaded-services)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](https://opensource.org/licenses/MIT)

---

## ⚡ The Case for SafeXML: Why DefusedXML is Obsolete

For over a decade, Python developers relied on `defusedxml` to protect against XML bombs. But `defusedxml` is fundamentally a legacy wrapper around CPython's 1990s-era C `pyexpat` engine. In modern Python (>=3.12), `defusedxml` has become a security liability and performance bottleneck:

### 1. Immune to C Memory Corruption (CVE Hell)
`defusedxml` is just a Python-level monkeypatch on top of C `libexpat`. When `libexpat` suffers from integer overflows, heap buffer overflows, or use-after-free bugs, **`defusedxml` cannot protect you**. Between 2022 and 2026 alone, `libexpat` was hit by a barrage of critical CVEs:
- **CVE-2024-45490, CVE-2024-45491, CVE-2024-45492**: Integer overflows in XML parsing causing heap corruption.
- **CVE-2023-52425**: Denial of service through entity expansion parser state corruption.
- **CVE-2022-25235, CVE-2022-25236, CVE-2022-23852**: Malformed namespace and character encoding heap buffer crashes.

**SafeXML is written in 100% memory-safe Rust** using [`quick-xml`](https://github.com/tafia/quick-xml) and [`PyO3`](https://github.com/PyO3/pyo3). There is zero C code, zero raw memory pointers, zero heap corruption, and zero use-after-free risk.

### 2. True GIL Release for Modern Multi-Threaded Services
When parsing XML inside high-concurrency web frameworks (FastAPI, Django, Flask, Celery, gRPC), `defusedxml` **holds Python's Global Interpreter Lock (GIL)**. Ten worker threads parsing XML become serialized into a single-core crawl.

**SafeXML detaches the Python GIL during parsing (`py.detach(|| ...)`).** Rust processes, validates, and decodes the XML stream completely in parallel across all CPU cores, unlocking linear multi-core speedup.

### 3. Defeats Modern XML Attacks That `defusedxml` Misses
`defusedxml` only guards against traditional DTD and entity expansions. It completely misses modern XML attack vectors:
- **Input Size Bounding (CWE-400)**: Unbounded source streams exhaust host memory before parsing completes. **SafeXML enforces `max_input_size` (default 256MB) with bounded reading.**
- **Element Count Bounding (CWE-400)**: Millions of sibling elements bypass recursion depth limits. **SafeXML enforces `max_elements` (default 5,000,000).**
- **Attribute Flood / Attribute Hash DoS (CWE-400)**: Attackers submit elements with 100,000 attributes. `defusedxml` constructs a massive Python dictionary, causing quadratic memory overhead. **SafeXML enforces `max_attributes` (default 1,000).**
- **Giant Attribute Value Bombs (CWE-400)**: A single 50MB attribute value crashes memory. `defusedxml` does not inspect attribute lengths. **SafeXML enforces `max_attribute_size` (default 10MB).**
- **Comment Amplification Bombs**: Millions of comments or giant comment streams exhaust parser memory. **SafeXML enforces `max_comment_size` (default 10MB).**
- **Tag Name Memory Bombs**: Gigantic element tag names consume unbounded memory during string interning. **SafeXML enforces `max_name_size` (default 1,024 chars).**
- **Null Byte Injection**: Embedded null bytes (`\0`) in tag or attribute names cause C-string truncation attacks downstream in databases and auth services. **SafeXML strictly rejects null bytes.**

---

## 🥊 Comprehensive Attack Surface & Feature Matrix

| Security / Feature Matrix | `safexml` (Rust) | `defusedxml` (Python + C) | `lxml` (C `libxml2`) | `xml.etree` (Python stdlib) |
| :--- | :---: | :---: | :---: | :---: |
| **Billion Laughs / Exponential Entity Bomb** | 🛡️ **BLOCKED** | 🛡️ **BLOCKED** | ⚠️ Config-dependent | ❌ **VULNERABLE** |
| **Quadratic Blowup Entity Attack** | 🛡️ **BLOCKED** | 🛡️ **BLOCKED** | ⚠️ Config-dependent | ❌ **VULNERABLE** |
| **External Entity (XXE) / SSRF** | 🛡️ **BLOCKED** | 🛡️ **BLOCKED** | ⚠️ Config-dependent | ❌ **VULNERABLE** |
| **External DTD Retrieval** | 🛡️ **BLOCKED** | 🛡️ **BLOCKED** | ⚠️ Config-dependent | ❌ **VULNERABLE** |
| **Document Size Bounding** | 🛡️ **BLOCKED** (`max_input_size`) | ❌ Unbounded read | ⚠️ Config-dependent | ❌ Unbounded read |
| **Element Count Bounding** | 🛡️ **BLOCKED** (`max_elements`) | ❌ Unbounded | ❌ Unbounded | ❌ Unbounded |
| **Attribute Flood / Memory DoS (CWE-400)** | 🛡️ **BLOCKED** (`max_attributes`) | ❌ **VULNERABLE** | ❌ **VULNERABLE** | ❌ **VULNERABLE** |
| **Giant Attribute Value Bomb (CWE-400)** | 🛡️ **BLOCKED** (`max_attribute_size`) | ❌ **VULNERABLE** | ❌ **VULNERABLE** | ❌ **VULNERABLE** |
| **Tag Name Memory Bomb** | 🛡️ **BLOCKED** (`max_name_size`) | ❌ **VULNERABLE** | ❌ **VULNERABLE** | ❌ **VULNERABLE** |
| **Comment Amplification Bomb** | 🛡️ **BLOCKED** (`max_comment_size`) | ❌ **VULNERABLE** | ❌ **VULNERABLE** | ❌ **VULNERABLE** |
| **Null Byte Identifier Injection** | 🛡️ **BLOCKED** | ❌ Truncated / Allowed | ❌ Truncated / Allowed | ❌ Truncated / Allowed |
| **Immune to C-Level Memory Corruption** | 🛡️ **YES (Safe Rust)** | ❌ No (`libexpat` CVEs) | ❌ No (`libxml2` CVEs) | ❌ No (`libexpat` CVEs) |
| **Releases Python GIL (Parallel Scaling)** | ⚡ **YES (`py.detach`)** | ❌ No (Blocks GIL) | ⚠️ Partial | ❌ No (Blocks GIL) |
| **PEP 561 Type Annotations (`py.typed`)** | ✅ **YES** | ❌ No | ⚠️ Separate stub | ⚠️ Standard library |
| **Rich / Structured Logging Compatible** | ✅ **YES** | ❌ Missing args | ✅ Yes | ✅ Yes |
| **ElementTree `indent()` Built-in** | ✅ **YES** | ❌ Missing | ✅ Yes | ✅ Yes |
| **Modern Python Target** | 🐍 **Python >= 3.12** | 🏚️ Python 2 / Legacy | 🐍 All | 🐍 Standard library |

---

## 🚀 Benchmarks: SafeXML vs DefusedXML

Benchmarks run on Linux x86_64, Python 3.12.14, comparing `safexml` against `defusedxml` and stdlib `xml.etree`:

### 1. Single-Threaded Throughput & Latency

```
Small Workload (~1 KB XML document):
  SafeXML (Rust):    67.2 µs | 14,879 ops/sec  [1.63x FASTER (+62.9% throughput)] ⚡
  defusedxml:       109.5 µs |  9,133 ops/sec  [Baseline]

Large Workload (~500 KB, 5,000 items):
  SafeXML (Rust):    42.3 ms |    23.6 ops/sec  [1.23x FASTER (+23.3% throughput)] ⚡
  defusedxml:        52.2 ms |    19.2 ops/sec  [Baseline]
```

### 2. Multi-Threaded Concurrency (GIL-Release Benchmark)

Under `concurrent.futures.ThreadPoolExecutor` simulating concurrent API requests:

| Worker Threads | `defusedxml` Throughput | `SafeXML` Throughput | Real-World Concurrency Speedup |
| :--- | :--- | :--- | :--- |
| **2 Workers** | 547.6 docs/sec | **779.9 docs/sec** | **1.42x FASTER** 🚀 |
| **4 Workers** | 579.8 docs/sec | **828.8 docs/sec** | **1.43x FASTER** 🚀 |
| **8 Workers** | 624.1 docs/sec | **838.6 docs/sec** | **1.34x FASTER** 🚀 |

> *Under heavy multi-threaded workloads, `defusedxml` saturates the GIL and stalls. `safexml` frees Python threads to process requests in parallel.*

---

## ✨ Modern Standard Library Compatibility & Developer Ergonomics

`safexml` provides complete compatibility with Python's standard `xml.etree.ElementTree` while delivering modern developer ergonomics:

- **Structured Tracebacks**: All exceptions populate standard `args` and `message` properties, rendering cleanly in `rich`, IPython, and logging pipelines.
- **PEP 561 Typing**: Ships with inline `py.typed` markers and comprehensive type annotations for `mypy` and `pyright`.
- **ElementTree `indent()`**: Full support for XML pretty-printing and tree indentation matching Python 3.9+ standard library APIs.
- **Element Class Re-export**: `Element` is exported directly from `safexml.ElementTree` and top-level `safexml`.
- **Namespace Registration**: `register_namespace()` is supported for deterministic namespace prefix serialization.
- **Signature Parity**: `fromstring()` accepts standard library keyword arguments including `parser=`.
- **Non-Destructive Defusing**: `defuse_stdlib()` patches standard library parsers without breaking third-party libraries (e.g. `openpyxl`, `xmlschema`) or corrupting `Element` identity.

---

## 📦 Installation

Prebuilt `abi3` binary wheels are available on PyPI for Linux, macOS (Apple Silicon & Intel), and Windows:

```bash
pip install safexml
```

*Requirements: Python >= 3.12.*

---

## 💡 Quickstart: 10-Second Migration

### 1. Direct Drop-in Replacement for `defusedxml.ElementTree`

Simply update your import:

```python
# Before:
# import defusedxml.ElementTree as ET

# After:
import safexml.ElementTree as ET

# 100% identical API, backed by Rust:
root = ET.fromstring("<catalog><item id='1'>Safe XML</item></catalog>")
print(root.tag)               # "catalog"
print(root[0].text)           # "Safe XML"

# Built-in pretty-printing
ET.indent(root)
print(ET.tostring(root, encoding="unicode"))
```

### 2. Drop-in Replacement for `defusedxml.minidom` and `defusedxml.sax`

```python
# minidom drop-in
from safexml import minidom

doc = minidom.parseString("<catalog><item id='1'>Safe XML</item></catalog>")
print(doc.documentElement.tagName)  # "catalog"

# SAX drop-in
from safexml import sax
from xml.sax.handler import ContentHandler

class CustomHandler(ContentHandler):
    def startElement(self, name, attrs):
        print(f"Element: {name}")

sax.parseString("<root><item/></root>", CustomHandler())
```

### 3. Global Non-Destructive Stdlib Defusing

If you have third-party dependencies (like `openpyxl`, `boto3`, or `saml2`) using Python's standard `xml.etree.ElementTree`, `xml.dom.minidom`, or `xml.sax`, you can secure your entire application runtime with one call:

```python
import safexml

# Safely patches xml.etree.ElementTree, xml.dom.minidom, and xml.sax
safexml.defuse_stdlib()
```

### 4. Catching Security Violations

```python
import safexml.ElementTree as ET
from safexml.common import (
    DefusedXmlException,
    DTDForbidden,
    EntitiesForbidden,
    ExternalReferenceForbidden,
)

# 1. Billion Laughs / Exponential Entity Bomb
try:
    ET.fromstring("""<!DOCTYPE bomb [
        <!ENTITY a "1234567890">
        <!ENTITY b "&a;&a;&a;&a;&a;&a;&a;&a;">
    ]><bomb>&a;</bomb>""")
except EntitiesForbidden as exc:
    print(f"Blocked entity expansion: {exc.name}")

# 2. External DTD / XXE / SSRF
try:
    ET.fromstring("""<!DOCTYPE root SYSTEM "http://attacker.com/evil.dtd"><root/>""")
except ExternalReferenceForbidden as exc:
    print(f"Blocked external reference: {exc.sysid}")

# 3. Attribute Flood DoS (CWE-400)
try:
    # Restrict attributes to 5 per element (default: 1,000)
    ET.fromstring("<root a1='1' a2='2' a3='3' a4='4' a5='5' a6='6'/>", max_attributes=5)
except DefusedXmlException as exc:
    print(f"Blocked attribute flood: {exc}")

# 4. Giant Tag Name Bomb
try:
    ET.fromstring(f"<{'A' * 2000}/>", max_name_size=1024)
except DefusedXmlException as exc:
    print(f"Blocked oversized tag: {exc}")
```

---

## 🏗️ Architectural Distinction: `safexml` vs `polyxml`

Both projects are maintained by the **[PolyXML](https://github.com/polyxml)** organization:

| Feature | `safexml` | `polyxml` |
| :--- | :--- | :--- |
| **Primary Role** | **Untyped DOM / ElementTree** drop-in replacement | **Data-Binding & Serde Engine** (Schema-driven) |
| **Output Type** | `xml.etree.ElementTree.Element` | Typed Python objects (Dataclasses, Pydantic, Attrs) |
| **Primary Use** | Legacy migrations, SAML, SVG, Office files, arbitrary XML | High-throughput APIs, SOAP, microservices, typed pipelines |
| **Security Focus** | Comprehensive attack surface defense & resource bounding | Strict schema validation & zero-copy Rust deserialization |

---

## 📄 License

MIT License. Engineered with pride under the [PolyXML](https://github.com/polyxml) organization by [Bailey Nguyen](mailto:bailey.tan.nguyen@gmail.com).
