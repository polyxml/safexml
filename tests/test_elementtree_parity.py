"""Tests verifying 1:1 drop-in parity with xml.etree.ElementTree and defusedxml."""

from __future__ import annotations

import io
import xml.etree.ElementTree as std_ET

import safexml.ElementTree as safe_ET


def test_element_class_identity(xml_simple: str) -> None:
    """Parsed elements must be instances of stdlib xml.etree.ElementTree.Element."""
    root = safe_ET.fromstring(xml_simple)
    assert isinstance(root, std_ET.Element)
    assert isinstance(root[0], std_ET.Element)


def test_dom_parity_simple(xml_simple: str) -> None:
    """Document tree parsed by safexml must match stdlib ElementTree exactly."""
    std_root = std_ET.fromstring(xml_simple)
    safe_root = safe_ET.fromstring(xml_simple)

    assert safe_root.tag == std_root.tag
    assert safe_root.attrib == std_root.attrib
    assert len(safe_root) == len(std_root)

    for safe_child, std_child in zip(safe_root, std_root, strict=True):
        assert safe_child.tag == std_child.tag
        assert safe_child.attrib == std_child.attrib
        for safe_sub, std_sub in zip(safe_child, std_child, strict=True):
            assert safe_sub.tag == std_sub.tag
            assert safe_sub.text == std_sub.text


def test_namespace_resolution(xml_namespaces: str) -> None:
    """Namespace prefixes must be resolved according to ElementTree standards ({uri}tag)."""
    std_root = std_ET.fromstring(xml_namespaces)
    safe_root = safe_ET.fromstring(xml_namespaces)

    assert safe_root.tag == "{http://www.w3.org/2005/Atom}feed"
    assert safe_root.tag == std_root.tag

    std_entry = std_root.find("{http://www.w3.org/2005/Atom}entry")
    safe_entry = safe_root.find("{http://www.w3.org/2005/Atom}entry")
    assert safe_entry is not None
    assert std_entry is not None

    std_creator = std_entry.find("{http://purl.org/dc/elements/1.1/}creator")
    safe_creator = safe_entry.find("{http://purl.org/dc/elements/1.1/}creator")
    assert safe_creator is not None
    assert std_creator is not None
    assert safe_creator.text == std_creator.text == "John Doe"


def test_standard_entities_and_cdata() -> None:
    """Predefined entities (&amp;, etc.) and CDATA sections must decode correctly."""
    xml = """<root>
        <data id="1">Tom &amp; Jerry &lt;3</data>
        <data id="2">Quotes: &quot;hello&quot; and &apos;world&apos;</data>
        <data id="3">Numeric: &#65;&#x42;&#x43;</data>
        <data id="4"><![CDATA[Raw <tags> & "quotes" here]]></data>
    </root>"""
    root = safe_ET.fromstring(xml)

    assert root[0].text == "Tom & Jerry <3"
    assert root[1].text == "Quotes: \"hello\" and 'world'"
    assert root[2].text == "Numeric: ABC"
    assert root[3].text == 'Raw <tags> & "quotes" here'


def test_text_and_tail() -> None:
    """Element.text and Element.tail semantics must be preserved."""
    xml = "<root>Leading text<child>Child text</child>Trailing tail text</root>"
    root = safe_ET.fromstring(xml)

    assert root.text == "Leading text"
    assert root[0].tag == "child"
    assert root[0].text == "Child text"
    assert root[0].tail == "Trailing tail text"


def test_parse_and_getroot(xml_simple: str) -> None:
    """safe_ET.parse() must return an ElementTree whose getroot() is the root Element."""
    tree = safe_ET.parse(io.StringIO(xml_simple))
    assert isinstance(tree, safe_ET.ElementTree)
    root = tree.getroot()
    assert isinstance(root, std_ET.Element)
    assert root.tag == "catalog"


def test_iterparse_events(xml_simple: str) -> None:
    """safe_ET.iterparse() must produce (event, elem) sequence."""
    events = list(safe_ET.iterparse(io.StringIO(xml_simple), events=("start", "end")))
    assert len(events) > 0

    first_event, first_elem = events[0]
    assert first_event == "start"
    assert first_elem.tag == "catalog"

    last_event, last_elem = events[-1]
    assert last_event == "end"
    assert last_elem.tag == "catalog"


def test_xml_alias(xml_simple: str) -> None:
    """safe_ET.XML() must behave identically to safe_ET.fromstring()."""
    root1 = safe_ET.fromstring(xml_simple)
    root2 = safe_ET.XML(xml_simple)
    assert root1.tag == root2.tag
    assert len(root1) == len(root2)


def test_elementtree_instance_parse(tmp_path: any, xml_simple: str) -> None:
    """safe_ET.ElementTree.parse() instance method must parse into self and return root."""
    file_path = tmp_path / "test_instance.xml"
    file_path.write_text(xml_simple, encoding="utf-8")

    tree = safe_ET.ElementTree()
    root = tree.parse(str(file_path))
    assert root.tag == "catalog"
    assert tree.getroot() is root

    # Also test passing Path directly
    tree2 = safe_ET.ElementTree()
    root2 = tree2.parse(file_path)
    assert root2.tag == "catalog"


def test_parse_invalid_source_type() -> None:
    """parse() with invalid object must raise TypeError."""
    import pytest

    with pytest.raises(TypeError, match="Invalid source type"):
        safe_ET.parse(12345)  # type: ignore[arg-type]


def test_iterparse_event_filters(xml_simple: str) -> None:
    """Iterparse with only 'start' or only 'end' events."""
    starts = list(safe_ET.iterparse(io.StringIO(xml_simple), events=("start",)))
    assert all(ev == "start" for ev, _ in starts)
    assert len(starts) > 0

    ends = list(safe_ET.iterparse(io.StringIO(xml_simple), events=("end",)))
    assert all(ev == "end" for ev, _ in ends)
    assert len(ends) > 0

    defaults = list(safe_ET.iterparse(io.StringIO(xml_simple)))
    assert all(ev == "end" for ev, _ in defaults)


def test_exception_representations_and_fields() -> None:
    """All exception reprs and attributes must format correctly without crashing."""
    from safexml.common import (
        DefusedXmlException,
        DTDForbidden,
        EntitiesForbidden,
        ExternalReferenceForbidden,
        NotSupportedError,
        ParseError,
    )

    base = DefusedXmlException("custom message")
    assert repr(base) == "DefusedXmlException('custom message')"
    assert base.args == ("custom message",)

    dtd = DTDForbidden("root", sysid="http://example.com/test.dtd", pubid=None)
    assert (
        repr(dtd)
        == "DTDForbidden(name='root', system_id='http://example.com/test.dtd', public_id=None)"
    )
    assert dtd.name == "root"
    assert dtd.sysid == "http://example.com/test.dtd"
    assert dtd.pubid is None

    ent = EntitiesForbidden("evil", sysid=None, pubid=None)
    assert "EntitiesForbidden(name='evil'" in repr(ent)
    assert ent.name == "evil"

    ext = ExternalReferenceForbidden(sysid="file:///etc/passwd", pubid=None)
    assert repr(ext) == "ExternalReferenceForbidden(system_id='file:///etc/passwd', public_id=None)"
    assert ext.sysid == "file:///etc/passwd"

    err = ParseError("syntax error")
    assert repr(err) == "ParseError('syntax error')"
    assert str(err) == "syntax error"
    assert issubclass(ParseError, std_ET.ParseError)
    assert issubclass(NotSupportedError, DefusedXmlException)
    assert issubclass(ParseError, DefusedXmlException)


def test_xmlparser_lifecycle_and_defusedxmlparser_alias() -> None:
    """XMLParser supports feed()/close() for strings and bytes, enforces limits, and aliases DefusedXMLParser."""
    import pytest

    from safexml.common import EntitiesForbidden, ParseError

    assert safe_ET.DefusedXMLParser is safe_ET.XMLParser

    # Feed string
    parser = safe_ET.XMLParser()
    parser.feed("<root>")
    parser.feed("<item>hello</item>")
    parser.feed("</root>")
    root = parser.close()
    assert root.tag == "root"
    assert root[0].text == "hello"

    # Feed bytes
    parser_bytes = safe_ET.XMLParser()
    parser_bytes.feed(b"<catalog>")
    parser_bytes.feed(b"<item>data</item>")
    parser_bytes.feed(b"</catalog>")
    root_b = parser_bytes.close()
    assert root_b.tag == "catalog"
    assert root_b[0].text == "data"

    # Close with no data
    empty_parser = safe_ET.XMLParser()
    with pytest.raises(ParseError, match="No XML root element"):
        empty_parser.close()

    # Security enforcement via XMLParser
    sec_parser = safe_ET.XMLParser()
    sec_parser.feed('<!DOCTYPE bomb [<!ENTITY a "123">]><bomb>&a;</bomb>')
    with pytest.raises(EntitiesForbidden):
        sec_parser.close()


def test_iterparse_root_property() -> None:
    """Iterparse provides .root property pointing to the document root element."""
    xml = "<catalog><book id='1'>Text</book></catalog>"
    it = safe_ET.iterparse(io.StringIO(xml))
    assert hasattr(it, "root")
    assert it.root.tag == "catalog"
    events = list(it)
    assert len(events) == 2


def test_character_encoding_support() -> None:
    """Parser decodes declared ISO-8859-1 and UTF-16 encodings correctly."""
    # ISO-8859-1
    iso_xml = b'<?xml version="1.0" encoding="ISO-8859-1"?><doc>\xe9l\xe9phant</doc>'
    root_iso = safe_ET.fromstring(iso_xml)
    assert root_iso.tag == "doc"
    assert root_iso.text == "\u00e9l\u00e9phant"

    # UTF-16 with BOM
    utf16_xml = '<?xml version="1.0" encoding="utf-16"?><msg>hello</msg>'.encode("utf-16")
    root_u16 = safe_ET.fromstring(utf16_xml)
    assert root_u16.tag == "msg"
    assert root_u16.text == "hello"


def test_dtd_default_attributes_application() -> None:
    """DTD ATTLIST default attributes are applied when not explicitly specified on elements."""
    xml = '<!DOCTYPE r [<!ATTLIST r role CDATA "guest" status CDATA "active">]><r status="admin"/>'
    root = safe_ET.fromstring(xml)
    assert root.attrib["role"] == "guest"
    assert root.attrib["status"] == "admin"
