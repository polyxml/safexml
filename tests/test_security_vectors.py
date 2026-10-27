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


def test_multiple_roots_and_trailing_unclosed_tags() -> None:
    """Document state machine must reject multiple roots and trailing junk."""
    from safexml.common import ParseError

    # Multiple roots
    with pytest.raises(ParseError):
        ET.fromstring("<signed/><unsigned/>")

    # Trailing unclosed element
    with pytest.raises(ParseError):
        ET.fromstring("<signed/><unsigned>")

    # DOCTYPE after root
    with pytest.raises(ParseError, match="DOCTYPE declaration not allowed"):
        ET.fromstring("<r/><!DOCTYPE r>")


def test_unbound_prefix_rejection() -> None:
    """Elements and attributes with undeclared namespace prefixes must be rejected."""
    from safexml.common import ParseError

    with pytest.raises(ParseError, match="unbound prefix"):
        ET.fromstring("<p:root/>")

    with pytest.raises(ParseError, match="unbound prefix"):
        ET.fromstring('<root p:attr="value"/>')


def test_duplicate_expanded_attribute_rejection() -> None:
    """Attributes that resolve to identical expanded names must be rejected."""
    from safexml.common import ParseError

    xml = '<r xmlns:a="urn:x" xmlns:b="urn:x" a:id="signed" b:id="unsigned"/>'
    with pytest.raises(ParseError, match="duplicate attribute"):
        ET.fromstring(xml)


def test_invalid_xml_names_and_chars_rejection() -> None:
    """XML 1.0 well-formedness rules must reject invalid names, control characters, and malformed syntax."""
    from safexml.common import ParseError

    # Invalid tag name starting with digit
    with pytest.raises(ParseError):
        ET.fromstring("<1root/>")

    # NUL character in text
    with pytest.raises(ParseError, match="Null byte|character"):
        ET.fromstring("<r>\x00</r>")

    # Invalid numeric entity (NUL)
    with pytest.raises(ParseError, match="Invalid XML character reference"):
        ET.fromstring("<r>&#0;</r>")

    # Uppercase hex entity reference
    with pytest.raises(ParseError, match="Invalid uppercase character reference"):
        ET.fromstring("<r>&#X41;</r>")

    # Raw '<' in attribute value
    with pytest.raises(ParseError, match="Attribute value contains unescaped"):
        ET.fromstring('<r a="<"/>')

    # Double-dash inside comment
    with pytest.raises(ParseError, match="Comment cannot contain '--'"):
        ET.fromstring("<r><!--a--b--></r>")


def test_multibyte_utf8_dtd_robustness() -> None:
    """Multi-byte UTF-8 sequences in DTD must not panic or corrupt scanner indexing."""
    from safexml.common import ParseError

    # Multibyte character in DTD name/text
    root = ET.fromstring("<!DOCTYPE r é><r/>")
    assert root.tag == "r"

    # Multibyte entity value blocked cleanly without panic
    with pytest.raises((EntitiesForbidden, ParseError)):
        ET.fromstring("<!DOCTYPE r [<!ENTITY e é>]><r/>")

    # Comment containing multibyte character in DTD parsed cleanly
    root_cmt = ET.fromstring("<!DOCTYPE r [<!-- <!ENTITY fake é> -->]><r/>")
    assert root_cmt.tag == "r"

    # Comment containing quoted entity in DTD
    root_cmt2 = ET.fromstring('<!DOCTYPE r [<!-- <!ENTITY fake "x"> -->]><r/>')
    assert root_cmt2.tag == "r"


def test_namespace_amplification_defense() -> None:
    """Namespace declarations and values must be bounded by attribute limits."""
    # Attribute count limit applies to xmlns
    with pytest.raises(DefusedXmlException, match="attribute count limit"):
        ET.fromstring('<r xmlns:a="x" xmlns:b="y"/>', max_attributes=1)

    # Attribute size limit applies to xmlns URI
    with pytest.raises(DefusedXmlException, match="maximum size limit"):
        ET.fromstring('<r xmlns="http://example.com/very/long/uri"/>', max_attribute_size=10)

    # Namespace entity expansion & resolution
    root = ET.fromstring('<r xmlns="urn:a&amp;b"/>')
    assert root.tag == "{urn:a&b}r"

    with pytest.raises(EntitiesForbidden):
        ET.fromstring('<r xmlns="urn:&evil;"/>')


def test_short_read_stream_robustness() -> None:
    """Stream reader must handle chunked reads and enforce limits across chunk boundaries."""

    class ChunkedStream:
        def __init__(self, data: bytes, chunk_size: int = 4) -> None:
            self.data = data
            self.chunk_size = chunk_size
            self.pos = 0

        def read(self, n: int = -1) -> bytes:
            if self.pos >= len(self.data):
                return b""
            amt = min(self.chunk_size, len(self.data) - self.pos)
            res = self.data[self.pos : self.pos + amt]
            self.pos += amt
            return res

    xml_data = b"<root><child id='c1'>content</child></root>"
    stream = ChunkedStream(xml_data, chunk_size=3)
    root = ET.parse(stream).getroot()
    assert root.tag == "root"
    assert root[0].attrib["id"] == "c1"
    assert root[0].text == "content"


def test_deep_nesting_wrappers_no_recursion_error() -> None:
    """iterparse, sax, and minidom must handle deep document trees iteratively without RecursionError."""
    from xml.sax.handler import ContentHandler

    import safexml.minidom
    import safexml.sax

    depth = 1000
    xml = "<r>" * depth + "</r>" * depth

    # ElementTree.iterparse
    events = list(ET.iterparse(io.StringIO(xml)))
    assert len(events) == depth

    # SAX
    handler = ContentHandler()
    safexml.sax.parseString(xml, handler)

    # Minidom
    doc = safexml.minidom.parseString(xml)
    assert doc.documentElement.tagName == "r"


def test_attlist_default_attribute_security_limits() -> None:
    """ATTLIST default attributes must enforce entity, size, count, name, and character restrictions."""
    from safexml.common import ParseError

    # Entity reference inside ATTLIST default value blocked when forbid_entities=True
    with pytest.raises(EntitiesForbidden):
        ET.fromstring('<!DOCTYPE r [<!ATTLIST r a CDATA "&evil;">]><r/>')

    # Oversized default attribute value rejected by max_attribute_size
    big_val = "A" * 200
    with pytest.raises(DefusedXmlException, match="maximum size limit"):
        ET.fromstring(
            f'<!DOCTYPE r [<!ATTLIST r a CDATA "{big_val}">]><r/>',
            max_attribute_size=50,
        )

    # Default attributes counted toward max_attributes
    with pytest.raises(DefusedXmlException, match="attribute count limit"):
        ET.fromstring(
            '<!DOCTYPE r [<!ATTLIST r a CDATA "1" b CDATA "2" c CDATA "3">]><r/>',
            max_attributes=2,
        )

    # Oversized attribute name in ATTLIST rejected by max_name_size
    long_name = "attr_" + "x" * 100
    with pytest.raises(DefusedXmlException, match="maximum length limit"):
        ET.fromstring(
            f'<!DOCTYPE r [<!ATTLIST r {long_name} CDATA "1">]><r/>',
            max_name_size=20,
        )

    # Unescaped '<' in ATTLIST default value rejected
    with pytest.raises(ParseError, match="Attribute value contains unescaped"):
        ET.fromstring('<!DOCTYPE r [<!ATTLIST r a CDATA "<script>">]><r/>')


def test_xmlparser_feed_input_size_limit() -> None:
    """XMLParser.feed() must enforce max_input_size immediately before buffering unbounded data."""
    parser = ET.XMLParser(max_input_size=20)
    parser.feed("<root>")
    with pytest.raises(DefusedXmlException, match="exceeds maximum allowed limit"):
        parser.feed("A" * 50)
