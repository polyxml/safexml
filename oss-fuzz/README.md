# Google OSS-Fuzz Integration Guide

SafeXML provides pre-configured integration definitions for [Google OSS-Fuzz](https://github.com/google/oss-fuzz), enabling 24/7 continuous fuzzing across Google Cloud infrastructure with AddressSanitizer (ASan), MemorySanitizer (MSan), and UndefinedBehaviorSanitizer (UBSan).

## Included Artifacts

The [`oss-fuzz/`](.) directory contains:
- `project.yaml`: Project metadata, contacts, languages, and sanitizer configurations.
- `Dockerfile`: Container image specification extending `gcr.io/oss-fuzz-base/base-builder-rust`.
- `build.sh`: Target compilation script using `cargo-fuzz`, packaging the `fuzz_parser` binary, `xml.dict` dictionary, and initial seed corpus.

## Upstream Submission Steps

To integrate SafeXML with OSS-Fuzz:

1. Fork [`google/oss-fuzz`](https://github.com/google/oss-fuzz).
2. Create directory `projects/safexml` in your fork:
   ```bash
   mkdir -p projects/safexml
   cp oss-fuzz/project.yaml projects/safexml/
   cp oss-fuzz/Dockerfile projects/safexml/
   cp oss-fuzz/build.sh projects/safexml/
   ```
3. Test locally using the OSS-Fuzz helper tool:
   ```bash
   python infra/helper.py build_image safexml
   python infra/helper.py build_fuzzers --sanitizer address safexml
   python infra/helper.py run_fuzzer safexml fuzz_parser
   ```
4. Submit a Pull Request to `google/oss-fuzz` titled `safexml: Initial integration`.
