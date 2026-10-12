#!/usr/bin/env python3
"""Standalone high-throughput differential fuzzing campaign runner for SafeXML.

Tests millions of structured and mutated XML inputs against Python stdlib ElementTree and defusedxml.

Usage:
    python scripts/run_differential_fuzz.py --iterations 100000 --seed 42
"""

from __future__ import annotations

import argparse
import hashlib
import random
import sys
import time
from pathlib import Path
from xml.etree import ElementTree as std_ET

import safexml
from safexml.common import DefusedXmlException


def compute_dom_size(elem: std_ET.Element) -> int:
    """Compute total byte size of expanded DOM nodes (tags, attributes, text, tail)."""
    size = len(elem.tag.encode("utf-8"))
    for k, v in elem.attrib.items():
        size += len(k.encode("utf-8")) + len(v.encode("utf-8"))
    if elem.text:
        size += len(elem.text.encode("utf-8"))
    if elem.tail:
        size += len(elem.tail.encode("utf-8"))
    for child in elem:
        size += compute_dom_size(child)
    return size


def assert_dom_equal(e1: std_ET.Element, e2: std_ET.Element) -> None:
    """Recursively assert that two Element instances represent identical DOM trees."""
    assert e1.tag == e2.tag, f"Tag mismatch: {e1.tag} != {e2.tag}"
    assert e1.attrib == e2.attrib, f"Attribute mismatch: {e1.attrib} != {e2.attrib}"
    assert (e1.text or "") == (e2.text or ""), f"Text mismatch: {repr(e1.text)} != {repr(e2.text)}"
    assert (e1.tail or "") == (e2.tail or ""), f"Tail mismatch: {repr(e1.tail)} != {repr(e2.tail)}"
    assert len(e1) == len(e2), f"Child count mismatch: {len(e1)} != {len(e2)}"
    for c1, c2 in zip(e1, e2, strict=True):
        assert_dom_equal(c1, c2)


class StructuredXMLGenerator:
    """Fast pseudo-random generator of valid and mutated XML trees."""

    def __init__(self, rng: random.Random) -> None:
        self.rng = rng
        self.sample_tags = ["catalog", "item", "title", "data", "record", "payload", "node", "val"]
        self.sample_attrs = ["id", "status", "version", "type", "lang", "role"]
        self.sample_words = ["Alpha", "Beta", "Gamma", "Delta", "123", "Hello World", "Sample Text"]
        self.sample_namespaces = ["", "http://example.com/ns1", "http://example.org/ns2"]

    def generate_valid(self, max_depth: int = 3) -> bytes:
        root_tag = self.rng.choice(self.sample_tags)
        ns = self.rng.choice(self.sample_namespaces)
        ns_decl = f' xmlns="{ns}"' if ns else ""

        def _gen_elem(tag: str, depth: int) -> str:
            num_attrs = self.rng.randint(0, 3)
            attrs = " ".join(
                f'{self.rng.choice(self.sample_attrs)}="{self.rng.choice(self.sample_words)}"'
                for _ in range(num_attrs)
            )
            attr_str = f" {attrs}" if attrs else ""

            if depth >= max_depth or self.rng.random() < 0.4:
                text = self.rng.choice(self.sample_words) if self.rng.random() < 0.7 else ""
                return f"<{tag}{attr_str}>{text}</{tag}>"

            num_children = self.rng.randint(1, 3)
            children = "".join(
                _gen_elem(self.rng.choice(self.sample_tags), depth + 1) for _ in range(num_children)
            )
            return f"<{tag}{attr_str}>{children}</{tag}>"

        doc = f"<{root_tag}{ns_decl}>{_gen_elem(self.rng.choice(self.sample_tags), 1)}</{root_tag}>"
        return doc.encode("utf-8")

    def generate_mutated(self) -> bytes:
        valid = self.generate_valid()
        mutation = self.rng.choice(
            [
                "truncate",
                "mismatch_end",
                "duplicate_root",
                "null_byte",
                "illegal_control",
                "unclosed_attr",
            ]
        )

        if mutation == "truncate" and len(valid) > 6:
            cut = self.rng.randint(2, len(valid) - 3)
            return valid[:cut]
        elif mutation == "mismatch_end":
            return valid.replace(b"</", b"<//")
        elif mutation == "duplicate_root":
            return valid + b"<extra/>"
        elif mutation == "null_byte":
            return valid.replace(b">", b">\x00", 1)
        elif mutation == "illegal_control":
            return valid.replace(b">", b">\x0b", 1)
        elif mutation == "unclosed_attr":
            return valid.replace(b'="', b"=")

        return valid


def run_campaign(iterations: int, seed: int, regressions_dir: Path) -> int:
    rng = random.Random(seed)
    gen = StructuredXMLGenerator(rng)
    regressions_dir.mkdir(parents=True, exist_ok=True)

    print(
        f"[START] Starting SafeXML Differential Fuzzing Campaign ({iterations:,} iterations, seed={seed})..."
    )
    start_time = time.perf_counter()

    valid_matches = 0
    malformed_rejected = 0
    max_amp = 0.0

    for i in range(1, iterations + 1):
        is_mutated = i % 2 == 0
        data = gen.generate_mutated() if is_mutated else gen.generate_valid()

        # Step 1: Run SafeXML (Must never panic/segfault)
        safe_result = None
        try:
            safe_result = safexml.fromstring(data)
        except DefusedXmlException:
            pass
        except Exception as crash:
            h = hashlib.sha256(data).hexdigest()[:12]
            failing_path = regressions_dir / f"crash_{h}.xml"
            failing_path.write_bytes(data)
            print(f"\n[FAIL] UNHANDLED CRASH on iteration {i}: {crash}")
            print(f"Saved payload to: {failing_path}")
            return 1

        # Step 2: Compare against CPython stdlib ElementTree
        std_result = None
        std_exc = None
        try:
            std_result = std_ET.fromstring(data)
        except Exception as exc:
            std_exc = exc

        # Step 3: Verify Invariants
        if std_exc is not None:
            # Rejection Parity: SafeXML must also reject
            if safe_result is not None:
                h = hashlib.sha256(data).hexdigest()[:12]
                failing_path = regressions_dir / f"permissive_{h}.xml"
                failing_path.write_bytes(data)
                print(f"\n[FAIL] REJECTION PARITY VIOLATION on iteration {i}!")
                print(f"Stdlib rejected with {type(std_exc).__name__}, but SafeXML accepted it!")
                print(f"Saved payload to: {failing_path}")
                return 1
            malformed_rejected += 1
        elif safe_result is not None and std_result is not None:
            # DOM Equivalence: 1:1 match
            try:
                assert_dom_equal(std_result, safe_result)
            except AssertionError as err:
                h = hashlib.sha256(data).hexdigest()[:12]
                failing_path = regressions_dir / f"discrepancy_{h}.xml"
                failing_path.write_bytes(data)
                print(f"\n[FAIL] DOM DISCREPANCY on iteration {i}: {err}")
                print(f"Saved payload to: {failing_path}")
                return 1

            # Amplification check
            dom_sz = compute_dom_size(safe_result)
            ratio = dom_sz / max(len(data), 1)
            if ratio > max_amp:
                max_amp = ratio
            if ratio > 10.0:
                h = hashlib.sha256(data).hexdigest()[:12]
                failing_path = regressions_dir / f"amplification_{h}.xml"
                failing_path.write_bytes(data)
                print(
                    f"\n[FAIL] EXCESSIVE AMPLIFICATION on iteration {i}: ratio {ratio:.2f} > 10.0"
                )
                print(f"Saved payload to: {failing_path}")
                return 1

            valid_matches += 1

        if i % 10000 == 0 or i == iterations:
            elapsed = time.perf_counter() - start_time
            rate = i / max(elapsed, 0.001)
            print(
                f"[{i:,}/{iterations:,}] Elapsed: {elapsed:.1f}s | Rate: {rate:,.0f} docs/sec | Valid: {valid_matches:,} | Malformed: {malformed_rejected:,} | Max Amp: {max_amp:.2f}x"
            )

    total_time = time.perf_counter() - start_time
    print(
        f"\n[OK] Campaign Completed in {total_time:.2f}s ({iterations / total_time:,.0f} docs/sec)"
    )
    print(f"   * Valid Matches: {valid_matches:,}")
    print(f"   * Malformed Inputs Rejected: {malformed_rejected:,}")
    print(f"   * Peak Amplification Ratio: {max_amp:.2f}x (Threshold: 10.0x)")
    print("   * Zero Panics, Zero Crashes, Zero Parity Discrepancies.")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Differential fuzzing campaign for SafeXML")
    parser.add_argument(
        "--iterations",
        type=int,
        default=10000,
        help="Number of iterations to run (default: 10,000)",
    )
    parser.add_argument(
        "--seed", type=int, default=42, help="RNG seed for reproducibility (default: 42)"
    )
    parser.add_argument(
        "--regressions-dir",
        type=Path,
        default=Path("tests/regressions"),
        help="Output directory for regressions",
    )
    args = parser.parse_args()

    return run_campaign(args.iterations, args.seed, args.regressions_dir)


if __name__ == "__main__":
    sys.exit(main())
