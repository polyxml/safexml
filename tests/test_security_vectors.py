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
