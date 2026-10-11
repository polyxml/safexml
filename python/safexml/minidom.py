"""safexml.minidom: Secure drop-in replacement for xml.dom.minidom and defusedxml.minidom."""

from __future__ import annotations

import os
from collections import deque
from typing import IO, Any
from xml.dom import minidom as _stdlib_minidom

from safexml import ElementTree as _safexml_etree

Document = _stdlib_minidom.Document
Node = _stdlib_minidom.Node
Element = _stdlib_minidom.Element


def _etree_to_minidom(root: _safexml_etree.Element) -> _stdlib_minidom.Document:
    doc = _stdlib_minidom.Document()
    doc_root = doc.createElement(root.tag)
    for k, v in root.attrib.items():
        doc_root.setAttribute(k, v)
    if root.text:
        doc_root.appendChild(doc.createTextNode(root.text))
    doc.appendChild(doc_root)

    queue: deque[tuple[_safexml_etree.Element, _stdlib_minidom.Element]] = deque([(root, doc_root)])
    while queue:
        parent_etree, parent_dom = queue.popleft()
        for child in parent_etree:
            child_dom = doc.createElement(child.tag)
            for k, v in child.attrib.items():
                child_dom.setAttribute(k, v)
            if child.text:
                child_dom.appendChild(doc.createTextNode(child.text))
            parent_dom.appendChild(child_dom)
            if child.tail:
                parent_dom.appendChild(doc.createTextNode(child.tail))
            queue.append((child, child_dom))

    return doc


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
    return _etree_to_minidom(tree.getroot())


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
    return _etree_to_minidom(root)


__all__ = [
    "Document",
    "Element",
    "Node",
    "parse",
    "parseString",
]
