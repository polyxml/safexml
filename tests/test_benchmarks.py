"""Benchmark comparisons: safexml vs defusedxml vs xml.etree.ElementTree."""

from __future__ import annotations

import concurrent.futures
import xml.etree.ElementTree as std_ET
from typing import Any

import defusedxml.ElementTree as defused_ET

import safexml.ElementTree as safe_ET

# 100-item XML document for benchmarking
BENCHMARK_XML = (
    "<catalog>"
    + "".join(
        f'<item id="{i}"><name>Item #{i}</name><value>{i * 1.5}</value><status active="true">OK</status></item>'
        for i in range(200)
    )
    + "</catalog>"
)


def test_benchmark_safexml(benchmark: Any) -> None:
    res = benchmark(safe_ET.fromstring, BENCHMARK_XML)
    assert res.tag == "catalog"
    assert len(res) == 200


def test_benchmark_defusedxml(benchmark: Any) -> None:
    res = benchmark(defused_ET.fromstring, BENCHMARK_XML)
    assert res.tag == "catalog"
    assert len(res) == 200


def test_benchmark_stdlib(benchmark: Any) -> None:
    res = benchmark(std_ET.fromstring, BENCHMARK_XML)
    assert res.tag == "catalog"
    assert len(res) == 200


def test_benchmark_safexml_multithreaded(benchmark: Any) -> None:
    def _run() -> None:
        with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
            futures = [pool.submit(safe_ET.fromstring, BENCHMARK_XML) for _ in range(20)]
            concurrent.futures.wait(futures)

    benchmark(_run)


def test_benchmark_defusedxml_multithreaded(benchmark: Any) -> None:
    def _run() -> None:
        with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
            futures = [pool.submit(defused_ET.fromstring, BENCHMARK_XML) for _ in range(20)]
            concurrent.futures.wait(futures)

    benchmark(_run)
