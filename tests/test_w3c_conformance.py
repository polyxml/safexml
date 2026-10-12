"""Tests for W3C XML Conformance validation and manifest runner."""

from __future__ import annotations

from pathlib import Path

import pytest

import safexml
from scripts.run_w3c_conformance import (
    ensure_corpus,
    parse_manifests,
    print_report,
    run_conformance,
)
from scripts.run_w3c_conformance import (
    main as runner_main,
)


@pytest.fixture(scope="session")
def xmlts_corpus() -> Path:
    corpus_dir = Path(".cache/xmlts/xmlconf")
    return ensure_corpus(corpus_dir)


def test_w3c_manifest_parsing(xmlts_corpus: Path) -> None:
    test_cases = parse_manifests(xmlts_corpus)
    assert len(test_cases) > 2000

    types = {tc.type for tc in test_cases}
    assert "not-wf" in types
    assert "valid" in types


def test_w3c_conformance_runner_execution(
    xmlts_corpus: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    test_cases = parse_manifests(xmlts_corpus)
    # Run across entire corpus
    results = run_conformance(test_cases)

    assert results["not_wf"]["total"] >= 1400
    assert results["not_wf"]["properly_rejected"] >= 900
    assert len(results["not_wf"]["discrepancies"]) == 0

    assert results["valid"]["total"] >= 800
    assert results["valid"]["passed"] >= 500
    assert len(results["valid"]["discrepancies"]) == 0

    print_report(results)
    captured = capsys.readouterr()
    assert "ALL QUALITY CRITERIA MET (0 DISCREPANCIES)" in captured.out


def test_w3c_conformance_runner_main(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "sys.argv",
        [
            "run_w3c_conformance.py",
            "--corpus-dir",
            ".cache/xmlts/xmlconf",
            "--json",
        ],
    )
    exit_code = runner_main()
    assert exit_code == 0


def test_w3c_xml_declaration_wellformedness() -> None:
    # Encoding mismatch between BOM and declaration
    with pytest.raises(safexml.DefusedXmlException, match="Encoding mismatch"):
        safexml.fromstring(
            b"\xff\xfe<\x00?\x00x\x00m\x00l\x00 \x00v\x00e\x00r\x00s\x00i\x00o\x00n\x00=\x00'\x001\x00.\x000\x00'\x00 \x00e\x00n\x00c\x00o\x00d\x00i\x00n\x00g\x00=\x00'\x00u\x00t\x00f\x00-\x008\x00'\x00?\x00>\x00<\x00r\x00o\x00o\x00t\x00/\x00>\x00"
        )

    # XML declaration after leading whitespace
    with pytest.raises(safexml.DefusedXmlException, match="XML declaration"):
        safexml.fromstring(b"   <?xml version='1.0'?><root/>")

    # XML declaration after leading comment
    with pytest.raises(safexml.DefusedXmlException, match="XML declaration"):
        safexml.fromstring(b"<!-- comment --><?xml version='1.0'?><root/>")

    # XML declaration uppercase VERSION
    with pytest.raises(safexml.DefusedXmlException):
        safexml.fromstring(b"<?xml VERSION='1.0'?><root/>")

    # XML declaration encoding before version
    with pytest.raises(safexml.DefusedXmlException):
        safexml.fromstring(b"<?xml encoding='UTF-8' version='1.0'?><root/>")

    # XML declaration invalid standalone
    with pytest.raises(safexml.DefusedXmlException):
        safexml.fromstring(b"<?xml version='1.0' standalone='YES'?><root/>")

    # XML declaration missing whitespace between attributes
    with pytest.raises(safexml.DefusedXmlException):
        safexml.fromstring(b"<?xml version='1.0'encoding='UTF-8'?><root/>")

    # XML declaration invalid encoding name
    with pytest.raises(safexml.DefusedXmlException):
        safexml.fromstring(b"<?xml version='1.0' encoding='123bad'?><root/>")


def test_w3c_content_wellformedness() -> None:
    # ']]>' in character data
    with pytest.raises(safexml.DefusedXmlException, match="']]>' not allowed"):
        safexml.fromstring(b"<root>content]]>more</root>")

    # Missing whitespace between element attributes
    with pytest.raises(safexml.DefusedXmlException, match="Whitespace required"):
        safexml.fromstring(b'<root att="val"att2="val2"/>')

    # Comment ending with 3 dashes
    with pytest.raises(safexml.DefusedXmlException, match="Comment cannot"):
        safexml.fromstring(b"<!-- bad comment ---><root/>")

    # PI target invalid, reserved, or containing colon inside document
    with pytest.raises(safexml.DefusedXmlException, match="processing instruction"):
        safexml.fromstring(b"<root><?xmL bad?></root>")

    with pytest.raises(safexml.DefusedXmlException, match="processing instruction"):
        safexml.fromstring(b"<root><??></root>")

    with pytest.raises(safexml.DefusedXmlException, match="processing instruction"):
        safexml.fromstring(b"<root><?a:b bad?></root>")

    # Invalid control characters in prolog (vertical tab / form feed)
    with pytest.raises(safexml.DefusedXmlException):
        safexml.fromstring(b"\x0b<root/>")

    with pytest.raises(safexml.DefusedXmlException):
        safexml.fromstring(b"\x0c<root/>")

    # Mixed case DOCTYPE keyword
    with pytest.raises(safexml.DefusedXmlException, match="DOCTYPE keyword"):
        safexml.fromstring(b"<!DOCtYPE root [\n<!ELEMENT root EMPTY>\n]><root/>")
