# SafeXML Fuzzing & Verification Architecture

SafeXML employs a multi-tiered, research-backed fuzzing and property-testing infrastructure designed to guarantee **memory safety, algorithmic complexity resilience, rejection parity, and parser differential immunity**.

---

## 1. Multi-Target Rust Fuzzing Infrastructure (`cargo-fuzz` & `libFuzzer`)

SafeXML maintains four specialized `libFuzzer` harnesses compiled with **AddressSanitizer (ASan)**, **UndefinedBehaviorSanitizer (UBSan)**, and LLVM Value Profiling (`-use_value_profile=1`):

| Fuzz Target | Strategy | Oracles & Invariants Checked |
| :--- | :--- | :--- |
| **`fuzz_parser`** | Bit-level mutation with structured parameter extraction (`ParseOptions`) | **Post-Condition Limit Oracles**: Verifies that any accepted document strictly satisfies `actual_depth <= max_depth`, `element_count <= max_elements`, `attr_count <= max_attributes`, and `tag_length <= max_name_size`. Zero limit escapes or silent truncation. |
| **`fuzz_structured_xml`** | AST-based grammar fuzzing (*Zest / Nautilus* paradigm) with fault-injection mutators | **Deep-State Penetration**: Generates typed XML ASTs with complex DTDs, `<!ATTLIST>` defaults with `#FIXED`, scoped namespaces, entity refs, CDATA, comments, and PIs, then injects syntactic corruptions to stress deep parser recovery paths. |
| **`fuzz_metamorphic`** | Metamorphic testing across round-trip serialization and transcoding | **Metamorphic Oracles**: <br>1. *Canonical Round-Trip Idempotence*: `parse(serialize(parse(x))) == parse(x)`.<br>2. *Encoding Invariance*: Transcoding UTF-8 to UTF-16 with encoding declarations produces identical DOM structures.<br>3. *Monotonic Security*: Stricter security settings never accept what permissive settings rejected. |
| **`fuzz_doctype_scanner`** | Compositional micro-harness targeting slice/cursor arithmetic | **Zero-Panic Slice Scanners**: Directly fuzzes `doctype::parse_doctype`, `extract_quoted`, XML declaration validation, encoding detection, and attribute whitespace scanners against arbitrary string/byte slices. |

---

## 2. Hypothesis Differential & Stream Testing

In addition to native Rust fuzzers, SafeXML runs automated property-based differential campaigns against Python stdlib `xml.etree.ElementTree` and `defusedxml`:

- **DOM Equivalence Oracle**: Verifies 1:1 tag, attribute, text, tail, and child ordering parity on valid XML trees.
- **Rejection Parity Oracle**: Verifies that if Python stdlib `ElementTree` rejects a malformed document, SafeXML also rejects it and never panics or accepts invalid syntax.
- **Amplification Detector**: Computes the ratio of in-memory DOM size to encoded byte size. Rejects any execution that expands beyond $10\times$ without triggering limit enforcement (defense against quadratic blowup and entity-less billion laughs attacks).
- **Chunked Stream Invariance**: Randomizes chunk boundaries (1 to 32 bytes) over file-like streams to ensure streaming reads produce identical trees to in-memory buffers.
- **ATTLIST Default Application**: Validates that default attribute definitions from DTD internal subsets match stdlib XML parser behavior.

---

## 3. Continuous Execution in CI & Nightly Campaigns

- **Pull Request CI**: Every PR runs a multi-target smoke test across all 4 fuzz binaries under AddressSanitizer and value profiling.
- **Nightly Sanitizer Pipeline (`.github/workflows/fuzz.yml`)**: Automated nightly jobs run extensive campaigns on GitHub Actions runners with crash artifact archiving.
- **Google OSS-Fuzz (`oss-fuzz/`)**: Standalone integration scripts package all four fuzz binaries with dictionaries (`fuzz/xml.dict`) and seed corpora for continuous cluster fuzzing.
