"""Benchmark comparisons: safexml vs defusedxml vs xml.etree.ElementTree."""

from __future__ import annotations

import xml.etree.ElementTree as std_ET

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


def test_benchmark_safexml(benchmark) -> None:
    res = benchmark(safe_ET.fromstring, BENCHMARK_XML)
    assert res.tag == "catalog"
    assert len(res) == 200


def test_benchmark_defusedxml(benchmark) -> None:
    res = benchmark(defused_ET.fromstring, BENCHMARK_XML)
    assert res.tag == "catalog"
    assert len(res) == 200


def test_benchmark_stdlib(benchmark) -> None:
    res = benchmark(std_ET.fromstring, BENCHMARK_XML)
    assert res.tag == "catalog"
    assert len(res) == 200
