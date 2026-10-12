# SafeXML security and replacement-readiness audit

Date: 2026-10-11. Source: commit `46689bf2bf14b1a898be870112bcda8ad44d4729`, package 1.0.2.

## Verdict

**Do not position this release as a secure drop-in successor to defusedxml.** It has useful defenses and a promising Rust core, but confirmed denial-of-service, resource amplification, parser disagreement, and unprotected API paths prevent that claim. In particular, it should not be substituted into authentication or signature processing without fixing parser correctness and independently validating the integration.

This is a source review with executable adversarial probes, not a security certification or a proof of absence of vulnerabilities. Severity is qualitative: “high” means a release blocker for a library advertised for untrusted XML; actual application exploitability depends on how its APIs are used. No CVE assignment or application authentication bypass is claimed.

## Scope and evidence

Reviewed all four Rust source files, all five Python modules, existing tests, the fuzz target, manifests, README, security policy, benchmark harness, and CI/release workflows. Built the local source in an isolated Python environment. Runtime: Linux x86_64 under WSL2, Python 3.12.15, Expat 2.8.5, quick-xml 0.42.0, PyO3 0.29.3. Comparison package: defusedxml 0.7.1.

Artifacts:

- `probe.py`: reproducible differential and API probes. It reports observations rather than asserting that defects are acceptable.
- `probe-results.json`: captured results, including isolated subprocess panic checks.
- `benchmark-results.txt`: one run of the repository benchmark; not a statistically controlled performance study.

Run `python audit/probe.py` using an environment with the locally built package and defusedxml installed. Panic probes run in subprocesses. The bounded namespace probe intentionally allocates tens of MB; do not run it inside a memory-constrained production service.

## Confirmed security findings

### A1 — High: namespace reuse amplifies memory outside configured limits

Locations: `src/parser.rs:256`, `src/parser.rs:370`, `src/parser.rs:403`.

Namespace declaration values skip `max_attribute_size` and declaration counts skip `max_attributes`. Namespace resolution then materializes the full URI into every element and resolved attribute name. `max_name_size` constrains lexical names, not expanded names; there is no total expanded-name or tree-allocation budget.

Reproduction:

```python
xml = '<r xmlns="' + "x" * 16384 + '">' + "<c/>" * 2000 + "</r>"
r = safexml.fromstring(xml, max_attributes=0, max_attribute_size=1)
sum(len(e.tag) for e in r.iter())
```

24,400 input bytes produce **32,790,387 bytes of expanded tag content**. This succeeds with the default `max_name_size=1024`. It measures content lengths, not peak RSS; the Rust and Python trees and intermediary objects impose additional costs. Input and element limits still cap their own quantities, but their large defaults permit much larger amplification. No need to expand a custom entity or fetch external data.

Fix: bound namespace declarations before resolver allocation, bound expanded names, and enforce a cumulative decoded/output allocation budget before formatting. Consider interning namespace URIs and expanded names. Add a memory-constrained subprocess regression.

### A2 — High: attacker-controlled DTD content triggers Rust panic, including valid XML

Locations: `src/doctype.rs:74`, `src/doctype.rs:146`, `src/parser.rs:191`.

The DTD scanner increments byte indices and slices a UTF-8 string at those indices. Non-ASCII text can put the index inside a code point. Reproduced with:

```xml
<!DOCTYPE r é><r/>
<!DOCTYPE r [<!ENTITY e é>]><r/>
<!DOCTYPE r [<!-- <!ENTITY fake é> -->]><r/>
```

The first two are malformed input that must be rejected normally. The third is valid XML: the apparent declaration is inside a comment. defusedxml accepts it. SafeXML panics at `src/doctype.rs:146`, reporting a `pyo3_runtime.PanicException`. This exception derives from `BaseException`, so typical `except Exception` handlers do not catch it. The result is an uncontrolled exception, not demonstrated whole-process termination. A Rust consumer configured to abort on panic would have different consequences.

`forbid_dtd=True` also panics for the first two examples because DTD scanning happens before the policy rejection. Merely selecting a stricter flag does not prevent this.

Fix: parse bytes safely or advance by character boundaries, validate DTD grammar, recognize comments and quoted literals, and reject forbidden DTDs before expensive or fragile full-subset processing. The current fuzz target exercises this scanner even with `forbid_dtd=True`, but CI only checks that the target compiles; it does not run a fuzz campaign.

### A3 — High: multiple roots and incomplete trailing elements are accepted

Locations: `src/parser.rs:277`, `src/parser.rs:319`, `src/parser.rs:361`, `src/parser.rs:367`.

`<signed/><unsigned/>` returns the `unsigned` element, silently replacing the first root. `<signed/><unsigned>` returns `signed`, ignoring an unfinished trailing element. defusedxml and stdlib reject both. A DOCTYPE after the document element is also accepted.

The parser lacks a document state machine and does not require an empty element stack at EOF. Parser disagreement can compromise systems that validate with one parser and consume with another; an actual signature or authorization exploit has not been established.

Fix: enforce one root, legal prolog/epilog events, declaration placement and uniqueness, and complete closure at EOF.

### A4 — High: duplicate attributes after namespace expansion overwrite data

Locations: `src/parser.rs:412`, `src/parser.rs:467`, `src/python.rs:47`.

```xml
<r xmlns:a="urn:x" xmlns:b="urn:x" a:id="signed" b:id="unsigned"/>
```

SafeXML returns `{"{urn:x}id": "unsigned"}`. defusedxml and stdlib reject the duplicate expanded attribute. Lexical duplicate checking alone does not establish namespace-aware uniqueness. Python dictionary insertion silently selects the latter value.

Fix: reject duplicate expanded attribute names during Rust parsing, before tree conversion.

### A5 — High: exported XMLParser bypasses SafeXML defenses

Location: `python/safexml/ElementTree.py:13` import block.

`safexml.ElementTree.XMLParser` is exactly `xml.etree.ElementTree.XMLParser`. Its `feed()`/`close()` path expands internal entities and applies none of SafeXML's resource limits. This is a major migration hazard because defusedxml exports its protected parser class under `XMLParser`.

Reproduction: feed `<!DOCTYPE r [<!ENTITY e "expanded">]><r>&e;</r>` to `safe.XMLParser()`, then close it; `.text` is `expanded`. This demonstrates a policy bypass, not bypass of Expat's own modern amplification protection.

Fix: provide a protected compatible parser, or explicitly remove/reject this API and narrow replacement claims.

### A6 — High: defuse_stdlib leaves entry points using the original parser

Location: `python/safexml/__init__.py:56`.

After calling `safexml.defuse_stdlib()`, both `xml.etree.ElementTree.ElementTree().parse(stream)` and `xml.etree.ElementTree.fromstringlist([xml])` still expand the simple internal entity above. `XMLParser` and `XMLPullParser` remain available as original parser paths. The patch does not secure the “entire application runtime.” Already imported aliases and other XML modules also cannot be assumed protected.

Fix: define the exact patch contract, protect all intended public parser entry points, and test them in fresh subprocesses. Do not advertise comprehensive protection until that contract is satisfied. Do not silently route unsupported custom parsers through unsafe fallback paths.

### A7 — Medium: invalid XML names, characters, comments, and namespaces accepted

Locations: `src/parser.rs:236`, `src/parser.rs:325`, `src/parser.rs:370`, `src/parser.rs:426`, `src/parser.rs:472`.

Confirmed acceptance of `<1root/>`, unbound `<p:root/>`, raw NUL text, `&#0;`, uppercase `&#X41;`, literal `<` inside an attribute, and a comment containing forbidden `--`. Namespace values are neither correctly unescaped nor checked for undefined entities: `<r xmlns="urn:&evil;"/>` is accepted and becomes `{urn:&evil;}r`. `<r xmlns="urn:a&amp;b"/>` produces the wrong expanded name.

The numeric-reference code validates Unicode scalar values, which is weaker than XML 1.0 character validity. These disagreements are particularly concerning across parser boundaries. NUL acceptance in text also contradicts the README's implication of comprehensive null-injection protection. No downstream database exploit is claimed.

Fix: implement XML and namespace well-formedness checks; use XML-specific whitespace, character-reference syntax, and character ranges. Test malformed inputs against a conforming reference parser.

### A8 — Medium: stream parsing reads once and can accept an incomplete input stream

Location: `src/python.rs:108`.

The binding issues one `read(max_input_size+1)` call and treats the result as the entire document. A file-like object can legally return fewer bytes than requested before EOF. A stream returning `<r/>` on its first read and additional bytes later is accepted after one call; remaining content is never validated. Regular files and BytesIO do not expose this defect in existing tests.

Fix: loop over bounded reads until EOF, distinguish short reads from EOF, stop at the cumulative input budget, and avoid unbounded copying. Text streams are sized in characters, then copied to UTF-8 before the byte limit is enforced; the current read request is not a strict byte allocation bound for them.

### A9 — Medium: recursive consumers exceed the advertised depth; high overrides can crash

Locations: `src/python.rs:40`, `python/safexml/ElementTree.py:245`, `python/safexml/sax.py:24`, `python/safexml/minidom.py:66`.

With 1,000 nested elements, core `fromstring` succeeds, but `iterparse`, SAX traversal, and minidom serialization each raise `RecursionError` under Python's normal recursion limit. This is controlled exception failure, not a demonstrated process crash at default settings.

A separate subprocess with 30,000 nested elements and `max_depth=30000` exited with signal 11 on this host. It had a five-second timeout, core dumps disabled, and a 512 MiB address-space cap. At 10,000 nesting the same probe succeeded. The exact crashing boundary is platform-dependent; raising the depth limit exposes recursive native tree conversion/destruction. This override is application-controlled, so the crash finding is conditional.

Fix: iterative conversion, traversal, serialization and teardown where possible; otherwise enforce a conservative validated maximum and document platform limits. No claim that safe Rust alone eliminates stack or allocation failures is justified.

### A10 — Medium: resource controls do not establish a total memory budget

Locations: `src/parser.rs:21`, `src/parser.rs:191`, `src/python.rs:123`.

`max_entity_size` is passed through but never read by the parser. An unused 100-byte entity declaration is accepted with `forbid_entities=False, max_entity_size=1`. Custom entity expansion is not implemented even when enabled, so this is an unenforced advertised declaration bound, not an entity-expansion exploit.

DTD declarations and values are collected before entity/DTD policy rejection. Limits for text, comments and attributes are checked after a complete token has been read; they are not pre-allocation bounds. The complete Rust tree exists alongside Python tree construction. Processing instructions have no dedicated limit. Five million permitted elements can consume substantial memory independently of text length. These are architectural observations; apart from A1, this audit did not measure peak memory exhaustion.

Fix: specify what each limit counts and when it is enforced, remove ineffective options, reject early, enforce a combined allocation budget, and benchmark peak RSS under adversarial workloads and concurrency.

## Compatibility and product-readiness findings

### A11 — High replacement blocker: iterparse is not incremental

`python/safexml/ElementTree.py:223` parses a complete document and recursively walks it. Clearing elements cannot prevent the initial full-tree allocation. Namespace events are silently absent; unknown events are not rejected; the iterator has no `.root`. Comments and PI events are absent. Start events see a completed tree. These failures invalidate streaming migration assumptions and increase memory requirements.

### A12 — High replacement blocker: DOM/SAX behavior and public APIs differ

- `parser=` is accepted and ignored. A custom TreeBuilder configured to retain comments silently loses them.
- minidom reparses serialized ElementTree output using the original C/Expat minidom parser. It loses comments, PIs, CDATA node identity, DTD information, and original namespace prefixes. A tested `<p:r>` document became `<ns0:r>` and its other node types disappeared.
- SAX builds a DOM before callbacks, uses Clark names in `startElement`, has no namespace event semantics, omits processing instructions and locators, and does not route parse failures through the configured ErrorHandler. Several inherited XMLReader operations are unsupported.
- `ParseError` is a new security-exception subclass, not the stdlib `ParseError` exported by defusedxml; existing catches fail. Position/code information is absent.
- `fromstringlist`, `DefusedXMLParser`, `XMLTreeBuilder`, and other defusedxml-module coverage are missing. Python below 3.12 is deliberately unsupported; any successor claim must state this scope.
- CR/CRLF text normalization differs; attribute CRLF becomes two spaces instead of one. Valid ISO-8859-1 and UTF-16 documents are rejected despite enabling quick-xml's encoding feature. The parser does not wrap input in the required DecodingReader.
- Internal DTD default attributes are ignored although defusedxml accepts and applies them by default. With `forbid_entities=False`, custom entities remain unsupported.

Third-party compatibility with pysaml2, python3-saml, openpyxl, python-docx, feedparser and botocore was not demonstrated by this repository's suite or this audit. Standard Element instance identity is necessary but insufficient.

## Claims, performance and release engineering

### A13 — Materially misleading documentation

The README's absolute memory-corruption immunity and “zero C code” claims are false for the delivered API surface: Python Elements use CPython's native implementation, PyO3 crosses the Python C API, and minidom calls Expat. There are no explicit unsafe blocks in the project's four Rust files; that supports a much narrower claim.

Its stdlib XXE/DTD and null-byte comparison entries contradict Python's documented behavior. Modern Expat has billion-laughs/quadratic-expansion protection; version-dependent risk should be stated. CVE-2023-52425 concerns quadratic reparsing of large tokens, not the entity-expansion state-corruption description in the README. Avoid treating a dependency's historical CVEs as evidence of current vulnerability in every consumer.

References: [Python 3.12 XML security documentation](https://docs.python.org/3.12/library/xml.html), [defusedxml ElementTree source](https://github.com/tiran/defusedxml/blob/main/defusedxml/ElementTree.py), [quick-xml Reader documentation](https://docs.rs/quick-xml/0.42.0/quick_xml/reader/struct.Reader.html).

Rust tokenization detaches the GIL, but reading streams, building Python Elements, and dropping the Rust tree after conversion occur with Python attached. The full API is not “GIL-free.” The benchmark here found genuine advantages over defusedxml on its selected workload: 1.73x small, 1.20x medium, 1.59x large. Two/four/eight-worker SafeXML throughput was 1459.9/1449.2/1301.7 docs/sec, offering no evidence of linear multi-core scaling. The actual input sizes for 10/500/5000 items are 3,019/151,539/1,539,549 bytes; labels claiming approximately 1/50/500 KB are inaccurate. The threaded benchmark retains results in all futures, never calls `future.result()` to surface failures, has no one-worker baseline, and lacks repeated-run uncertainty. Rework the harness before making general speedup claims.

### A14 — Assurance and release gaps

- All 56 existing Python tests passed with 100% reported coverage. Coverage includes only 193 Python wrapper statements and excludes the native extension. It does not measure Rust correctness, XML conformance or attack coverage.
- All 20 default Rust tests passed, as did no-default-feature Clippy and formatting. Standard CI does not exercise the `python` feature's Rust binding tests. The audit additionally attempted them; see validation notes below.
- The Hypothesis strategy generates only shallow valid documents with a narrow grammar and 50 examples. It cannot establish rejection parity or full encoding/namespace/DTD coverage.
- A fuzz target and two seeds exist. CI performs `cargo check` on it, with no actual fuzz run, corpus mutation results, coverage report or sanitizer campaign supplied.
- Tests leak global monkeypatches: one only restores `fromstring`; another leaves `XML`/`iterparse` patched. This can contaminate differential reference behavior.
- Release builds are separate from CI and publication does not depend on validation jobs. Tag and release triggers can independently publish, `skip-existing` can hide duplicate attempts, and release version rewriting is not checked against the package embedded in an already published artifact. These are control gaps, not demonstrated supply-chain compromise.
- Third-party actions use mutable version refs, not immutable commit pins. Release permissions are broadly `contents: write` and `id-token: write`. Trusted publishing and a PyPI environment are good foundations; environment reviewer requirements cannot be inferred from the workflow file.
- No dependency advisory scan, SBOM, provenance verification, published-wheel inspection, or reproducible-build validation was completed. Absence of known dependency vulnerabilities was not established.

## What is working

Ordinary UTF-8 parsing returns real stdlib Elements with correct basic text/tail and common namespace behavior. The existing tests confirm ordinary entity declarations and external SYSTEM/PUBLIC references are rejected in the tested cases, plus depth, input, element, ordinary attribute, comment and accumulated text thresholds. The Rust core does not implement external retrieval or custom entity expansion. This substantially reduces the classic XXE/entity-expansion surface; this audit found no successful external fetch or custom-entity bomb through `fromstring`.

The project has a private reporting policy, CI across Python/OS versions, fuzz scaffolding and trusted publishing. These are useful foundations, but they do not outweigh the reproduced blockers.

## Required path to a credible successor

1. Fix A1–A7 first: allocation budgeting, panic-free DTD scanning, XML document validity, namespace uniqueness, and protected parser/patch contracts. Add regressions that must reject the confirmed payloads.
2. Decide and document supported XML grammar and APIs. Implement real streaming and parser behavior or explicitly narrow the product to bounded UTF-8 ElementTree construction. Stop describing unsupported DOM/SAX and defusedxml interfaces as drop-in.
3. Fix stream reads, encoding and normalization; eliminate recursion hazards or establish enforceable limits. Specify all resource budgets and measure peak memory.
4. Add malformed-input differential tests, XML conformance corpus coverage, all public parser entry-point checks, real fuzz campaigns on default and permissive DTD options, and cross-platform memory/stack tests. Test target third-party packages instead of inferring compatibility from class identity.
5. Replace absolute README claims with verified scope and measured results. Harden release gating and audit the actual distributable wheels and dependencies.
6. Obtain independent review after the parser and API changes, with special attention to signature/authentication integrations. No single audit can certify complete safety.

## Validation limitations

This review tested the local source on one host and Python 3.12, not all distributed wheels or operating systems. It did not run a sustained fuzz campaign, a full W3C XML suite, current advisory database scans, remote repository/settings checks, or application-level SAML/signature exploit attempts. The benchmark is one local run. The high-depth signal-11 reproduction is conditional on raising `max_depth` and is not evidence of a default-setting process crash. Runtime DTD panic and namespace amplification findings were independently reproduced from tiny/bounded inputs.
