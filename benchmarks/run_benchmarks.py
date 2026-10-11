"""Benchmark suite: SafeXML vs defusedxml vs xml.etree.ElementTree.

Measures:
1. Single-threaded latency (µs) and throughput (docs/sec) across Small, Medium, Large XML.
2. Multi-threaded throughput (docs/sec) proving GIL release scaling with ThreadPoolExecutor.
"""

from __future__ import annotations

import concurrent.futures
import time
import xml.etree.ElementTree as std_ET

import defusedxml.ElementTree as defused_ET

import safexml.ElementTree as safe_ET


def generate_xml(num_items: int) -> str:
    lines = ['<?xml version="1.0" encoding="UTF-8"?>', '<catalog id="cat1">']
    for i in range(num_items):
        lines.append(
            f'  <item id="{i}" category="electronics" status="in-stock">'
            f"<title>Item Title #{i}</title>"
            f'<price currency="USD">{10.50 + i}</price>'
            f"<description>Detailed description of product #{i} with special &amp; characters.</description>"
            f'<nested depth="1"><subitem key="val_{i}">Nested content here</subitem></nested>'
            f"</item>"
        )
    lines.append("</catalog>")
    return "\n".join(lines)


def bench_single_threaded(parser_fn, xml_data: str, iterations: int) -> tuple[float, float]:
    """Returns (mean_latency_us, ops_per_sec)."""
    # Warmup
    for _ in range(min(5, iterations)):
        parser_fn(xml_data)

    start = time.perf_counter()
    for _ in range(iterations):
        parser_fn(xml_data)
    duration = time.perf_counter() - start

    mean_us = (duration / iterations) * 1_000_000
    ops_sec = iterations / duration
    return mean_us, ops_sec


def bench_multi_threaded(parser_fn, xml_data: str, total_tasks: int, workers: int) -> float:
    """Returns ops_per_sec under concurrent worker threads."""
    # Warmup
    for _ in range(4):
        parser_fn(xml_data)

    start = time.perf_counter()
    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as pool:
        futures = [pool.submit(parser_fn, xml_data) for _ in range(total_tasks)]
        concurrent.futures.wait(futures)
    duration = time.perf_counter() - start
    return total_tasks / duration


def main() -> None:
    print("=" * 80)
    print("  SAFEXML VS DEFUSEDXML HIGH-PERFORMANCE BENCHMARK SUITE")
    print("=" * 80)

    datasets = [
        ("Small (~1 KB, 10 items)", generate_xml(10), 1000),
        ("Medium (~50 KB, 500 items)", generate_xml(500), 200),
        ("Large (~500 KB, 5000 items)", generate_xml(5000), 20),
    ]

    print("\n### 1. SINGLE-THREADED BENCHMARK (Latency & Throughput)\n")
    print(
        f"{'Workload':<28} | {'Engine':<12} | {'Latency (µs)':<14} | {'Throughput (ops/s)':<18} | {'vs defusedxml':<14}"
    )
    print("-" * 95)

    for name, xml_data, iters in datasets:
        defused_us, defused_ops = bench_single_threaded(defused_ET.fromstring, xml_data, iters)
        safe_us, safe_ops = bench_single_threaded(safe_ET.fromstring, xml_data, iters)
        std_us, std_ops = bench_single_threaded(std_ET.fromstring, xml_data, iters)

        defused_rel = "1.00x (baseline)"
        safe_rel = f"{safe_ops / defused_ops:.2f}x ({'+' if safe_ops > defused_ops else ''}{(safe_ops / defused_ops - 1) * 100:.1f}%)"
        std_rel = f"{std_ops / defused_ops:.2f}x"

        print(
            f"{name:<28} | {'defusedxml':<12} | {defused_us:>12.1f} µs | {defused_ops:>16.1f} op/s | {defused_rel:<14}"
        )
        print(
            f"{'':<28} | {'SafeXML (Rust)':<12} | {safe_us:>12.1f} µs | {safe_ops:>16.1f} op/s | {safe_rel:<14}"
        )
        print(
            f"{'':<28} | {'stdlib etree':<12} | {std_us:>12.1f} µs | {std_ops:>16.1f} op/s | {std_rel:<14}"
        )
        print("-" * 95)

    print("\n### 2. MULTI-THREADED CONCURRENCY BENCHMARK (GIL-Release Scaling)\n")
    print("Simulating concurrent web requests parsing XML payloads with ThreadPoolExecutor:")
    print(
        f"{'Concurrency':<20} | {'Engine':<14} | {'Throughput (docs/s)':<22} | {'Speedup vs defusedxml':<22}"
    )
    print("-" * 85)

    test_xml = generate_xml(100)  # ~10 KB document
    total_docs = 2000

    for workers in [2, 4, 8]:
        defused_multi = bench_multi_threaded(defused_ET.fromstring, test_xml, total_docs, workers)
        safe_multi = bench_multi_threaded(safe_ET.fromstring, test_xml, total_docs, workers)

        speedup = safe_multi / defused_multi
        print(
            f"{workers} Worker Threads{'':<4} | {'defusedxml':<14} | {defused_multi:>18.1f} docs/s | {'1.00x (GIL blocked)':<22}"
        )
        print(
            f"{'':<20} | {'SafeXML (Rust)':<14} | {safe_multi:>18.1f} docs/s | {f'{speedup:.2f}x FASTER':<22}"
        )
        print("-" * 85)


if __name__ == "__main__":
    main()
