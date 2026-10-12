#!/usr/bin/env python3
"""Industrial schema performance & memory profiling benchmark for SafeXML.

Measures single-threaded and multi-threaded throughput, speedup, and peak RSS
across real-world multi-namespace industrial documents from polyxml-schema-corpus.
"""

from __future__ import annotations

import argparse
import resource
import time
import tracemalloc
import xml.etree.ElementTree as std_ET
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path

import defusedxml.ElementTree as defused_ET

import safexml

CORPUS_DIR = Path("/home/xenah/github/polyxml-schema-corpus/schemas")


@dataclass
class BenchmarkResult:
    name: str
    size_kb: float
    safexml_ms: float
    defusedxml_ms: float
    stdlib_ms: float
    safexml_throughput_mb_s: float
    peak_rss_mb: float
    threaded_workers: int
    threaded_speedup: float


def benchmark_single_document(file_path: Path, iterations: int = 5) -> BenchmarkResult:
    data = file_path.read_bytes()
    size_kb = len(data) / 1024.0

    # Warmup
    safexml.fromstring(data)
    std_ET.fromstring(data)
    defused_ET.fromstring(data)

    # 1. Benchmark SafeXML
    t0 = time.perf_counter()
    for _ in range(iterations):
        safexml.fromstring(data)
    safexml_ms = (time.perf_counter() - t0) / iterations * 1000.0

    # 2. Benchmark defusedxml
    t0 = time.perf_counter()
    for _ in range(iterations):
        defused_ET.fromstring(data)
    defusedxml_ms = (time.perf_counter() - t0) / iterations * 1000.0

    # 3. Benchmark stdlib
    t0 = time.perf_counter()
    for _ in range(iterations):
        std_ET.fromstring(data)
    stdlib_ms = (time.perf_counter() - t0) / iterations * 1000.0

    throughput_mb_s = (size_kb / 1024.0) / (safexml_ms / 1000.0)

    # 4. Memory profiling (peak RSS and tracemalloc)
    tracemalloc.start()
    rss_before = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    for _ in range(5):
        safexml.fromstring(data)
    current_mem, peak_mem = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    rss_after = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    # On Linux ru_maxrss is in KiB
    peak_rss_mb = max(peak_mem / 1024.0 / 1024.0, (rss_after - rss_before) / 1024.0)

    # 5. Multi-threaded benchmark
    workers = 4
    total_tasks = workers * 4

    def safe_task() -> None:
        safexml.fromstring(data)

    def defused_task() -> None:
        defused_ET.fromstring(data)

    t0 = time.perf_counter()
    with ThreadPoolExecutor(max_workers=workers) as ex:
        list(ex.map(lambda _: safe_task(), range(total_tasks)))
    safe_thread_time = time.perf_counter() - t0

    t0 = time.perf_counter()
    with ThreadPoolExecutor(max_workers=workers) as ex:
        list(ex.map(lambda _: defused_task(), range(total_tasks)))
    defused_thread_time = time.perf_counter() - t0

    speedup = (defused_thread_time / safe_thread_time) if safe_thread_time else 1.0

    return BenchmarkResult(
        name=file_path.name,
        size_kb=size_kb,
        safexml_ms=safexml_ms,
        defusedxml_ms=defusedxml_ms,
        stdlib_ms=stdlib_ms,
        safexml_throughput_mb_s=throughput_mb_s,
        peak_rss_mb=peak_rss_mb,
        threaded_workers=workers,
        threaded_speedup=speedup,
    )


def run_benchmarks(corpus_dir: Path) -> list[BenchmarkResult]:
    candidates = [
        corpus_dir / "ubl-2.1/common/UBL-CommonAggregateComponents-2.1.xsd",
        corpus_dir / "hl7-fhir/fhir-single.xsd",
        corpus_dir / "defense-uci/UCI_MessageDefinitions_v2_5_0.xsd",
        corpus_dir / "finance-fpml/fpml-loan-5-12.xsd",
        corpus_dir / "iso20022/camt.054.001.08.xsd",
        corpus_dir / "transit-railml/railML.xsd",
    ]

    results: list[BenchmarkResult] = []
    for c in candidates:
        if c.exists():
            print(f"Benchmarking {c.name} ({c.stat().st_size / 1024:.1f} KB)...")
            res = benchmark_single_document(c)
            results.append(res)
    return results


def print_table(results: list[BenchmarkResult]) -> None:
    print("\n" + "=" * 90)
    print("INDUSTRIAL CORPUS PERFORMANCE & MEMORY PROFILING REPORT")
    print("=" * 90)
    print(
        f"{'Document Name':35} | {'Size':8} | {'SafeXML':8} | {'defused':8} | {'Throughput':12} | {'4-Worker Speedup'}"
    )
    print("-" * 90)
    for r in results:
        print(
            f"{r.name[:35]:35} | {r.size_kb:6.1f}KB | {r.safexml_ms:6.1f}ms | {r.defusedxml_ms:6.1f}ms | {r.safexml_throughput_mb_s:8.1f} MB/s | {r.threaded_speedup:4.2f}x vs defused"
        )
    print("=" * 90)


def main() -> int:
    parser = argparse.ArgumentParser(description="Industrial Schema Benchmark Runner")
    parser.add_argument(
        "--corpus-dir",
        type=Path,
        default=CORPUS_DIR,
        help="Path to polyxml-schema-corpus schemas directory",
    )
    args = parser.parse_args()

    if not args.corpus_dir.exists():
        print(f"Error: Corpus directory not found at {args.corpus_dir}")
        return 1

    results = run_benchmarks(args.corpus_dir)
    print_table(results)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
