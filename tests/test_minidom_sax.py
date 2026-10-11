"""Tests for safexml.minidom and safexml.sax drop-in replacement functionality."""

from __future__ import annotations

import io
import xml.sax as std_sax
from pathlib import Path
from xml.dom import minidom as std_minidom
from xml.etree import ElementTree as std_ET
from xml.sax import (
    ContentHandler,
    ErrorHandler,
    InputSource,
    saxutils,
)

import pytest

import safexml
from safexml import minidom, sax
from safexml.common import (
    DefusedXmlException,
    DTDForbidden,
    EntitiesForbidden,
)


class LoggingContentHandler(ContentHandler):
    """Recorder for SAX events."""

    def __init__(self) -> None:
        super().__init__()
        self.events: list[tuple[str, ...]] = []

    def startDocument(self) -> None:
        self.events.append(("startDocument",))

    def endDocument(self) -> None:
        self.events.append(("endDocument",))

    def startElement(self, name: str, attrs: saxutils.xmlreader.AttributesImpl) -> None:
        self.events.append(("startElement", name, dict(attrs)))

    def endElement(self, name: str) -> None:
        self.events.append(("endElement", name))

    def characters(self, content: str) -> None:
        self.events.append(("characters", content))


def test_minidom_parse_string() -> None:
    """safexml.minidom.parseString parses safe XML into a standard minidom Document."""
    doc = minidom.parseString("<root><item id='1'>hello</item>tail<empty/></root>")
    assert isinstance(doc, minidom.Document)
    assert isinstance(doc, std_minidom.Document)
    assert doc.documentElement.tagName == "root"
    child = doc.documentElement.firstChild
    assert child.getAttribute("id") == "1"
    assert child.firstChild.data == "hello"
    assert doc.documentElement.childNodes[1].data == "tail"
    assert doc.documentElement.childNodes[2].tagName == "empty"

    # Bytes input
    doc_bytes = minidom.parseString(b"<data key='val'>sample</data>", parser=None)
    assert doc_bytes.documentElement.tagName == "data"
    assert doc_bytes.documentElement.getAttribute("key") == "val"


def test_minidom_parse_file_and_stream(tmp_path: Path) -> None:
    """safexml.minidom.parse works with file path and file-like stream objects."""
    xml_content = "<config><setting name='debug'>true</setting></config>"
    xml_file = tmp_path / "test.xml"
    xml_file.write_text(xml_content, encoding="utf-8")

    # Path string
    doc_file = minidom.parse(str(xml_file))
    assert doc_file.documentElement.tagName == "config"

    # BytesIO stream
    stream = io.BytesIO(xml_content.encode("utf-8"))
    doc_stream = minidom.parse(stream, bufsize=1024)
    assert doc_stream.documentElement.tagName == "config"


def test_minidom_security_enforcement() -> None:
    """safexml.minidom blocks XML attacks (billion laughs, DTD, size limits)."""
    billion_laughs = """<?xml version="1.0"?>
    <!DOCTYPE lolz [
      <!ENTITY lol "lol">
      <!ENTITY lol2 "&lol;&lol;">
    ]>
    <lolz>&lol2;</lolz>
    """
    with pytest.raises(EntitiesForbidden):
        minidom.parseString(billion_laughs)

    with pytest.raises(DTDForbidden):
        minidom.parseString("<!DOCTYPE root><root/>", forbid_dtd=True)

    with pytest.raises(DefusedXmlException, match="input exceeded maximum size limit"):
        minidom.parseString("<root>too long</root>", max_input_size=5)

    with pytest.raises(DefusedXmlException, match="element count limit"):
        minidom.parseString("<root><a/><b/></root>", max_elements=1)


def test_sax_parse_string() -> None:
    """safexml.sax.parseString safely drives a SAX ContentHandler."""
    xml_str = "<catalog><book id='b1'>Text 1</book>Tail text<book id='b2'>Text 2</book></catalog>"
    handler = LoggingContentHandler()
    sax.parseString(xml_str, handler)

    assert ("startDocument",) in handler.events
    assert ("endDocument",) in handler.events
    assert ("startElement", "catalog", {}) in handler.events
    assert ("startElement", "book", {"id": "b1"}) in handler.events
    assert ("characters", "Text 1") in handler.events
    assert ("characters", "Tail text") in handler.events
    assert ("endElement", "book") in handler.events
    assert ("endElement", "catalog") in handler.events

    # Bytes input
    handler_bytes = LoggingContentHandler()
    sax.parseString(b"<node>content</node>", handler_bytes)
    assert ("startElement", "node", {}) in handler_bytes.events


def test_sax_parse_sources_and_inputsource(tmp_path: Path) -> None:
    """safexml.sax.parse handles file-like streams, file paths, and InputSource variants."""
    xml_content = "<root><child>value</child></root>"
    xml_file = tmp_path / "sax_test.xml"
    xml_file.write_text(xml_content, encoding="utf-8")

    # 1. File path
    h1 = LoggingContentHandler()
    sax.parse(str(xml_file), h1)
    assert ("startElement", "root", {}) in h1.events

    # 2. BytesIO stream
    h2 = LoggingContentHandler()
    sax.parse(io.BytesIO(xml_content.encode("utf-8")), h2)
    assert ("startElement", "root", {}) in h2.events

    # 3. InputSource with ByteStream
    src_bytes = InputSource()
    src_bytes.setByteStream(io.BytesIO(xml_content.encode("utf-8")))
    h3 = LoggingContentHandler()
    sax.parse(src_bytes, h3)
    assert ("startElement", "root", {}) in h3.events

    # 4. InputSource with CharacterStream
    src_char = InputSource()
    src_char.setCharacterStream(io.StringIO(xml_content))
    h4 = LoggingContentHandler()
    sax.parse(src_char, h4)
    assert ("startElement", "root", {}) in h4.events

    # 5. InputSource with SystemId (file path)
    src_sys = InputSource()
    src_sys.setSystemId(str(xml_file))
    h5 = LoggingContentHandler()
    sax.parse(src_sys, h5)
    assert ("startElement", "root", {}) in h5.events


def test_sax_parser_lifecycle_and_handlers() -> None:
    """SafeXMLParser conforms to XMLReader handler setters and getters."""
    parser = sax.make_parser(["dummy"])
    assert isinstance(parser, sax.SafeXMLParser)

    ch = ContentHandler()
    eh = ErrorHandler()
    parser.setContentHandler(ch)
    assert parser.getContentHandler() is ch

    parser.setErrorHandler(eh)
    assert parser.getErrorHandler() is eh

    # Test parse with explicit error handler
    h = LoggingContentHandler()
    sax.parse(io.StringIO("<root/>"), h, errorHandler=eh)
    assert ("startElement", "root", {}) in h.events


def test_sax_security_enforcement() -> None:
    """safexml.sax rejects entity attacks and resource limits."""
    billion_laughs = """<?xml version="1.0"?>
    <!DOCTYPE lolz [
      <!ENTITY lol "lol">
      <!ENTITY lol2 "&lol;&lol;">
    ]>
    <lolz>&lol2;</lolz>
    """
    h = LoggingContentHandler()
    with pytest.raises(EntitiesForbidden):
        sax.parseString(billion_laughs, h)

    with pytest.raises(DTDForbidden):
        sax.parseString("<!DOCTYPE root><root/>", h, forbid_dtd=True)

    with pytest.raises(DefusedXmlException, match="input exceeded maximum size limit"):
        sax.parseString("<root>long</root>", h, max_input_size=3)

    with pytest.raises(DefusedXmlException, match="element count limit"):
        sax.parseString("<root><x/></root>", h, max_elements=1)


def test_defuse_stdlib_full_mapping() -> None:
    """safexml.defuse_stdlib patches ElementTree, minidom, and sax, and returns a dictionary."""
    orig_et_fromstring = std_ET.fromstring
    orig_et_parse = std_ET.parse
    orig_et_iterparse = std_ET.iterparse
    orig_et_XML = std_ET.XML
    orig_et_XMLParser = std_ET.XMLParser
    orig_et_fromstringlist = getattr(std_ET, "fromstringlist", None)
    orig_et_ElementTree_parse = std_ET.ElementTree.parse
    orig_minidom_parse = std_minidom.parse
    orig_minidom_parsestr = std_minidom.parseString
    orig_sax_parse = std_sax.parse
    orig_sax_parsestr = std_sax.parseString
    orig_sax_make = std_sax.make_parser

    try:
        patched = safexml.defuse_stdlib()
        assert "xml.etree.ElementTree" in patched
        assert "xml.dom.minidom" in patched
        assert "xml.sax" in patched

        # Verify minidom is defused
        with pytest.raises(EntitiesForbidden):
            std_minidom.parseString('<!DOCTYPE bomb [<!ENTITY a "123">]><bomb>&a;</bomb>')

        # Verify sax is defused
        h = LoggingContentHandler()
        with pytest.raises(EntitiesForbidden):
            std_sax.parseString('<!DOCTYPE bomb [<!ENTITY a "123">]><bomb>&a;</bomb>', h)

        # Verify normal parsing still succeeds through defused stdlib
        doc = std_minidom.parseString("<root><elem>val</elem></root>")
        assert doc.documentElement.tagName == "root"

        h_normal = LoggingContentHandler()
        std_sax.parseString("<root><elem>val</elem></root>", h_normal)
        assert ("startElement", "root", {}) in h_normal.events

        p = std_sax.make_parser()
        assert isinstance(p, sax.SafeXMLParser)

    finally:
        std_ET.fromstring = orig_et_fromstring
        std_ET.parse = orig_et_parse
        std_ET.iterparse = orig_et_iterparse
        std_ET.XML = orig_et_XML
        std_ET.XMLParser = orig_et_XMLParser
        if orig_et_fromstringlist is not None:
            std_ET.fromstringlist = orig_et_fromstringlist
        std_ET.ElementTree.parse = orig_et_ElementTree_parse
        std_minidom.parse = orig_minidom_parse
        std_minidom.parseString = orig_minidom_parsestr
        std_sax.parse = orig_sax_parse
        std_sax.parseString = orig_sax_parsestr
        std_sax.make_parser = orig_sax_make
