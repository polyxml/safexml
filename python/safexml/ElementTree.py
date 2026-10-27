"""Drop-in defused XML parser and modern ElementTree implementation.

Compatible with `defusedxml.ElementTree` and `xml.etree.ElementTree`.
Powered by Rust (`quick-xml`) with GIL release and strict entity/DoS defense.
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


class XMLParser:
    """Secure XMLParser compatible with xml.etree.ElementTree.XMLParser and defusedxml."""

    def __init__(
        self,
        *,
        target: Any | None = None,
        encoding: str | None = None,
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
        max_input_size: int = 256 * 1024 * 1024,
        max_elements: int = 5_000_000,
    ) -> None:
        self.target = target
        self.encoding = encoding
        self.forbid_dtd = forbid_dtd
        self.forbid_entities = forbid_entities
        self.forbid_external = forbid_external
        self.max_depth = max_depth
        self.max_entity_size = max_entity_size
        self.max_text_size = max_text_size
        self.max_attributes = max_attributes
        self.max_attribute_size = max_attribute_size
        self.max_name_size = max_name_size
        self.max_comment_size = max_comment_size
        self.max_input_size = max_input_size
        self.max_elements = max_elements
        self._chunks: list[bytes] = []
        self._total_size: int = 0

    def feed(self, data: str | bytes) -> None:
        raw_bytes = data.encode("utf-8") if isinstance(data, str) else data
        if self._total_size + len(raw_bytes) > self.max_input_size:
            self._chunks.clear()
            self._total_size = 0
            raise DefusedXmlException(
                f"Input document size exceeds maximum allowed limit ({self.max_input_size} bytes)"
            )
        self._total_size += len(raw_bytes)
        self._chunks.append(raw_bytes)

    def close(self) -> Element:
        combined = b"".join(self._chunks)
        self._chunks.clear()
        self._total_size = 0

        return _parse_xml(
            combined,
            forbid_dtd=self.forbid_dtd,
            forbid_entities=self.forbid_entities,
            forbid_external=self.forbid_external,
            max_depth=self.max_depth,
            max_entity_size=self.max_entity_size,
            max_text_size=self.max_text_size,
            max_attributes=self.max_attributes,
            max_attribute_size=self.max_attribute_size,
            max_name_size=self.max_name_size,
            max_comment_size=self.max_comment_size,
            max_input_size=self.max_input_size,
            max_elements=self.max_elements,
        )


DefusedXMLParser = XMLParser


class ElementTree(_StdlibElementTree):
    """ElementTree wrapper with safe parsing capabilities."""

    def __init__(
        self,
        element: Element | None = None,
        file: str | bytes | os.PathLike[Any] | IO[Any] | None = None,
    ) -> None:
        super().__init__(element=element, file=file)

    def getroot(self) -> Element:
        return super().getroot()  # type: ignore[return-value]

    def parse(  # type: ignore[override]
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
        max_input_size: int = 256 * 1024 * 1024,
        max_elements: int = 5_000_000,
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
            max_input_size=max_input_size,
            max_elements=max_elements,
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
    max_input_size: int = 256 * 1024 * 1024,
    max_elements: int = 5_000_000,
) -> Element:
    """Parse XML from string or bytes with strict security defenses."""
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
        max_input_size=max_input_size,
        max_elements=max_elements,
    )


XML = fromstring


def XMLID(
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
    max_input_size: int = 256 * 1024 * 1024,
    max_elements: int = 5_000_000,
) -> tuple[Element, dict[str, Element]]:
    """Parse XML from a string or bytes and return (root_element, id_dict) safely."""
    root = fromstring(
        text,
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
        max_input_size=max_input_size,
        max_elements=max_elements,
    )
    ids: dict[str, Element] = {}
    for elem in root.iter():
        elem_id = elem.get("id")
        if elem_id:
            ids[elem_id] = elem
    return root, ids


def fromstringlist(
    sequence: list[str] | list[bytes] | tuple[str, ...] | tuple[bytes, ...],
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
    max_input_size: int = 256 * 1024 * 1024,
    max_elements: int = 5_000_000,
) -> Element:
    """Parse XML from a sequence of fragments."""
    if not sequence:
        raise ParseError("No XML root element found")
    first = sequence[0]
    text = "".join(sequence) if isinstance(first, str) else b"".join(sequence)  # type: ignore[arg-type]
    return fromstring(
        text,
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
        max_input_size=max_input_size,
        max_elements=max_elements,
    )


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
    max_input_size: int = 256 * 1024 * 1024,
    max_elements: int = 5_000_000,
) -> ElementTree:
    """Parse an XML document from a filepath or file-like object into an ElementTree."""
    if isinstance(source, (str, bytes, os.PathLike)):
        with open(source, "rb") as f:
            root = _parse_xml(
                f,
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
                max_input_size=max_input_size,
                max_elements=max_elements,
            )
    elif hasattr(source, "read"):
        root = _parse_xml(
            source,
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
            max_input_size=max_input_size,
            max_elements=max_elements,
        )
    else:
        raise TypeError(f"Invalid source type for parse(): {type(source).__name__}")

    tree = ElementTree()
    tree._setroot(root)
    return tree


class iterparse:
    """Incrementally parse an XML document, yielding (event, elem) pairs safely."""

    def __init__(
        self,
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
        max_input_size: int = 256 * 1024 * 1024,
        max_elements: int = 5_000_000,
    ) -> None:
        self.root: Element | None = None
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
            max_input_size=max_input_size,
            max_elements=max_elements,
        )
        self.root = tree.getroot()
        self._events = tuple(events or ("end",))
        self._iter = self._generate_events(self.root, self._events)

    def _generate_events(self, root: Element, events: tuple[str, ...]) -> Iterator[tuple[str, Any]]:
        wanted = set(events)
        stack: list[tuple[Element, bool]] = [(root, False)]
        while stack:
            elem, visited = stack.pop()
            if visited:
                if "end" in wanted:
                    yield ("end", elem)
            else:
                if "start" in wanted:
                    yield ("start", elem)
                stack.append((elem, True))
                for child in reversed(elem):
                    stack.append((child, False))

    def __iter__(self) -> Iterator[tuple[str, Any]]:
        return self

    def __next__(self) -> tuple[str, Any]:
        return next(self._iter)


__all__ = [
    "Comment",
    "DTDForbidden",
    "DefusedXMLParser",
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
    "XMLID",
    "XMLParse",
    "XMLParser",
    "canonicalize",
    "dump",
    "fromstring",
    "fromstringlist",
    "indent",
    "iterparse",
    "parse",
    "register_namespace",
    "tostring",
    "tostringlist",
]
