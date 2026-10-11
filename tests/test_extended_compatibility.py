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
    """Package must include PEP 561 `py.typed` marker for static type checkers (mypy/pyright)."""
    safexml_pkg = pathlib.Path(safexml.__file__).parent
    py_typed = safexml_pkg / "py.typed"
    assert py_typed.is_file(), f"Missing PEP 561 marker at {py_typed}"


def test_defuse_stdlib_interoperability() -> None:
    """`defuse_stdlib()` must safely protect standard library XML parsing functions without breaking class identity."""
    orig_fromstring = std_ET.fromstring
    try:
        safexml.defuse_stdlib()
        # Verify stdlib fromstring now blocks entities
        with pytest.raises(EntitiesForbidden):
            std_ET.fromstring('<!DOCTYPE bomb [<!ENTITY a "123">]><bomb>&a;</bomb>')
    finally:
        std_ET.fromstring = orig_fromstring
