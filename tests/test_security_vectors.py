"""Comprehensive tests for XML security vulnerabilities.

Verifies strict rejection of:
1. Billion Laughs (exponential entity expansion)
2. Quadratic blowup attacks
3. XML External Entity (XXE) injection (SYSTEM and PUBLIC)
4. Cyclic entity references
5. External DTD injections (DTDForbidden)
6. Deep nesting recursion attacks (C stack exhaustion)
7. Text size and memory limits
"""

from __future__ import annotations

import io

import pytest

import safexml.ElementTree as ET
from safexml.common import (
    DefusedXmlException,
    DTDForbidden,
    EntitiesForbidden,
    ExternalReferenceForbidden,
)


def test_xml_bomb_billion_laughs(xml_bomb: str) -> None:
    """Billion laughs attack must be rejected via EntitiesForbidden."""
    with pytest.raises(EntitiesForbidden) as excinfo:
        ET.fromstring(xml_bomb)
    assert excinfo.value.name in ("a", "b", "c", "d", "e")
    assert "EntitiesForbidden" in repr(excinfo.value)


def test_quadratic_blowup(xml_quadratic: str) -> None:
    """Quadratic blowup entity attack must be rejected via EntitiesForbidden."""
    with pytest.raises(EntitiesForbidden) as excinfo:
        ET.fromstring(xml_quadratic)
    assert excinfo.value.name == "a"


def test_external_entity_system(xml_external: str) -> None:
    """External entity reference with HTTP URI must be blocked."""
    with pytest.raises(ExternalReferenceForbidden) as excinfo:
        ET.fromstring(xml_external)
    assert excinfo.value.sysid == "http://www.w3schools.com/xml/note.xml"
    assert "ExternalReferenceForbidden" in repr(excinfo.value)


def test_external_entity_file(xml_external_file: str) -> None:
    """External entity reference with file:// URI must be blocked."""
    with pytest.raises(ExternalReferenceForbidden) as excinfo:
        ET.fromstring(xml_external_file)
    assert excinfo.value.sysid == "file:///etc/passwd"


def test_cyclic_entities(xml_cyclic: str) -> None:
    """Cyclic entity definitions must be blocked."""
    with pytest.raises(EntitiesForbidden) as excinfo:
        ET.fromstring(xml_cyclic)
    assert excinfo.value.name in ("a", "b")


def test_dtd_forbidden(xml_external_dtd: str) -> None:
    """Enabling forbid_dtd=True must reject all DOCTYPEs."""
    with pytest.raises(DTDForbidden) as excinfo:
        ET.fromstring(xml_external_dtd, forbid_dtd=True)
    assert excinfo.value.name == "html"
    assert "DTDForbidden" in repr(excinfo.value)


def test_dtd_external_reference_forbidden(xml_external_dtd: str) -> None:
    """Default forbid_external=True must reject DOCTYPE with external SYSTEM/PUBLIC ID."""
    with pytest.raises(ExternalReferenceForbidden) as excinfo:
        ET.fromstring(xml_external_dtd, forbid_external=True)
    assert excinfo.value.pubid == "-//W3C//DTD XHTML 1.0 Transitional//EN"
    assert excinfo.value.sysid == "http://www.w3.org/TR/xhtml1/DTD/xhtml1-transitional.dtd"


def test_deep_nesting_depth_limit() -> None:
    """Deeply nested tags exceeding max_depth must be rejected to prevent call stack overflow."""
    depth = 1200
    nested_xml = ("<a>" * depth) + ("</a>" * depth)
    with pytest.raises(DefusedXmlException) as excinfo:
        ET.fromstring(nested_xml, max_depth=1000)
    assert "depth limit" in str(excinfo.value)


def test_custom_max_depth() -> None:
    """Custom max_depth limit must be strictly enforced."""
    xml = "<a><b><c><d><e/></d></c></b></a>"
    with pytest.raises(DefusedXmlException):
        ET.fromstring(xml, max_depth=3)

    # Allowed when depth is within limits
    root = ET.fromstring(xml, max_depth=10)
    assert root.tag == "a"


def test_attribute_entity_injection() -> None:
    """Entities inside attribute values must be strictly checked."""
    attack_attr = '<root attr="hello &evil; world"/>'
    with pytest.raises(EntitiesForbidden) as excinfo:
        ET.fromstring(attack_attr, forbid_entities=True)
    assert excinfo.value.name == "evil"


def test_parse_file_like_object(xml_bomb: str) -> None:
    """parse() on file-like objects must enforce entity protection."""
    bio = io.BytesIO(xml_bomb.encode("utf-8"))
    with pytest.raises(EntitiesForbidden):
        ET.parse(bio)


def test_iterparse_security(xml_bomb: str) -> None:
    """iterparse() must enforce entity protection."""
    bio = io.BytesIO(xml_bomb.encode("utf-8"))
    with pytest.raises(EntitiesForbidden):
        list(ET.iterparse(bio))


def test_attribute_flood_hash_dos() -> None:
    """Attribute count flood (Attribute Hash DoS / CWE-400) must be rejected."""
    xml = '<root a1="1" a2="2" a3="3" a4="4" a5="5"/>'
    with pytest.raises(DefusedXmlException, match="attribute count limit"):
        ET.fromstring(xml, max_attributes=3)

    # Allowed when below limit
    root = ET.fromstring(xml, max_attributes=10)
    assert len(root.attrib) == 5


def test_giant_attribute_value_bomb() -> None:
    """Giant attribute value bomb (CWE-400) must be rejected."""
    huge_attr = f'<root attr="{"A" * 500}"/>'
    with pytest.raises(DefusedXmlException, match="attribute exceeded maximum size limit"):
        ET.fromstring(huge_attr, max_attribute_size=100)

    # Allowed when below limit
    root = ET.fromstring(huge_attr, max_attribute_size=1000)
    assert len(root.attrib["attr"]) == 500


def test_giant_tag_name_bomb() -> None:
    """Giant element tag name bomb must be rejected."""
    huge_tag = f"<{'A' * 500}/>"
    with pytest.raises(DefusedXmlException, match="tag name exceeded maximum length limit"):
        ET.fromstring(huge_tag, max_name_size=50)

    # Allowed when below limit
    root = ET.fromstring(huge_tag, max_name_size=1000)
    assert len(root.tag) == 500


def test_comment_size_limit() -> None:
    """Giant comment bomb (Comment Amplification / CWE-400) must be rejected."""
    huge_comment = f"<root><!-- {'C' * 500} --></root>"
    with pytest.raises(DefusedXmlException, match="comment exceeded maximum size limit"):
        ET.fromstring(huge_comment, max_comment_size=50)

    # Allowed when below limit
    root = ET.fromstring(huge_comment, max_comment_size=1000)
    assert root.tag == "root"


def test_null_byte_in_tag_name() -> None:
    """Null byte in element tag name must be rejected to prevent C-string truncation attacks."""
    from safexml.common import ParseError

    with pytest.raises(ParseError, match="Null byte"):
        ET.fromstring(b"<root\0bad/>")

    with pytest.raises(ParseError, match="Null byte"):
        ET.fromstring(b"<root><bad\0child/></root>")


def test_null_byte_in_attribute_key() -> None:
    """Null byte in attribute name must be rejected."""
    from safexml.common import ParseError

    with pytest.raises(ParseError, match="Null byte"):
        ET.fromstring(b'<root attr\0bad="value"/>')


def test_parameter_entity_in_dtd() -> None:
    """Parameter entities (%param;) in DTD must be strictly rejected."""
    xml_pe = '<!DOCTYPE root [ <!ENTITY % pe "test"> ]><root/>'
    with pytest.raises(EntitiesForbidden) as excinfo:
        ET.fromstring(xml_pe, forbid_entities=True)
    assert excinfo.value.name == "pe"


def test_text_accumulation_limit() -> None:
    """Text size accumulation limit must prevent memory blowup from uncompressed text."""
    xml = f"<root><child>{'T' * 500}</child></root>"
    with pytest.raises(DefusedXmlException, match="text size limit"):
        ET.fromstring(xml, max_text_size=100)

    # Allowed when below limit
    root = ET.fromstring(xml, max_text_size=1000)
    assert root[0].text == "T" * 500


def test_cdata_accumulation_limit() -> None:
    """CDATA text size accumulation limit must prevent memory blowup via CDATA blocks."""
    xml = f"<root><![CDATA[{'C' * 500}]]></root>"
    with pytest.raises(DefusedXmlException, match="text size limit"):
        ET.fromstring(xml, max_text_size=100)

    # Allowed when below limit
    root = ET.fromstring(xml, max_text_size=1000)
    assert root.text == "C" * 500


def test_max_input_size_limit() -> None:
    """Input size bounding must reject oversized payloads from strings and streams."""
    xml = "<root><item>Hello World</item></root>"
    # Rejection on string
    with pytest.raises(DefusedXmlException, match="input exceeded maximum size limit"):
        ET.fromstring(xml, max_input_size=10)

    # Allowed when below limit
    root = ET.fromstring(xml, max_input_size=100)
    assert root.tag == "root"

    # Rejection on file-like stream
    stream = io.BytesIO(xml.encode("utf-8"))
    with pytest.raises(DefusedXmlException, match="input exceeded maximum size limit"):
        ET.parse(stream, max_input_size=10)


def test_max_elements_limit() -> None:
    """Element count bounding must prevent sibling element expansion DoS."""
    xml = "<root><a/><b/><c/><d/><e/></root>"
    # Total 6 elements (<root>, <a>, <b>, <c>, <d>, <e>)
    with pytest.raises(DefusedXmlException, match="element count limit"):
        ET.fromstring(xml, max_elements=4)

    # Allowed when below or equal to limit
    root = ET.fromstring(xml, max_elements=6)
    assert len(root) == 5
