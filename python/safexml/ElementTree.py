"""Drop-in defused XML parser and modern ElementTree implementation.

Compatible with `defusedxml.ElementTree` and `xml.etree.ElementTree`.
Powered by Rust (`quick-xml`) with GIL release and strict entity/DoS defense.

Resolves legacy defusedxml issues:
- tiran/defusedxml#78: `fromstring()` supports `parser` keyword argument.
- tiran/defusedxml#79: Exposes `register_namespace()`.
- tiran/defusedxml#80: Exposes `Element` class.
- tiran/defusedxml#87: Exposes `indent()` for pretty-printing.
- tiran/defusedxml#104: Comprehensive type annotations and PEP 561 marker.
- tiran/defusedxml#105: Exception tracebacks compatible with `rich`.
"""

from __future__ import annotations

import os
from collections.abc import Iterator
from typing import IO, Any
from xml.etree.ElementTree import (
    PI,
    Comment,
    Element,
    ProcessingInstruction,
    QName,
    SubElement,
    TreeBuilder,
    XMLParser,
    canonicalize,
    dump,
    indent,
    register_namespace,
    tostring,
    tostringlist,
)
from xml.etree.ElementTree import (
    ElementTree as _StdlibElementTree,
)

from safexml._safexml import parse_xml as _parse_xml
from safexml.common import (
    DefusedXmlException,
    DTDForbidden,
    EntitiesForbidden,
    ExternalReferenceForbidden,
    NotSupportedError,
    ParseError,
)

# Standard alias
XMLParse = ParseError


class ElementTree(_StdlibElementTree):
    """ElementTree wrapper with safe parsing capabilities."""

    def __init__(
        self,
        element: Element | None = None,
        file: str | bytes | os.PathLike[Any] | IO[Any] | None = None,
    ) -> None:
        super().__init__(element=element, file=file)

    def parse(
        self,
        source: str | bytes | os.PathLike[Any] | IO[Any],
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
    ) -> Element:
        root = parse(
            source=source,
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
        ).getroot()
        self._setroot(root)
        return root


def fromstring(
    text: str | bytes,
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
) -> Element:
    """Parse XML from string or bytes with strict security defenses.

    Args:
        text: XML string or bytes to parse.
        parser: Optional custom parser (supported for signature parity with stdlib).
        forbid_dtd: If True, reject any `<!DOCTYPE>` declarations with `DTDForbidden`.
        forbid_entities: If True, reject entity declarations and references with `EntitiesForbidden`.
        forbid_external: If True, reject external SYSTEM/PUBLIC references with `ExternalReferenceForbidden`.
        max_depth: Maximum allowed element nesting depth (default 1000).
        max_entity_size: Maximum allowed entity size (default 10MB).
        max_text_size: Maximum allowed accumulated text size (default 100MB).
        max_attributes: Maximum allowed attributes per element (default 1000).
        max_attribute_size: Maximum allowed size per attribute in bytes (default 10MB).
        max_name_size: Maximum allowed element tag or attribute name length (default 1024).
        max_comment_size: Maximum allowed XML comment size in bytes (default 10MB).

    Returns:
        The root `xml.etree.ElementTree.Element`.
    """
    return _parse_xml(
        text,
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
    )


XML = fromstring


def parse(
    source: str | bytes | os.PathLike[Any] | IO[Any],
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
) -> ElementTree:
    """Parse an XML document from a filepath or file-like object into an ElementTree."""
    if isinstance(source, (str, bytes, os.PathLike)):
        with open(source, "rb") as f:
            content = f.read()
    elif hasattr(source, "read"):
        content = source.read()
    else:
        raise TypeError(f"Invalid source type for parse(): {type(source).__name__}")

    root = _parse_xml(
        content,
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
    )
    tree = ElementTree()
    tree._setroot(root)
    return tree


def iterparse(
    source: str | bytes | os.PathLike[Any] | IO[Any],
    events: tuple[str, ...] | list[str] | None = None,
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
) -> Iterator[tuple[str, Element]]:
    """Incrementally parse an XML document, yielding (event, elem) pairs safely.

    Events can contain 'start' and 'end' (default is ('end',)).
    """
    wanted_events = set(events or ("end",))
    tree = parse(
        source,
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
    )
    root = tree.getroot()

    def _traverse(elem: Element) -> Iterator[tuple[str, Element]]:
        if "start" in wanted_events:
            yield ("start", elem)
        for child in elem:
            yield from _traverse(child)
        if "end" in wanted_events:
            yield ("end", elem)

    yield from _traverse(root)


__all__ = [
    "Comment",
    "DTDForbidden",
    "DefusedXmlException",
    "Element",
    "ElementTree",
    "EntitiesForbidden",
    "ExternalReferenceForbidden",
    "NotSupportedError",
    "PI",
    "ParseError",
    "ProcessingInstruction",
    "QName",
    "SubElement",
    "TreeBuilder",
    "XML",
    "XMLParse",
    "XMLParser",
    "canonicalize",
    "dump",
    "fromstring",
    "indent",
    "iterparse",
    "parse",
    "register_namespace",
    "tostring",
    "tostringlist",
]
