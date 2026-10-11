"""Tests verifying direct fixes for known upstream defusedxml issues.

Resolves:
- tiran/defusedxml#105: Exception formatting compatible with `rich` tracebacks.
- tiran/defusedxml#104: PEP 561 py.typed marker and type annotations.
- tiran/defusedxml#87: Missing `ElementTree.indent()` function.
- tiran/defusedxml#80: Missing `Element` class export.
- tiran/defusedxml#79: Missing `register_namespace()` method.
- tiran/defusedxml#78: `fromstring()` does not accept `parser` argument.
- tiran/defusedxml#76, #77, #88: Safe `defuse_stdlib()` without breaking 3rd-party libs.
"""

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


def test_fix_issue_105_rich_exception_formatting() -> None:
    """Exception classes must populate .args properly so rich traceback printing does not crash.

    References: tiran/defusedxml#105
    """
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


def test_fix_issue_87_indent_support() -> None:
    """safexml.ElementTree must provide and re-export `indent()`.

    References: tiran/defusedxml#87
    """
    assert hasattr(ET, "indent")
    assert hasattr(safexml, "indent")

    root = ET.fromstring("<root><child1/><child2><subchild/></child2></root>")
    ET.indent(root, space="  ")
    serialized = ET.tostring(root, encoding="unicode")
    assert "  <child1 />" in serialized or "  <child1/>" in serialized
    assert "    <subchild />" in serialized or "    <subchild/>" in serialized


def test_fix_issue_80_element_class_export() -> None:
    """`Element` must be directly importable from `safexml.ElementTree` and `safexml`.

    References: tiran/defusedxml#80
    """
    assert hasattr(ET, "Element")
    assert hasattr(safexml, "Element")

    elem = ET.Element("test", {"attr": "val"})
    assert isinstance(elem, std_ET.Element)
    assert elem.tag == "test"
    assert elem.attrib["attr"] == "val"


def test_fix_issue_79_register_namespace() -> None:
    """`register_namespace` must be available in `safexml.ElementTree` and `safexml`.

    References: tiran/defusedxml#79
    """
    assert hasattr(ET, "register_namespace")
    assert hasattr(safexml, "register_namespace")

    # Calling register_namespace should not raise
    ET.register_namespace("custom", "http://example.com/custom")


def test_fix_issue_78_fromstring_parser_kwarg() -> None:
    """`fromstring()` must accept `parser=` parameter for standard library signature parity.

    References: tiran/defusedxml#78
    """
    # In stdlib ElementTree: fromstring(text, parser=None)
    # defusedxml broke when callers passed parser=None
    root = ET.fromstring("<root><item/></root>", parser=None)
    assert root.tag == "root"


def test_fix_issue_104_py_typed_marker() -> None:
    """Package must include PEP 561 `py.typed` marker for type checkers (mypy/pyright).

    References: tiran/defusedxml#104
    """
    safexml_pkg = pathlib.Path(safexml.__file__).parent
    py_typed = safexml_pkg / "py.typed"
    assert py_typed.is_file(), f"Missing PEP 561 marker at {py_typed}"


def test_fix_defuse_stdlib_safety() -> None:
    """`defuse_stdlib()` must safely patch stdlib functions without breaking class identity.

    References: tiran/defusedxml#76, #77, #88
    """
    # Save original references
    orig_fromstring = std_ET.fromstring
    try:
        safexml.defuse_stdlib()
        # Verify stdlib fromstring now blocks entities
        with pytest.raises(EntitiesForbidden):
            std_ET.fromstring('<!DOCTYPE bomb [<!ENTITY a "123">]><bomb>&a;</bomb>')
    finally:
        std_ET.fromstring = orig_fromstring
