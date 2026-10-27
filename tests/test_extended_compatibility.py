"""Tests verifying standard library compatibility, formatting, and developer ergonomics."""

from __future__ import annotations

import pathlib
import xml.etree.ElementTree as std_ET

import pytest

import safexml
import safexml.ElementTree as ET
from safexml.common import (
    DTDForbidden,
    EntitiesForbidden,
    ExternalReferenceForbidden,
)


def test_exception_traceback_and_args_formatting() -> None:
    """Exception classes must populate .args properly for structured logging and traceback formatters."""
    exc1 = DTDForbidden(name="root", sysid="http://example.com/test.dtd", pubid=None)
    assert len(exc1.args) > 0
    assert "DTDForbidden" in str(exc1)
    assert "DTDForbidden" in repr(exc1)

    exc2 = EntitiesForbidden(name="evil", sysid=None, pubid=None)
    assert len(exc2.args) > 0
    assert "EntitiesForbidden" in str(exc2)
    assert "EntitiesForbidden" in repr(exc2)

    exc3 = ExternalReferenceForbidden(sysid="file:///etc/passwd", pubid=None)
    assert len(exc3.args) > 0
    assert "ExternalReferenceForbidden" in str(exc3)
    assert "ExternalReferenceForbidden" in repr(exc3)


def test_elementtree_indent_support() -> None:
    """safexml.ElementTree must provide and re-export `indent()` matching modern stdlib API."""
    assert hasattr(ET, "indent")
    assert hasattr(safexml, "indent")

    root = ET.fromstring("<root><child1/><child2><subchild/></child2></root>")
    ET.indent(root, space="  ")
    serialized = ET.tostring(root, encoding="unicode")
    assert "  <child1 />" in serialized or "  <child1/>" in serialized
    assert "    <subchild />" in serialized or "    <subchild/>" in serialized


def test_element_class_reexport() -> None:
    """`Element` must be directly importable from `safexml.ElementTree` and top-level `safexml`."""
    assert hasattr(ET, "Element")
    assert hasattr(safexml, "Element")

    elem = ET.Element("test", {"attr": "val"})
    assert isinstance(elem, std_ET.Element)
    assert elem.tag == "test"
    assert elem.attrib["attr"] == "val"


def test_register_namespace_support() -> None:
    """`register_namespace` must be available in `safexml.ElementTree` and top-level `safexml`."""
    assert hasattr(ET, "register_namespace")
    assert hasattr(safexml, "register_namespace")

    # Calling register_namespace should register without error
    ET.register_namespace("custom", "http://example.com/custom")


def test_fromstring_parser_keyword_argument() -> None:
    """`fromstring()` must accept `parser=` parameter for standard library signature parity."""
    root = ET.fromstring("<root><item/></root>", parser=None)
    assert root.tag == "root"


def test_pep561_py_typed_marker() -> None:
    """Package must include PEP 561 `py.typed` marker and `_safexml.pyi` stub for static type checkers."""
    import mypy.api

    safexml_pkg = pathlib.Path(safexml.__file__).parent
    py_typed = safexml_pkg / "py.typed"
    stub_file = safexml_pkg / "_safexml.pyi"
    assert py_typed.is_file(), f"Missing PEP 561 marker at {py_typed}"
    assert stub_file.is_file(), f"Missing type stub at {stub_file}"

    stdout, stderr, exit_code = mypy.api.run(["--strict", str(safexml_pkg)])
    assert exit_code == 0, f"mypy --strict failed:\n{stdout}\n{stderr}"


def test_multi_attribute_and_enumerated_attlist_defaults() -> None:
    """DOCTYPE ATTLIST must support multiple attribute definitions, enumerated types, and default xmlns."""
    xml = (
        "<!DOCTYPE root [\n"
        "  <!ATTLIST root\n"
        '    xmlns CDATA "urn:test"\n'
        '    mode (fast | safe) "safe"\n'
        '    version CDATA #FIXED "1.0"\n'
        "    optional CDATA #IMPLIED\n"
        '    extra CDATA "ok">\n'
        "]>\n"
        "<root/>"
    )
    root = ET.fromstring(xml)
    assert root.tag == "{urn:test}root"
    assert root.attrib["mode"] == "safe"
    assert root.attrib["version"] == "1.0"
    assert root.attrib["extra"] == "ok"
    assert "optional" not in root.attrib


def test_encoding_declaration_whitespace_around_equals() -> None:
    """XML declaration with whitespace around '=' in encoding attribute must be detected properly."""
    raw = b'<?xml version = "1.0" encoding = "ISO-8859-1"?><r>caf\xe9</r>'
    root = ET.fromstring(raw)
    assert root.text == "café"


def test_doctype_casing_ignores_comments_and_pis() -> None:
    """Lowercase '<!doctype' inside comments or PIs must not trigger false-positive casing errors."""
    xml = "<!-- <!doctype html> --><?pi <!doctype html>?><!DOCTYPE r><r><!-- <!doctype x> --></r>"
    root = ET.fromstring(xml)
    assert root.tag == "r"


def test_doctype_brackets_in_system_literal() -> None:
    """Brackets inside quoted SYSTEM/PUBLIC literals must not be mistaken for an internal subset."""
    xml = '<!DOCTYPE r SYSTEM "http://example.com/dtd[1].dtd"><r/>'
    root = ET.fromstring(xml, forbid_external=False)
    assert root.tag == "r"


def test_fromstringlist_support() -> None:
    """`fromstringlist()` parses sequence of string or bytes fragments and enforces security."""
    from safexml.common import ParseError

    # Empty sequence
    with pytest.raises(ParseError, match="No XML root element"):
        safexml.fromstringlist([])

    # String sequence
    root_str = safexml.fromstringlist(["<root>", "<item id='1'>test</item>", "</root>"])
    assert root_str.tag == "root"
    assert root_str[0].text == "test"

    # Bytes sequence
    root_bytes = safexml.fromstringlist([b"<root>", b"<item id='2'>bytes</item>", b"</root>"])
    assert root_bytes.tag == "root"
    assert root_bytes[0].attrib["id"] == "2"

    # Security enforcement
    with pytest.raises(EntitiesForbidden):
        safexml.fromstringlist(['<!DOCTYPE bomb [<!ENTITY a "123">]><bomb>&a;</bomb>'])


def test_defuse_stdlib_interoperability() -> None:
    """`defuse_stdlib()` must safely protect standard library XML parsing functions without breaking class identity."""
    import io

    orig_fromstring = std_ET.fromstring
    orig_parse = std_ET.parse
    orig_iterparse = std_ET.iterparse
    orig_xml = std_ET.XML
    orig_xmlparser = std_ET.XMLParser
    orig_fromstringlist = getattr(std_ET, "fromstringlist", None)
    orig_et_parse = std_ET.ElementTree.parse

    try:
        safexml.defuse_stdlib()
        # Verify stdlib fromstring now blocks entities
        with pytest.raises(EntitiesForbidden):
            std_ET.fromstring('<!DOCTYPE bomb [<!ENTITY a "123">]><bomb>&a;</bomb>')

        # Verify stdlib fromstringlist now blocks entities
        with pytest.raises(EntitiesForbidden):
            std_ET.fromstringlist(['<!DOCTYPE bomb [<!ENTITY a "123">]><bomb>&a;</bomb>'])

        # Verify stdlib ElementTree().parse() works on valid XML and blocks entities
        tree = std_ET.ElementTree()
        safe_root = tree.parse(io.StringIO("<root><item/></root>"))
        assert safe_root.tag == "root"
        assert tree.getroot() is safe_root

        with pytest.raises(EntitiesForbidden):
            tree.parse(io.StringIO('<!DOCTYPE bomb [<!ENTITY a "123">]><bomb>&a;</bomb>'))

        # Verify stdlib XMLParser() blocks entities
        parser = std_ET.XMLParser()
        parser.feed('<!DOCTYPE bomb [<!ENTITY a "123">]><bomb>&a;</bomb>')
        with pytest.raises(EntitiesForbidden):
            parser.close()
    finally:
        std_ET.fromstring = orig_fromstring
        std_ET.parse = orig_parse
        std_ET.iterparse = orig_iterparse
        std_ET.XML = orig_xml
        std_ET.XMLParser = orig_xmlparser
        if orig_fromstringlist is not None:
            std_ET.fromstringlist = orig_fromstringlist
        std_ET.ElementTree.parse = orig_et_parse
