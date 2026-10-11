"""safexml.minidom: Secure drop-in replacement for xml.dom.minidom and defusedxml.minidom."""

from __future__ import annotations

import os
from typing import IO, Any
from xml.dom import minidom as _stdlib_minidom
from xml.etree import ElementTree as _stdlib_etree

from safexml import ElementTree as _safexml_etree

Document = _stdlib_minidom.Document
Node = _stdlib_minidom.Node
Element = _stdlib_minidom.Element

# Retain references to original stdlib implementations to avoid recursion when monkey-patched.
_orig_minidom_parse = _stdlib_minidom.parse
_orig_minidom_parseString = _stdlib_minidom.parseString


def parse(
    file: str | bytes | os.PathLike[Any] | IO[Any],
    parser: Any | None = None,
    bufsize: int | None = None,
    forbid_dtd: bool = False,
    forbid_entities: bool = True,
    forbid_external: bool = True,
    max_depth: int = 1000,
    max_elements: int = 5_000_000,
    max_input_size: int = 256 * 1024 * 1024,
) -> _stdlib_minidom.Document:
    """Parse a file or stream into a minidom Document with SafeXML security protections."""
    tree = _safexml_etree.parse(
        file,
        parser=parser,
        forbid_dtd=forbid_dtd,
        forbid_entities=forbid_entities,
        forbid_external=forbid_external,
        max_depth=max_depth,
        max_elements=max_elements,
        max_input_size=max_input_size,
    )
    root = tree.getroot()
    xml_bytes = _stdlib_etree.tostring(root, encoding="utf-8")
    return _orig_minidom_parseString(xml_bytes)


def parseString(
    string: str | bytes,
    parser: Any | None = None,
    forbid_dtd: bool = False,
    forbid_entities: bool = True,
    forbid_external: bool = True,
    max_depth: int = 1000,
    max_elements: int = 5_000_000,
    max_input_size: int = 256 * 1024 * 1024,
) -> _stdlib_minidom.Document:
    """Parse an XML string or bytes into a minidom Document with SafeXML security protections."""
    root = _safexml_etree.fromstring(
        string,
        parser=parser,
        forbid_dtd=forbid_dtd,
        forbid_entities=forbid_entities,
        forbid_external=forbid_external,
        max_depth=max_depth,
        max_elements=max_elements,
        max_input_size=max_input_size,
    )
    xml_bytes = _stdlib_etree.tostring(root, encoding="utf-8")
    return _orig_minidom_parseString(xml_bytes)


__all__ = [
    "Document",
    "Element",
    "Node",
    "parse",
    "parseString",
]
