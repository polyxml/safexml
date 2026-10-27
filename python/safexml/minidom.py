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
    max_entity_size: int = 10 * 1024 * 1024,
    max_text_size: int = 100 * 1024 * 1024,
    max_attributes: int = 1000,
    max_attribute_size: int = 10 * 1024 * 1024,
    max_name_size: int = 1024,
    max_comment_size: int = 10 * 1024 * 1024,
    max_elements: int = 5_000_000,
    max_input_size: int = 256 * 1024 * 1024,
) -> _stdlib_minidom.Document:
    """Parse a file or stream into a minidom `Document` with SafeXML security protections.

    Args:
        file: File path or file-like stream containing XML data.
        parser: Optional parser instance (retained for stdlib compatibility).
        bufsize: Optional buffer size parameter (retained for stdlib compatibility).
        forbid_dtd: Disallow `<!DOCTYPE ...>` declarations.
        forbid_entities: Disallow `<!ENTITY ...>` declarations and custom entity references.
        forbid_external: Disallow external `SYSTEM` and `PUBLIC` references.
        max_depth: Maximum allowed element nesting depth.
        max_entity_size: Maximum size in bytes of an entity value.
        max_text_size: Maximum accumulated text and synthesized attribute size in bytes.
        max_attributes: Maximum number of attributes per element.
        max_attribute_size: Maximum size in bytes of a single attribute value.
        max_name_size: Maximum length in bytes of an XML element or attribute name.
        max_comment_size: Maximum size in bytes of a comment or processing instruction.
        max_elements: Maximum total number of elements in the document.
        max_input_size: Maximum size in bytes of the raw input document.

    Returns:
        A `xml.dom.minidom.Document` instance.
    """
    tree = _safexml_etree.parse(
        file,
        parser=parser,
        forbid_dtd=forbid_dtd,
        forbid_entities=forbid_entities,
        forbid_external=forbid_external,
        max_depth=max_depth,
        max_entity_size=max_entity_size,
        max_text_size=max_text_size,
        max_attributes=max_attributes,
        max_attribute_size=max_attribute_size,
        max_name_size=max_name_size,
        max_comment_size=max_comment_size,
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
    max_entity_size: int = 10 * 1024 * 1024,
    max_text_size: int = 100 * 1024 * 1024,
    max_attributes: int = 1000,
    max_attribute_size: int = 10 * 1024 * 1024,
    max_name_size: int = 1024,
    max_comment_size: int = 10 * 1024 * 1024,
    max_elements: int = 5_000_000,
    max_input_size: int = 256 * 1024 * 1024,
) -> _stdlib_minidom.Document:
    """Parse an XML string or bytes into a minidom `Document` with SafeXML security protections.

    Args:
        string: XML document string or byte sequence.
        parser: Optional parser instance (retained for stdlib compatibility).
        forbid_dtd: Disallow `<!DOCTYPE ...>` declarations.
        forbid_entities: Disallow `<!ENTITY ...>` declarations and custom entity references.
        forbid_external: Disallow external `SYSTEM` and `PUBLIC` references.
        max_depth: Maximum allowed element nesting depth.
        max_entity_size: Maximum size in bytes of an entity value.
        max_text_size: Maximum accumulated text and synthesized attribute size in bytes.
        max_attributes: Maximum number of attributes per element.
        max_attribute_size: Maximum size in bytes of a single attribute value.
        max_name_size: Maximum length in bytes of an XML element or attribute name.
        max_comment_size: Maximum size in bytes of a comment or processing instruction.
        max_elements: Maximum total number of elements in the document.
        max_input_size: Maximum size in bytes of the raw input document.

    Returns:
        A `xml.dom.minidom.Document` instance.
    """
    root = _safexml_etree.fromstring(
        string,
        parser=parser,
        forbid_dtd=forbid_dtd,
        forbid_entities=forbid_entities,
        forbid_external=forbid_external,
        max_depth=max_depth,
        max_entity_size=max_entity_size,
        max_text_size=max_text_size,
        max_attributes=max_attributes,
        max_attribute_size=max_attribute_size,
        max_name_size=max_name_size,
        max_comment_size=max_comment_size,
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
